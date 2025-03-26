# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/31_momos-for-wikiseealsotitles.ipynb.

# %% auto 0
__all__ = ['get_label_remap']

# %% ../nbs/31_momos-for-wikiseealsotitles.ipynb 2
import os,torch, torch.multiprocessing as mp, pickle, numpy as np
from transformers import DistilBertConfig

from xcai.basics import *
from xcai.models.oak import OAK008
from xcai.models.distillation import DTL011,TCH001,TCH002

from xclib.utils.sparse import retain_topk

from fastcore.utils import *

# %% ../nbs/31_momos-for-wikiseealsotitles.ipynb 4
os.environ['CUDA_VISIBLE_DEVICES'] = '0,1'
os.environ['WANDB_PROJECT']='medic_00-wikiseealsotitles'

# %% ../nbs/31_momos-for-wikiseealsotitles.ipynb 6
@patch
def get_label_representation(
    cls:DTL011,
    data_idx:Optional[torch.Tensor]=None,
    data_input_ids:Optional[torch.Tensor]=None,
    data_attention_mask:Optional[torch.Tensor]=None,
    **kwargs
):
    cls.m_student.get_label_representation(data_idx, data_input_ids, data_attention_mask, **kwargs)
    

# %% ../nbs/31_momos-for-wikiseealsotitles.ipynb 7
def get_label_remap(lbl_repr:torch.Tensor, cluster_sz:int=3):
    clusters = BalancedClusters.proc(lbl_repr.half(), min_cluster_sz=cluster_sz)

    lbl_remap = torch.zeros(lbl_repr.shape[0], dtype=torch.int64)
    for i,o in enumerate(clusters): lbl_remap[o] = i

    return lbl_remap, len(clusters)

# %% ../nbs/31_momos-for-wikiseealsotitles.ipynb 8
if __name__ == '__main__':
    build_block = False
    pkl_dir = '/home/scai/phd/aiz218323/scratch/datasets/'
    data_dir = '/home/scai/phd/aiz218323/Projects/XC_NLG/data'
    
    output_dir = '/home/scai/phd/aiz218323/scratch/outputs/medic/31_momos-for-wikiseealsotitles'
    model_output = '/home/scai/phd/aiz218323/scratch/outputs/67-ngame-ep-for-wikiseealso-with-input-concatenation-1-4'
    meta_embed_file = '/home/aiscuser/scratch/OGB_Weights/LF-WikiSeeAlsoTitles-320K/emb_weights.npy'

    """ Load data """
    pkl_file = f'{pkl_dir}/processed/wikiseealsotitles_data-lnk_distilbert-base-uncased_xcs.pkl'

    if build_block:
        block = XCBlock.from_cfg(data_dir, 'data_lnk', transform_type='xcs', tokenizer='distilbert-base-uncased', 
                                 sampling_features=[('lbl2data',4), ('lnk2data',3)], oversample=False)
        with open(pkl_file, 'wb') as file: pickle.dump(block, file)
    else:
        with open(pkl_file, 'rb') as file: block = pickle.load(file)

    """ Prune metadata """
    data_meta = retain_topk(block.train.dset.meta.lnk_meta.data_meta, k=5)
    lbl_meta = block.train.dset.meta.lnk_meta.lbl_meta
    block.train.dset.meta.lnk_meta.update_meta_matrix(data_meta, lbl_meta)
    
    data_meta = retain_topk(block.test.dset.meta.lnk_meta.data_meta, k=3)
    lbl_meta = block.test.dset.meta.lnk_meta.lbl_meta
    block.test.dset.meta.lnk_meta.update_meta_matrix(data_meta, lbl_meta)

    block.collator.tfms.tfms[0].sampling_features = [('lbl2data',4),('lnk2data',3)]
    block.collator.tfms.tfms[0].oversample = False
    
    block.train.dset.meta.lnk_meta.meta_info = None
    block.test.dset.meta.lnk_meta.meta_info = None

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
        
        label_names=['lbl2data_idx', 'lbl2data_input_ids', 'lbl2data_attention_mask', 'lnk2data_idx'],
        
        prune_metadata=False,
        num_metadata_prune_warmup_epochs=10,
        num_metadata_prune_epochs=5,
        metadata_prune_batch_size=2048,
        prune_metadata_names=['lnk_meta'],
        use_data_metadata_for_pruning=True,
    
        predict_with_augmentation=False,
        use_augmentation_index_representation=True,
    
        data_aug_meta_name='lnk',
        augmentation_num_beams=None,
        data_aug_prefix='lnk',
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

    lbl_remap, n_clusters = get_label_remap(m_teacher.lbl_repr.weight, cluster_sz=3)

    """ Student model """
    bsz = max(args.per_device_train_batch_size, args.per_device_eval_batch_size)*torch.cuda.device_count()

    m_student = OAK008.from_pretrained('sentence-transformers/msmarco-distilbert-base-v4', batch_size=bsz, num_batch_labels=5000,
                                       margin=0.3, num_negatives=10, tau=0.1, apply_softmax=True,
                                       
                                       data_aug_meta_prefix='lnk2data', lbl2data_aug_meta_prefix=None,
                                       data_pred_meta_prefix=None, lbl2data_pred_meta_prefix=None,
                                       
                                       num_metadata=block.train.dset.meta['lnk_meta'].n_meta, resize_length=5000,
                                       n_clusters=n_clusters, n_labels=block.n_lbl,
                                       
                                       calib_margin=0.05, calib_num_negatives=10, calib_tau=0.1, calib_apply_softmax=False,
                                       calib_loss_weight=0.1, use_calib_loss=True,
                                       
                                       use_query_loss=True,
                                       
                                       meta_loss_weight=0.0,
                                       
                                       fusion_loss_weight=0.1, use_fusion_loss=False,
                                       
                                       use_encoder_parallel=True)
    m_student.init_retrieval_head()
    m_student.init_cross_head()
    m_student.init_meta_embeddings()
    m_student.init_label_embeddings()
    m_student.set_label_remap(lbl_remap)
    
    # meta_embeddings = np.load(meta_embed_file)
    # m_student.encoder.set_pretrained_meta_embeddings(torch.tensor(meta_embeddings, dtype=torch.float32))
    m_student.encoder.set_pretrained_meta_embeddings(torch.zeros(block.train.dset.meta['lnk_meta'].n_meta, m_student.config.dim))
    m_student.encoder.freeze_pretrained_meta_embeddings()

    """ Distillation model """
    model = DTL011(DistilBertConfig(), m_student=m_student, m_teacher=m_teacher, bsz=bsz, tn_targ=5000, margin=0.3, tau=0.1, 
                   n_negatives=10, apply_softmax=True, bandit_learning_rate=0.01, bandit_minimum_value=0.05, bandit_collector=100)
    
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
    
