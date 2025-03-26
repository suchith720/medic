# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/12_ngame-for-wikipedia-with-input-concatenation.ipynb.

# %% auto 0
__all__ = []

# %% ../nbs/12_ngame-for-wikipedia-with-input-concatenation.ipynb 2
import os,torch, torch.multiprocessing as mp, pickle, numpy as np
from transformers import AutoTokenizer
from tqdm.auto import tqdm

from xcai.basics import *
from xcai.models.PPP0XX import DBT009,DBT011

# %% ../nbs/12_ngame-for-wikipedia-with-input-concatenation.ipynb 4
os.environ['CUDA_VISIBLE_DEVICES'] = '2,3,4,5,6,7'
os.environ['WANDB_PROJECT']='medic_03-wikipedia'

# %% ../nbs/12_ngame-for-wikipedia-with-input-concatenation.ipynb 6
if __name__ == '__main__':
    build_block = False

    """ Load data """
    pkl_dir = '/home/aiscuser/scratch1/datasets'
    pkl_file = f'{pkl_dir}/processed/wikipedia_data-metas_distilbert-base-uncased_xcs_hlk-256.pkl'

    with open(pkl_file, 'rb') as file: block = pickle.load(file)
    
    """ Training Arguements """
    args = XCLearningArguments(
        output_dir='/home/aiscuser/scratch1/outputs/medic/12_ngame-for-wikipedia-with-input-concatenation-001',
        logging_first_step=True,
        per_device_train_batch_size=300,
        per_device_eval_batch_size=300,
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

        use_cpu_for_searching=True,
        use_cpu_for_clustering=True,

        clustering_devices=[2,3,4,5],
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
    
