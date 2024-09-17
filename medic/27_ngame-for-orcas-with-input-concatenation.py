# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/27_ngame-for-orcas-with-input-concatenation.ipynb.

# %% auto 0
__all__ = []

# %% ../nbs/27_ngame-for-orcas-with-input-concatenation.ipynb 2
import os,torch, torch.multiprocessing as mp, pickle, numpy as np
from xcai.basics import *
from xcai.models.PPP0XX import DBT009,DBT011

# %% ../nbs/27_ngame-for-orcas-with-input-concatenation.ipynb 4
os.environ['CUDA_VISIBLE_DEVICES'] = '0,1'
os.environ['WANDB_PROJECT']='medic_06-orcas'

# %% ../nbs/27_ngame-for-orcas-with-input-concatenation.ipynb 6
if __name__ == '__main__':
    build_block = False

    """ Load data """
    pkl_dir = '/home/scai/phd/aiz218323/scratch/datasets'
    pkl_file = f'{pkl_dir}/processed/orcas_data-meta_distilbert-base-uncased_xcs_gpt-128.pkl'

    if build_block:
        data_dir = '/home/scai/phd/aiz218323/Projects/XC_NLG/data'
        block = XCBlock.from_cfg(data_dir, 'data_meta', dset='orcas', transform_type='xcs', tokenizer='distilbert-base-uncased', 
                                 sampling_features=[('lbl2data',1)], oversample=False)

        block = AugmentMetaInputIdsTfm.apply(block, 'gpt_meta', 'data', 128, True)
        block = AugmentMetaInputIdsTfm.apply(block, 'gpt_meta', 'lbl', 128, True)

        with open(pkl_file, 'wb') as file: pickle.dump(block, file)
    else:
        with open(pkl_file, 'rb') as file: block = pickle.load(file)

    block.train.dset.data.data_info['input_ids'] = block.train.dset.data.data_info['input_ids_aug_gpt']
    block.train.dset.data.data_info['attention_mask'] = block.train.dset.data.data_info['attention_mask_aug_gpt']
    block.test.dset.data.data_info['input_ids'] = block.test.dset.data.data_info['input_ids_aug_gpt']
    block.test.dset.data.data_info['attention_mask'] = block.test.dset.data.data_info['attention_mask_aug_gpt']

    block.train.dset.data.lbl_info['input_ids'] = block.train.dset.data.lbl_info['input_ids_aug_gpt']
    block.train.dset.data.lbl_info['attention_mask'] = block.train.dset.data.lbl_info['attention_mask_aug_gpt']
    block.test.dset.data.lbl_info['input_ids'] = block.test.dset.data.lbl_info['input_ids_aug_gpt']
    block.test.dset.data.lbl_info['attention_mask'] = block.test.dset.data.lbl_info['attention_mask_aug_gpt']

    block.train.dset.meta = {}
    block.test.dset.meta = {}

    """ Training Arguements """
    args = XCLearningArguments(
        output_dir='/home/scai/phd/aiz218323/scratch/outputs/medic/27_ngame-for-orcas-with-input-concatenation',
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
    )

    metric = PrecRecl(block.n_lbl, block.test.data_lbl_filterer, prop=block.train.dset.data.data_lbl,
                      pk=10, rk=200, rep_pk=[1, 3, 5, 10], rep_rk=[10, 100, 200])

    """ Model """
    bsz = max(args.per_device_train_batch_size, args.per_device_eval_batch_size)*torch.cuda.device_count()
    model = DBT009.from_pretrained('sentence-transformers/msmarco-distilbert-base-v4', bsz=bsz, tn_targ=5000, margin=0.3, tau=0.1, 
                                   n_negatives=10, apply_softmax=True, use_encoder_parallel=True)
    model.init_dr_head()

    
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
    
