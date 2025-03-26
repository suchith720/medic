# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/23_ngame-linker-for-wikiseealsotitles.ipynb.

# %% auto 0
__all__ = ['get_meta_dataset', 'threshold_meta_dataset']

# %% ../nbs/23_ngame-linker-for-wikiseealsotitles.ipynb 2
import os,torch, torch.multiprocessing as mp, pickle, numpy as np
from scipy import sparse

from xcai.basics import *
from xcai.models.PPP0XX import DBT009,DBT011,DBT021
from xcai.models.distillation import TCH001,DTL007,TCH003,DTL008
from xcai.data import MetaXCDataset,XCDataset,MainXCDataset

from transformers import DistilBertConfig

# %% ../nbs/23_ngame-linker-for-wikiseealsotitles.ipynb 4
os.environ['WANDB_MODE'] = 'disabled'
os.environ['CUDA_VISIBLE_DEVICES'] = '10,11'
os.environ['WANDB_PROJECT']='medic_00-wikiseealsotitles'

# %% ../nbs/23_ngame-linker-for-wikiseealsotitles.ipynb 12
def get_meta_dataset(meta, idx):
    data_meta = meta.data_meta[:, idx]
    lbl_meta = meta.lbl_meta[:, idx]
    meta_info = {k:[v[i] for i in idx] for k,v in meta.meta_info.items()}
    return MetaXCDataset(meta.prefix, data_meta, lbl_meta, meta_info)
    
def threshold_meta_dataset(train_meta, test_meta, thresh=100):
    nnz = train_meta.data_meta.getnnz(axis=0)
    idx = np.where(np.logical_and(nnz < thresh, nnz > 0))[0]
    return get_meta_dataset(train_meta, idx), get_meta_dataset(test_meta, idx)
    

# %% ../nbs/23_ngame-linker-for-wikiseealsotitles.ipynb 37
if __name__ == '__main__':
    build_block = False

    meta_freq_threshold=100
    data_dir = '/data/datasets'
    pkl_dir = '/home/aiscuser/scratch1/datasets/'

    output_dir = '/home/aiscuser/scratch1/outputs/medic//23_ngame-linker-for-wikiseealsotitles-002'
    model_output = '/data/Projects/xc_nlg/outputs//67-ngame-ep-for-wikiseealso-with-input-concatenation-6-3'

    """ Load data """
    pkl_file = f'{pkl_dir}/processed/wikiseealsotitles_data-meta_distilbert-base-uncased_xcs.pkl'
    if build_block:
        block = XCBlock.from_cfg(data_dir, 'data_meta', transform_type='xcs', tokenizer='distilbert-base-uncased', 
                                 sampling_features=[('lbl2data', 4)], oversample=True)
        with open(pkl_file, 'wb') as file: pickle.dump(block, file)
    else:
        with open(pkl_file, 'rb') as file: block = pickle.load(file)

    """ Linker dataset """
    train_meta, test_meta = threshold_meta_dataset(block.train.dset.meta['cat_meta'], block.test.dset.meta['cat_meta'], thresh=100)
    block.train.dset.meta['cat_meta'], block.test.dset.meta['cat_meta'] = train_meta, test_meta

    train_idx = np.where(block.train.dset.meta['cat_meta'].data_meta.getnnz(axis=1) > 0)[0]
    train_block = block.train._getitems(train_idx)
    test_idx = np.where(block.test.dset.meta['cat_meta'].data_meta.getnnz(axis=1) > 0)[0]
    test_block = block.test._getitems(test_idx)

    sal_meta = MetaXCDataset('sal', train_block.dset.data.data_lbl, train_block.dset.meta['cat_meta'].lbl_meta.T.tocsr(), 
                             train_block.dset.data.lbl_info)
    train_dset = XCDataset(MainXCDataset(train_block.dset.data.data_info, train_block.dset.meta.cat_meta.data_meta, 
                                         train_block.dset.meta.cat_meta.meta_info), sal_meta=sal_meta)
    sal_meta = MetaXCDataset('sal', test_block.dset.data.data_lbl, test_block.dset.meta['cat_meta'].lbl_meta.T.tocsr(), 
                             test_block.dset.data.lbl_info)
    test_dset = XCDataset(MainXCDataset(test_block.dset.data.data_info, test_block.dset.meta.cat_meta.data_meta, 
                                        test_block.dset.meta.cat_meta.meta_info), sal_meta=sal_meta)

    block.collator.tfms.tfms[0].sampling_features = [('lbl2data,sal2lbl2data', (1,1)), ('sal2data', 1)]
    

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
        representation_search_type='BRUTEFORCE',
        adam_epsilon=1e-6,
        warmup_steps=100,
        weight_decay=0.01,
        learning_rate=2e-4,
    
        group_by_cluster=True,
        num_clustering_warmup_epochs=10,
        num_cluster_update_epochs=5,
        num_cluster_size_update_epochs=25,
        clustering_type='EXPO',
        minimum_cluster_size=2,
        maximum_cluster_size=1600,
        
        metric_for_best_model='P@1',
        load_best_model_at_end=True,
        target_indices_key='plbl2data_idx',
        target_pointer_key='plbl2data_data2ptr',
        
        use_encoder_parallel=True,
        max_grad_norm=None,
        fp16=True,
    
        label_names=['lbl2data_idx', 'lbl2data_input_ids', 'lbl2data_attention_mask',
                     'sal2data_idx', 'sal2data_input_ids', 'sal2data_attention_mask',
                     'sal2lbl2data_idx', 'sal2lbl2data_input_ids', 'sal2lbl2data_attention_mask'],

        prune_metadata=True,
        num_metadata_prune_warmup_epochs=0,
        num_metadata_prune_epochs=5,
        metadata_prune_batch_size=2048,
        prune_metadata_names=['sal_meta'],
        use_data_metadata_for_pruning=True,
        prune_metadata_threshold=0.0,
        prune_metadata_topk=3,
    )

    """ Model """
    teacher = TCH001.from_pretrained(f'{model_output}/teacher', n_data=block.train.dset.n_data, n_lbl=block.n_lbl)
    teacher.freeze_embeddings()
    m_teacher = TCH003(DistilBertConfig(), n_data=len(train_idx))
    m_teacher.init_embeddings(teacher.data_repr.weight.data[train_idx])
    m_teacher.freeze_embeddings()

    bsz = max(args.per_device_train_batch_size, args.per_device_eval_batch_size)*torch.cuda.device_count()

    m_student = DBT021.from_pretrained('sentence-transformers/msmarco-distilbert-base-v4', bsz=bsz, tn_targ=1000, margin=0.3, tau=0.1, 
                                       apply_softmax=True, n_negatives=10, m_lw=0.2, data_meta_prefix='sal2data', 
                                       lbl2data_meta_prefix='sal2lbl', use_encoder_parallel=True, task_repr_type='pool', 
                                       meta_repr_type='pool')
    m_student.init_dr_head()

    model = DTL008(DistilBertConfig(), m_student=m_student, m_teacher=m_teacher, bsz=bsz, tn_targ=5000, margin=0.3, tau=0.1, 
                   n_negatives=10, apply_softmax=True, teacher_data_student_label_loss_weight=1.0, data_mse_loss_weight=0.1)
    
    metric = PrecRecl(test_dset.n_lbl, test_dset.data.data_lbl_filterer, prop=train_dset.data.data_lbl,
                      pk=10, rk=200, rep_pk=[1, 3, 5, 10], rep_rk=[10, 100, 200])

    """ Training """
    learn = XCLearner(
        model=model, 
        args=args,
        train_dataset=train_dset,
        eval_dataset=test_dset,
        data_collator=block.collator,
        compute_metrics=metric,
    )

    mp.freeze_support()
    learn.train()
    
