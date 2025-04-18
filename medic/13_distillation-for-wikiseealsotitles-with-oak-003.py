# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/13_distillation-for-wikiseealsotitles-with-oak.ipynb.

# %% auto 0
__all__ = []

# %% ../nbs/13_distillation-for-wikiseealsotitles-with-oak.ipynb 2
import os,torch, torch.multiprocessing as mp, pickle, numpy as np
from transformers import DistilBertConfig

from xcai.basics import *
from xcai.models.oak import OAK003
from xcai.models.distillation import DTL004,TCH001,TCH002
from xcai.models.classifiers import CLS001
from xcai.analysis import *
from xcai.data import MetaXCDataset

from xclib.utils.sparse import retain_topk

from fastcore.utils import *

# %% ../nbs/13_distillation-for-wikiseealsotitles-with-oak.ipynb 4
os.environ['CUDA_VISIBLE_DEVICES'] = '4,5'
os.environ['WANDB_PROJECT']='medic_00-wikiseealsotitles'

# %% ../nbs/13_distillation-for-wikiseealsotitles-with-oak.ipynb 6
if __name__ == '__main__':
    build_block = False
    data_dir = '/data/datasets'
    pkl_dir = '/home/aiscuser/scratch1/datasets/'

    output_dir = '/home/aiscuser/scratch1/outputs/medic/13_distillation-for-wikiseealsotitles-with-oak-003'
    model_output = '/data/Projects/xc_nlg/outputs//67-ngame-ep-for-wikiseealso-with-input-concatenation-6-3'
    meta_embed_file = '/data/OGB_Weights/LF-WikiSeeAlsoTitles-320K/emb_weights.npy'

    """ Load data """
    pkl_file = f'{pkl_dir}/processed/wikiseealsotitles_data-meta_distilbert-base-uncased_xcs.pkl'

    if build_block:
        block = XCBlock.from_cfg(data_dir, 'data-meta', transform_type='xcs', tokenizer='distilbert-base-uncased', 
                                 sampling_features=[('lbl2data',4), ('cat2data',5)], oversample=False)
        with open(pkl_file, 'wb') as file: pickle.dump(block, file)
    else:
        with open(pkl_file, 'rb') as file: block = pickle.load(file)

    """ Prune metadata """
    block.collator.tfms.tfms[0].sampling_features = [('lbl2data',4),('cat2data',5)]
    block.collator.tfms.tfms[0].oversample = False
    
    block.train.dset.meta['cat_meta'].meta_info = None
    block.test.dset.meta['cat_meta'].meta_info = None

    """ Training arguements """
    args = XCLearningArguments(
        output_dir=output_dir,
        logging_first_step=True,
        per_device_train_batch_size=800,
        per_device_eval_batch_size=800,
        representation_num_beams=200,
        representation_accumulation_steps=10,
        save_strategy="steps",
        evaluation_strategy="steps",
        eval_steps=5000,
        save_steps=5000,
        save_total_limit=5,
        num_train_epochs=300,
        predict_with_representation=True,
        adam_epsilon=1e-6,
        warmup_steps=100,
        weight_decay=0.01,
        learning_rate=2e-4,
        representation_search_type='BRUTEFORCE',
        
        output_representation_attribute='data_fused_repr',
        label_representation_attribute='data_repr',
        metadata_representation_attribute='data_repr',
        data_augmentation_attribute='data_repr',
        representation_attribute='data_fused_repr',
        clustering_representation_attribute='data_fused_repr',
    
        group_by_cluster=True,
        num_clustering_warmup_epochs=10,
        num_cluster_update_epochs=5,
        num_cluster_size_update_epochs=25,
        use_data_metadata_for_clustering=True,
        clustering_type='EXPO',
        minimum_cluster_size=2,
        maximum_cluster_size=1600,

        metric_for_best_model='P@1',
        load_best_model_at_end=True,
        target_indices_key='plbl2data_idx',
        target_pointer_key='plbl2data_data2ptr',
        
        use_distributional_representation=False,
        use_encoder_parallel=True,
        max_grad_norm=None, 
        fp16=True,
        
        label_names=['lbl2data_idx', 'lbl2data_input_ids', 'lbl2data_attention_mask', 'cat2data_idx'],
        
        prune_metadata=False,
        num_metadata_prune_warmup_epochs=10,
        num_metadata_prune_epochs=5,
        metadata_prune_batch_size=2048,
        prune_metadata_names=['cat_meta'],
        use_data_metadata_for_pruning=True,
    
        predict_with_augmentation=False,
        use_augmentation_index_representation=True,
    
        data_aug_meta_name='cat',
        augmentation_num_beams=None,
        data_aug_prefix='cat',
        use_label_metadata=False,
        
        data_meta_batch_size=2048,
        augment_metadata=False,
        num_metadata_augment_warmup_epochs=10,
        num_metadata_augment_epochs=5,
    
        use_cpu_for_searching=True,
        use_cpu_for_clustering=True,
    )

    """ Teacher model """
    m_teacher = TCH001.from_pretrained(f'{model_output}/teacher', n_data=block.train.dset.n_data, n_lbl=block.n_lbl)
    m_teacher.freeze_embeddings()

    """ Student model """
    bsz = max(args.per_device_train_batch_size, args.per_device_eval_batch_size)*torch.cuda.device_count()

    m_student = OAK003.from_pretrained('sentence-transformers/msmarco-distilbert-base-v4', batch_size=bsz, num_batch_labels=5000,
                                       margin=0.3, num_negatives=10, tau=0.1, apply_softmax=True,
                                       
                                       data_aug_meta_prefix='cat2data', lbl2data_aug_meta_prefix=None,
                                       data_pred_meta_prefix=None, lbl2data_pred_meta_prefix=None,
                                       
                                       num_metadata=block.train.dset.meta['cat_meta'].n_meta, resize_length=5000,
                                       
                                       calib_margin=0.05, calib_num_negatives=10, calib_tau=0.1, calib_apply_softmax=False,
                                       calib_loss_weight=0.1, use_calib_loss=True,
                                       
                                       use_query_loss=True,
                                       
                                       meta_loss_weight=0.0,
                                       
                                       fusion_loss_weight=0.1, use_fusion_loss=False,
                                       
                                       use_encoder_parallel=True)
    m_student.init_retrieval_head()
    m_student.init_cross_head()
    m_student.init_meta_embeddings()
    
    meta_embeddings = np.load(meta_embed_file)
    m_student.encoder.set_pretrained_meta_embeddings(torch.tensor(meta_embeddings, dtype=torch.float32))
    m_student.encoder.freeze_pretrained_meta_embeddings()

    """ Distillation model """
    model = DTL004(DistilBertConfig(), m_student=m_student, m_teacher=m_teacher, bsz=bsz, tn_targ=5000, margin=0.3, tau=0.1, 
                   n_negatives=10, apply_softmax=True, teacher_data_student_label_loss_weight=1.0, 
                   student_data_teacher_label_loss_weight=1.0, data_mse_loss_weight=0.1, label_mse_loss_weight=0.1)

    """ Training """
    metric = PrecRecl(block.n_lbl, block.test.data_lbl_filterer, prop=block.train.dset.data.data_lbl,
                      pk=10, rk=200, rep_pk=[1, 3, 5, 10], rep_rk=[10, 100, 200])

    learn = XCLearner(
        model=model, 
        args=args,
        train_dataset=block.train.dset,
        eval_dataset=block.test.dset,
        data_collator=block.collator,
        compute_metrics=metric,
    )
    
    mp.freeze_support()
    learn.train()
    
