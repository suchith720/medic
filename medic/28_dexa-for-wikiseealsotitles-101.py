# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/28_dexa-for-wikiseealsotitles.ipynb.

# %% auto 0
__all__ = ['get_label_remap']

# %% ../nbs/28_dexa-for-wikiseealsotitles.ipynb 2
import os,torch, torch.multiprocessing as mp, pickle, numpy as np
from tqdm.auto import tqdm
from transformers import DistilBertConfig

from xcai.basics import *
from xcai.data import XCDataBlock
from xcai.models.PPP0XX import DBT009
from xcai.models.dexa import DEX001, DEX002
from xcai.clustering.cluster import BalancedClusters

from xclib.utils.sparse import retain_topk

from fastcore.utils import *

# %% ../nbs/28_dexa-for-wikiseealsotitles.ipynb 4
os.environ['CUDA_VISIBLE_DEVICES'] = '4,5'
os.environ['WANDB_MODE'] = 'disabled'

# %% ../nbs/28_dexa-for-wikiseealsotitles.ipynb 19
if __name__ == '__main__':
    build_block = False
    data_dir = '/data/datasets'
    pkl_dir = '/home/aiscuser/scratch1/datasets/'
    output_dir = '/home/aiscuser/scratch1/outputs/medic/28_dexa-for-wikiseealsotitles-001'

    """ Load data """
    pkl_file = f'{pkl_dir}/processed/wikiseealsotitles_data_distilbert-base-uncased_xcs.pkl'
    if build_block:
        block = XCBlock.from_cfg(data_dir, 'data', transform_type='xcs', tokenizer='distilbert-base-uncased', 
                                 sampling_features=[('lbl2data',4)], oversample=False)
        with open(pkl_file, 'wb') as file: pickle.dump(block, file)
    else:
        with open(pkl_file, 'rb') as file: block = pickle.load(file)

    block.collator.tfms.tfms[0].sampling_features = [('lbl2data',1)]
    block.collator.tfms.tfms[0].oversample = False

    n_clusters = 131072 

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
        
        output_representation_attribute='data_repr',
        label_representation_attribute='data_repr',
        metadata_representation_attribute='data_repr',
        data_augmentation_attribute='data_repr',
        representation_attribute='data_repr',
        clustering_representation_attribute='data_repr',
    
        metric_for_best_model='P@1',
        load_best_model_at_end=True,
        target_indices_key='plbl2data_idx',
        target_pointer_key='plbl2data_data2ptr',
        
        use_distributional_representation=False,
        use_encoder_parallel=True,
        max_grad_norm=None, 
        fp16=True,
    
        use_cpu_for_searching=True,
        use_cpu_for_clustering=True,
    )

    """ Model """
    bsz = max(args.per_device_train_batch_size, args.per_device_eval_batch_size)*torch.cuda.device_count()
    mname = f'{output_dir}/{os.path.basename(get_best_model(output_dir))}'
    model = DEX001.from_pretrained(mname, batch_size=bsz, num_batch_labels=5000,
                                   margin=0.3, num_negatives=10, tau=0.1, apply_softmax=True, use_encoder_parallel=True,
                                   n_labels=block.n_lbl, n_clusters=n_clusters)

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

    pred_dir = f'{output_dir}/predictions'
    os.makedirs(pred_dir, exist_ok=True)
    train_pred_file, test_pred_file = f'{pred_dir}/train_predictions.pkl', f'{pred_dir}/test_predictions.pkl' 

    o = learn.predict(block.test.dset)
    display_metric(o.metrics)
    print(o.metrics)

    with open(test_pred_file, 'wb') as file: pickle.dump(o, file)

    if train_pred_file:
        o = learn.predict(block.train.dset)
        display_metric(o.metrics)
        print(o.metrics)

        with open(train_pred_file, 'wb') as file: pickle.dump(o, file)
    
    
