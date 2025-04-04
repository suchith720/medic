# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/23_ngame-linker-for-wikiseealsotitles.ipynb.

# %% auto 0
__all__ = ['get_meta_dataset', 'threshold_meta_dataset']

# %% ../nbs/23_ngame-linker-for-wikiseealsotitles.ipynb 2
import os,torch, torch.multiprocessing as mp, pickle, numpy as np
from scipy import sparse
import torch.nn as nn

from xcai.basics import *
from xcai.models.PPP0XX import DBT009,DBT011,DBT021,XCModelOutput
from xcai.models.distillation import TCH001,DTL007,TCH003,DTL008
from xcai.data import MetaXCDataset,XCDataset,MainXCDataset

from fastcore.utils import *

from transformers import DistilBertConfig

# %% ../nbs/23_ngame-linker-for-wikiseealsotitles.ipynb 4
os.environ['WANDB_MODE'] = 'disabled'
os.environ['CUDA_VISIBLE_DEVICES'] = '2,3'

@patch
def forward(
    self:DBT021,
    data_input_ids:Optional[torch.Tensor]=None,
    data_attention_mask:Optional[torch.Tensor]=None,
    lbl2data_data2ptr:Optional[torch.Tensor]=None,
    lbl2data_idx:Optional[torch.Tensor]=None,
    lbl2data_input_ids:Optional[torch.Tensor]=None,
    lbl2data_attention_mask:Optional[torch.Tensor]=None,
    plbl2data_data2ptr:Optional[torch.Tensor]=None,
    plbl2data_idx:Optional[torch.Tensor]=None,
    output_attentions: Optional[bool] = None,
    output_hidden_states: Optional[bool] = None,
    return_dict: Optional[bool] = None,
    **kwargs
):  
    return_dict = return_dict if return_dict is not None else self.config.use_return_dict

    if self.use_encoder_parallel: 
        encoder = nn.DataParallel(module=self.encoder)
    else: encoder = self.encoder

    data_o, data_repr = encoder(data_input_ids, data_attention_mask, repr_type=self.task_repr_type)
        
    loss = lbl2data_repr = None
    if lbl2data_input_ids is not None:
        pass
            
    if not return_dict:
        o = (data_logits,data_repr,lbl2data_repr) + data_o[2:]
        return ((loss,lm_loss,dr_loss) + o) if loss is not None else o
        
    return XCModelOutput(
        loss=loss,
        dr_loss=loss,
        data_repr=data_repr,
        lbl2data_repr=lbl2data_repr,
        data_hidden_states=data_o.hidden_states,
        data_attentions=data_o.attentions,
    )


# %% ../nbs/23_ngame-linker-for-wikiseealsotitles.ipynb 37
if __name__ == '__main__':
    build_block = False

    data_dir = '/data/datasets'
    pkl_dir = '/home/aiscuser/scratch1/datasets/'
    output_dir = '/home/aiscuser/scratch1/outputs/medic/23_ngame-linker-for-wikiseealsotitles-005'

    """ Load data """
    pkl_file = f'{pkl_dir}/processed/wikiseealsotitles_data-meta_distilbert-base-uncased_xcs.pkl'
    if build_block:
        block = XCBlock.from_cfg(data_dir, 'data_meta', transform_type='xcs', tokenizer='distilbert-base-uncased', 
                                 sampling_features=[('lbl2data', 4)], oversample=True)
        with open(pkl_file, 'wb') as file: pickle.dump(block, file)
    else:
        with open(pkl_file, 'rb') as file: block = pickle.load(file)

    """ Linker dataset """
    train_dset = XCDataset(MainXCDataset(block.train.dset.data.data_info, block.train.dset.meta.cat_meta.data_meta, 
                                         block.train.dset.meta.cat_meta.meta_info))
    test_dset = XCDataset(MainXCDataset(block.test.dset.data.data_info, block.test.dset.meta.cat_meta.data_meta, 
                                        block.test.dset.meta.cat_meta.meta_info))

    block.collator.tfms.tfms[0].sampling_features = [('lbl2data', 1)]

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
    m_teacher = TCH003(DistilBertConfig(), n_data=train_dset.n_data)

    bsz = max(args.per_device_train_batch_size, args.per_device_eval_batch_size)*torch.cuda.device_count()

    m_student = DBT021.from_pretrained('sentence-transformers/msmarco-distilbert-base-v4', bsz=bsz, tn_targ=1000, margin=0.3, tau=0.1, 
                                       apply_softmax=True, n_negatives=10, m_lw=0.2, data_meta_prefix='sal2data', 
                                       lbl2data_meta_prefix='sal2lbl', use_encoder_parallel=True, task_repr_type='pool', 
                                       meta_repr_type='pool')

    mname = f'{output_dir}/{os.path.basename(get_best_model(output_dir))}'
    model = DTL008.from_pretrained(mname, m_student=m_student, m_teacher=m_teacher, bsz=bsz, tn_targ=5000, margin=0.3, tau=0.1, 
            n_negatives=10, apply_softmax=True, teacher_data_student_label_loss_weight=0.1, data_mse_loss_weight=0.0, ignore_mismatched_sizes=True)
    
    metric = PrecRecl(test_dset.n_lbl, test_dset.data.data_lbl_filterer, prop=train_dset.data.data_lbl,
                      pk=10, rk=200, rep_pk=[1, 3, 5, 10], rep_rk=[10, 100, 200], pa=0.5, pb=0.4)

    class DummyLoss(torch.nn.Module):
        def forward(self, *args, **kwargs):
            return 1
    loss_fn = DummyLoss()
    m_student.loss_fn = loss_fn
    model.rep_loss_fn = loss_fn

    """ Training """
    learn = XCLearner(
        model=model, 
        args=args,
        train_dataset=train_dset,
        eval_dataset=test_dset,
        data_collator=block.collator,
        compute_metrics=metric,
    )

    pred_dir = f'{output_dir}/linker'
    os.makedirs(pred_dir, exist_ok=True)

    train_pred_file, test_pred_file = f'{pred_dir}/train_predictions.pkl', f'{pred_dir}/test_predictions.pkl' 

    o = learn.predict(test_dset)
    with open(test_pred_file, 'wb') as file: pickle.dump(o, file)
    display_metric(o.metrics)
    print(o.metrics)

    if train_pred_file:
        o = learn.predict(train_dset)
        with open(train_pred_file, 'wb') as file: pickle.dump(o, file)
        display_metric(o.metrics)
        print(o.metrics)
    
