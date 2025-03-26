# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/01_teacher-model-for-distillation.ipynb.

# %% auto 0
__all__ = []

# %% ../nbs/01_teacher-model-for-distillation.ipynb 2
from tqdm.auto import tqdm
from scipy import sparse
import os,torch, torch.multiprocessing as mp, pickle, numpy as np
from safetensors import safe_open
from transformers import DistilBertConfig

from xcai.basics import *
from xcai.models.PPP0XX import DBT009
from xcai.models.distillation import TCH001

from xclib.utils.sparse import retain_topk

# %% ../nbs/01_teacher-model-for-distillation.ipynb 3
os.environ['WANDB_MODE'] = 'disabled'
os.environ['CUDA_VISIBLE_DEVICES'] = '14,15'

def random_topk(data_lbl, topk=5):
    data,indices,indptr = [],[],[0]
    for i,j in tqdm(zip(data_lbl.indptr, data_lbl.indptr[1:]), total=data_lbl.shape[0]):
        idx = np.random.permutation(j-i)[:topk]
        data.append(data_lbl.data[i:j][idx])
        indices.append(data_lbl.indices[i:j][idx])
        indptr.append(indptr[-1]+len(idx))
    data = np.hstack(data)
    indices = np.hstack(indices)
    indptr = np.array(indptr)

    o = sparse.csr_matrix((data,indices,indptr), shape=data_lbl.shape, dtype=np.float32)
    o.sort_indices()
    o.eliminate_zeros()
    return o

# %% ../nbs/01_teacher-model-for-distillation.ipynb 24
if __name__ == "__main__":
    build_block = False
    data_dir = '/data/datasets/'
    pkl_dir = '/home/aiscuser/scratch1/datasets/'
    output_dir = '/data/Projects/xc_nlg/outputs/67-ngame-ep-for-wikiseealso-with-input-concatenation-6-3/'
    
    """ Load data """
    pkl_file = f'{pkl_dir}/processed/wikiseealsotitles_data-cat-lnk_distilbert-base-uncased_xcs.pkl'
    if build_block:
        block = XCBlock.from_cfg(data_dir, 'data_cat_lnk', transform_type='xcs', tokenizer='distilbert-base-uncased', 
                                 sampling_features=[('lbl2data',1)], oversample=False)
        with open(pkl_file, 'wb') as file: pickle.dump(block, file)
    else:
        with open(pkl_file, 'rb') as file: block = pickle.load(file)

    block.collator.tfms.tfms[0].sampling_features = [('lbl2data',1)]
    block.collator.tfms.tfms[0].oversample = False

    data_meta = retain_topk(block.train.dset.meta.lnk_meta.data_meta, k=5)
    lbl_meta = block.train.dset.meta.lnk_meta.lbl_meta
    block.train.dset.meta.lnk_meta.update_meta_matrix(data_meta, lbl_meta)

    data_meta = retain_topk(block.test.dset.meta.lnk_meta.data_meta, k=3)
    lbl_meta = block.test.dset.meta.lnk_meta.lbl_meta
    block.test.dset.meta.lnk_meta.update_meta_matrix(data_meta, lbl_meta)

    block = AugmentMetaInputIdsTfm.apply(block, 'lnk_meta', 'data', 128, True)
    block = AugmentMetaInputIdsTfm.apply(block, 'cat_meta', 'lbl', 128, True)

    import pdb; pdb.set_trace()

    """ Augment metadata """
    block.train.dset.data.data_info['input_ids'] = block.train.dset.data.data_info['input_ids_aug_lnk']
    block.train.dset.data.data_info['attention_mask'] = block.train.dset.data.data_info['attention_mask_aug_lnk']
    block.test.dset.data.data_info['input_ids'] = block.test.dset.data.data_info['input_ids_aug_lnk']
    block.test.dset.data.data_info['attention_mask'] = block.test.dset.data.data_info['attention_mask_aug_lnk']

    block.train.dset.data.lbl_info['input_ids'] = block.train.dset.data.lbl_info['input_ids_aug_cat']
    block.train.dset.data.lbl_info['attention_mask'] = block.train.dset.data.lbl_info['attention_mask_aug_cat']
    block.test.dset.data.lbl_info['input_ids'] = block.test.dset.data.lbl_info['input_ids_aug_cat']
    block.test.dset.data.lbl_info['attention_mask'] = block.test.dset.data.lbl_info['attention_mask_aug_cat']
    
    """ Inference arguements """
    args = XCLearningArguments(
        output_dir=output_dir,
        logging_first_step=True,
        per_device_train_batch_size=800,
        per_device_eval_batch_size=800,
        representation_num_beams=200,
        representation_accumulation_steps=100,
        predict_with_representation=True,
        representation_search_type='BRUTEFORCE',
        target_indices_key='plbl2data_idx',
        target_pointer_key='plbl2data_data2ptr',
        use_encoder_parallel=True,
        fp16=True,
    )

    """ Load model """
    mname = f'{args.output_dir}/{os.path.basename(get_best_model(args.output_dir))}'

    model_weight_file,model_weights = f'{mname}/model.safetensors',{}
    with safe_open(model_weight_file, framework="pt") as file:
        for k in file.keys(): model_weights[k] = file.get_tensor(k)

    bsz = max(args.per_device_train_batch_size, args.per_device_eval_batch_size)*torch.cuda.device_count()
    model = DBT009.from_pretrained('sentence-transformers/msmarco-distilbert-base-v4', bsz=bsz, tn_targ=5000, margin=0.3, tau=0.1, 
                                   n_negatives=10, apply_softmax=True, use_encoder_parallel=True)

    model.load_state_dict(model_weights, strict=False)

    """ Inference """
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

    """ Metrics """
    o = learn.predict(block.test.dset)
    print(o.metrics)
