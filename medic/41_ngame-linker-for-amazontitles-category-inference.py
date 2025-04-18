# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/00_ngame-for-wikiseealsotitles-with-input-concatenation.ipynb.

# %% auto 0
__all__ = []

# %% ../nbs/00_ngame-for-wikiseealsotitles-with-input-concatenation.ipynb 2
import os,torch, torch.multiprocessing as mp, pickle, numpy as np
from xcai.basics import *
from xcai.models.PPP0XX import DBT009,DBT011
from data.config import load_config

from xcai.data import XCDataset, MainXCDataset
import xclib.data.data_utils as du

import argparse

# %% ../nbs/00_ngame-for-wikiseealsotitles-with-input-concatenation.ipynb 4
os.environ['CUDA_VISIBLE_DEVICES'] = '4,5' 
os.environ['WANDB_MODE'] = 'disabled'


# %% ../nbs/00_ngame-for-wikiseealsotitles-with-input-concatenation.ipynb 26
if __name__ == '__main__':
    build_block = False

    config = load_config('data/config.json')
    data_dir, pkl_dir, output_dir = config.data_dir, config.pkl_dir, config.output_dir

    output_dir = f'{output_dir}/41_ngame-linker-for-amazontitles-category'

    """ Load data """
    pkl_file = f'{pkl_dir}/processed/amazontitles_data-meta_distilbert-base-uncased.pkl'
    if build_block:
        block = XCBlock.from_cfg(data_dir, 'data_meta', dset='amazontitles', transform_type='xcs', tokenizer='distilbert-base-uncased', 
                                 sampling_features=[('lbl2data',1)], oversample=False)
        with open(pkl_file, 'wb') as file: pickle.dump(block, file)
    else:
        with open(pkl_file, 'rb') as file: block = pickle.load(file)

    train_dset = XCDataset(MainXCDataset(block.train.dset.data.data_info, block.train.dset.meta.cat_meta.data_meta, 
                                         block.train.dset.meta.cat_meta.meta_info))
    test_dset = XCDataset(MainXCDataset(block.test.dset.data.data_info, block.test.dset.meta.cat_meta.data_meta, 
                                        block.test.dset.meta.cat_meta.meta_info))

    block.collator.tfms.tfms[0].sampling_features = [('lbl2data',1)]
    block.collator.tfms.tfms[0].oversample = False

    """ Training Arguements """
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
        learning_rate=2e-5,
        
        target_indices_key='plbl2data_idx',
        target_pointer_key='plbl2data_data2ptr',
        
        use_encoder_parallel=True,
        max_grad_norm=None,
        fp16=True,
    )

    metric = PrecRecl(test_dset.n_lbl, test_dset.data.data_lbl_filterer, prop=train_dset.data.data_lbl,
                      pk=10, rk=200, rep_pk=[1, 3, 5, 10], rep_rk=[10, 100, 200])

    """ Model """
    mname = f'{output_dir}/{os.path.basename(get_best_model(output_dir))}'
    bsz = max(args.per_device_train_batch_size, args.per_device_eval_batch_size)*torch.cuda.device_count()
    model = DBT009.from_pretrained(mname, bsz=bsz, tn_targ=5000, margin=0.3, tau=0.1, 
                                   n_negatives=10, apply_softmax=True, use_encoder_parallel=True)

    class LossFn(torch.nn.Module):
        def forward(*args, **kwargs):
            return torch.tensor(1.0)
    model.loss_fn = LossFn()

    learn = XCLearner(
        model=model, 
        args=args,
        train_dataset=train_dset,
        eval_dataset=test_dset,
        data_collator=block.collator,
        compute_metrics=metric,
    )

    def get_sparse(pred_idx, pred_ptr, pred_score, n_lbl):
        n_data = pred_ptr.shape[0]
        pred_ptr = torch.cat([torch.zeros((1,), dtype=torch.long), pred_ptr.cumsum(dim=0)])
        pred = sparse.csr_matrix((pred_score,pred_idx,pred_ptr), shape=(n_data, n_lbl))
        return pred
    
    os.makedirs(f'{output_dir}/predictions', exist_ok=True)

    o = learn.predict(test_dset)
    print(o.metrics)
    pred = get_sparse(o.pred_idx, o.pred_ptr, o.pred_score, test_dset.data.n_lbl)
    du.write_sparse_file(pred, f'{output_dir}/predictions/test_predictions.txt')

    o = learn.predict(train_dset)
    print(o.metrics)
    pred = get_sparse(o.pred_idx, o.pred_ptr, o.pred_score, train_dset.data.n_lbl)
    du.write_sparse_file(pred, f'{output_dir}/predictions/train_predictions.txt')

