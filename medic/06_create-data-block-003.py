# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/06_create-data-block.ipynb.

# %% auto 0
__all__ = ['experiment_type', 'dataset_name', 'data_dir', 'pkl_dir', 'separate_title_and_content', 'tokenize', 'append_sep_token',
           'append_sep_token_into_block', 'concatenate_title_and_content_ids', 'create_block']

# %% ../nbs/06_create-data-block.ipynb 2
import os,torch, torch.multiprocessing as mp, pickle, numpy as np, argparse
from transformers import AutoTokenizer
from tqdm.auto import tqdm

from typing import Optional

from xcai.basics import *

# %% ../nbs/06_create-data-block.ipynb 4
def separate_title_and_content(input_text):
    title,content = [],[]
    for o in tqdm(input_text):
        text = o.split('  ', maxsplit=1)

        if len(text) == 2: 
            t,c = text
        else: 
            t,c = text[0], ''

        title.append(t)
        content.append(c)
    return title, content

def tokenize(tokenizer, info):
    o = tokenizer(info['input_text'], truncation=True, max_length=32)
    info.update(o)
    
    o = tokenizer(info['content_text'], truncation=True, max_length=1024)
    
    info['content_input_ids'] = o['input_ids']
    info['content_attention_mask'] = o['attention_mask']

def append_sep_token(input_ids, attention_mask):
    sep_tok = input_ids[0][-1]
    
    new_input_ids = [o+[sep_tok] for o in input_ids]
    new_attention_mask = [o+[1] for o in attention_mask]
    
    return new_input_ids, new_attention_mask

def append_sep_token_into_block(block):
    dset_type = ['train', 'test']
    info_type = ['data_info', 'lbl_info']
    
    for dt in dset_type:
        dset = getattr(block, dt)
        for it in info_type:
            info = getattr(dset.dset.data, it)
            input_ids, attention_mask = append_sep_token(info['input_ids'], info['attention_mask'])
            info['input_ids'],info['attention_mask'] = input_ids, attention_mask

def concatenate_title_and_content_ids(info, max_input_length, exclude_sep_tok=True):
    n_data = len(info['input_ids'])
    sep_tok = info['input_ids'][0][-1]
    
    for i,(p,q) in tqdm(enumerate(zip(info['input_ids'],info['content_input_ids'])), total=n_data):
        input_ids = p[:-1] + q[1:] if exclude_sep_tok else p + q[1:]
        if len(input_ids) > max_input_length:
            input_ids = input_ids[:max_input_length-1] + [sep_tok]
        info['input_ids'][i] = input_ids
    
    for i,(p,q) in tqdm(enumerate(zip(info['attention_mask'],info['content_attention_mask'])), total=n_data):
        attention_mask = p[:-1] + q[1:] if exclude_sep_tok else p + q[1:]
        if len(attention_mask) > max_input_length:
            attention_mask = attention_mask[:max_input_length-1] + [1]
        info['attention_mask'][i] = attention_mask
        

# %% ../nbs/06_create-data-block.ipynb 5
def create_block(data_dir:str, dataset_name:str, block_type:str, pkl_dir:str, sampling_features=[('lbl2data',4), ('lnk2data',3)], 
                 oversample:Optional[bool]=False, pkl_suffix:Optional[str]=''):
    pkl_suffix = f'-{pkl_suffix}' if pkl_suffix else pkl_suffix
    pkl_file = f'{pkl_dir}/processed/{dataset_name}_{block_type.replace("_", "-")}_distilbert-base-uncased_xcs{pkl_suffix}.pkl'
    block = XCBlock.from_cfg(data_dir, block_type, dset=dataset_name, transform_type='xcs', tokenizer='distilbert-base-uncased', 
                             sampling_features=sampling_features, oversample=oversample)
    with open(pkl_file, 'wb') as file: pickle.dump(block, file)
    return block


# %% ../nbs/06_create-data-block.ipynb 25
data_dir = '/data/From_B/'
pkl_dir = '/home/aiscuser/scratch1/datasets/'

# %% ../nbs/06_create-data-block.ipynb 26
if __name__ == '__main__':
    
    parser = argparse.ArgumentParser(description='create data block.')
    parser.add_argument('--experiment_type', type=str)
    parser.add_argument('--dataset_name', type=str)
    args = parser.parse_args()

    experiment_type, dataset_name = args.experiment_type, args.dataset_name

    if experiment_type == 'linker':
        
        block_type = 'data_lnk'
        sampling_features = [('lbl2data',4), ('lnk2data',3)]
        oversample = False
        block = create_block(data_dir, dataset_name, block_type, pkl_dir, sampling_features, oversample)
    
    elif experiment_type == 'teacher':
    
        if dataset_name == 'amazontitles131':
            block_type = 'data_meta'
            sampling_features = [('lbl2data',1)]
            oversample = False
            meta_name = 'cat' 
            
            block = create_block(data_dir, dataset_name, block_type, pkl_dir, sampling_features, oversample)
            
            """ Append metadata """
            block = AugmentMetaInputIdsTfm.apply(block, f'{meta_name}_meta', 'data', 128, True)
            block = AugmentMetaInputIdsTfm.apply(block, f'{meta_name}_meta', 'lbl', 128, True)
            
            pkl_file = f'{pkl_dir}/processed/{dataset_name}_{block_type.replace("_", "-")}_distilbert-base-uncased_xcs_{meta_name}-128.pkl'
            with open(pkl_file, 'wb') as file: pickle.dump(block, file)
            
        elif dataset_name == 'amazon131':
            block_type = 'data_meta'
            sampling_features = [('lbl2data',1)]
            oversample = False
            
            block = create_block(data_dir, dataset_name, block_type, pkl_dir, sampling_features, oversample)
            
            """ Separate title and content """
            train_title, train_content = separate_title_and_content(block.train.dset.data.data_info['input_text'])
            test_title, test_content = separate_title_and_content(block.test.dset.data.data_info['input_text'])
            
            block.train.dset.data.data_info['input_text'] = train_title
            block.train.dset.data.data_info['content_text'] = train_content
            
            block.test.dset.data.data_info['input_text'] = test_title
            block.test.dset.data.data_info['content_text'] = test_content
            
            """ Tokenize the title and content """
            tokenizer = AutoTokenizer.from_pretrained('distilbert-base-uncased')
            tokenize(tokenizer, block.train.dset.data.data_info)
            tokenize(tokenizer, block.test.dset.data.data_info)
            
            append_sep_token_into_block(block)
    
            """ Append metadata """
            block = AugmentMetaInputIdsTfm.apply(block, 'cat_meta', 'data', 256, True)
            block = AugmentMetaInputIdsTfm.apply(block, 'cat_meta', 'lbl', 256, True)
            
            block.train.dset.data.data_info['input_ids'] = block.train.dset.data.data_info['input_ids_aug_cat']
            block.train.dset.data.data_info['attention_mask'] = block.train.dset.data.data_info['attention_mask_aug_cat']
            block.test.dset.data.data_info['input_ids'] = block.test.dset.data.data_info['input_ids_aug_cat']
            block.test.dset.data.data_info['attention_mask'] = block.test.dset.data.data_info['attention_mask_aug_cat']
            
            block.train.dset.data.lbl_info['input_ids'] = block.train.dset.data.lbl_info['input_ids_aug_cat']
            block.train.dset.data.lbl_info['attention_mask'] = block.train.dset.data.lbl_info['attention_mask_aug_cat']
            block.test.dset.data.lbl_info['input_ids'] = block.test.dset.data.lbl_info['input_ids_aug_cat']
            block.test.dset.data.lbl_info['attention_mask'] = block.test.dset.data.lbl_info['attention_mask_aug_cat']
                
            """ Append the content """
            concatenate_title_and_content_ids(block.train.dset.data.data_info, 256, exclude_sep_tok=False)
            concatenate_title_and_content_ids(block.test.dset.data.data_info, 256, exclude_sep_tok=False)
            
            pkl_file = f'{pkl_dir}/processed/{dataset_name}_{block_type.replace("_", "-")}_distilbert-base-uncased_xcs_cat-256.pkl'
            with open(pkl_file, 'wb') as file: block = pickle.dump(block, file)
    
        else:
            raise ValueError(f'Invalid `dataset_name`: {dataset_name}')
    else:
        raise ValueError(f'Invalid `experiment_type`: {experiment_type}')
