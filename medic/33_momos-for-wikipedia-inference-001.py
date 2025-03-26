# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/32_momos-for-wikititles.ipynb.

# %% auto 0
__all__ = ['get_label_remap']

# %% ../nbs/32_momos-for-wikititles.ipynb 2
import os,torch, torch.multiprocessing as mp, pickle, numpy as np, transformers
from transformers import DistilBertConfig

from xcai.basics import *
from xcai.models.oakX import OAK004
from xcai.optimizers.oakX import MultipleOptimizer, MultipleScheduler
from xcai.models.distillation import DTL004,TCH001,TCH002
from xcai.models.classifiers import CLS001
from xcai.clustering.cluster import BalancedClusters

from xclib.utils.sparse import retain_topk

from fastcore.utils import *

# %% ../nbs/32_momos-for-wikititles.ipynb 4
os.environ['CUDA_VISIBLE_DEVICES'] = '10,11,12,13,14,15'
os.environ['WANDB_MODE'] = 'disabled'

# %% ../nbs/32_momos-for-wikititles.ipynb 6
@patch
def create_optimizer_and_scheduler(self:XCLearner, num_training_steps: int):
    NO_DECAY = ['bias', 'LayerNorm.weight']

    dense, sparse = [], []
    for k, p in model.named_parameters():
        if p.requires_grad:
            if "meta_embeddings" not in k: dense.append((k,p))
            else: sparse.append(p)

    params = [
        {'params': [p for n, p in dense if not any(nd in n for nd in NO_DECAY)], 'weight_decay': 0.01},
        {'params': [p for n, p in dense if any(nd in n for nd in NO_DECAY)], 'weight_decay': 0.0},
    ]

    optimizer_list = [torch.optim.AdamW(params, **{'lr': self.args.learning_rate, 'eps': 1e-6}),
                      torch.optim.SparseAdam(sparse, **{'lr': self.args.learning_rate * self.args.free_parameter_lr_coefficient, 'eps': 1e-6})]

    self.optimizer = MultipleOptimizer(optimizer_list)
    scheduler_list = [transformers.get_linear_schedule_with_warmup(self.optimizer.optimizers[0], num_warmup_steps=self.args.warmup_steps,
                                                                   num_training_steps=num_training_steps),
                        transformers.get_cosine_schedule_with_warmup(self.optimizer.optimizers[1],
                                                                     num_warmup_steps=self.args.free_parameter_warmup_steps,
                                                                     num_training_steps=num_training_steps)]

    self.lr_scheduler = MultipleScheduler(scheduler_list)

def get_predictions(pred_dir, args):
    train_pred_file, test_pred_file = None, None
    
    if args.use_centroid_label_representation:
        if args.use_teacher_data_representation: 
            test_pred_file = f'{pred_dir}/test_predictions_teacher_centroid.pkl'
        elif args.centroid_data_attribute_representation == 'data_repr': 
            test_pred_file = f'{pred_dir}/test_predictions_student-repr_centroid.pkl'
        else:
            test_pred_file = f'{pred_dir}/test_predictions_student-fused-repr_centroid.pkl'
    else:
        if args.use_teacher_lbl_representation: 
            test_pred_file = f'{pred_dir}/test_predictions_teacher.pkl'
            train_pred_file = f'{pred_dir}/train_predictions_teacher.pkl'
        else:
            test_pred_file = f'{pred_dir}/test_predictions.pkl'
            train_pred_file = f'{pred_dir}/train_predictions.pkl'
            
    return train_pred_file, test_pred_file

# %% ../nbs/32_momos-for-wikititles.ipynb 8
@patch
def get_label_representation(
    cls:DTL004,
    data_idx:Optional[torch.Tensor]=None,
    data_input_ids:Optional[torch.Tensor]=None,
    data_attention_mask:Optional[torch.Tensor]=None,
    **kwargs
):
    return cls.m_student.get_label_representation(data_idx, data_input_ids, data_attention_mask, **kwargs)
    

# %% ../nbs/32_momos-for-wikititles.ipynb 9
def get_label_remap(lbl_repr:torch.Tensor, cluster_sz:int=3):
    clusters = BalancedClusters.proc(lbl_repr.half(), min_cluster_sz=cluster_sz)

    lbl_remap = torch.zeros(lbl_repr.shape[0], dtype=torch.int64)
    for i,o in enumerate(clusters): lbl_remap[o] = i

    return lbl_remap, len(clusters)
    

# %% ../nbs/32_momos-for-wikititles.ipynb 10
if __name__ == '__main__':
    build_block = False

    data_dir = '/data/datasets'
    pkl_dir = '/home/aiscuser/scratch1/datasets/'

    output_dir = '/data/From_B/medic/33_momos-for-wikipedia-001'

    use_centroid_label_representation=False
    use_centroid_data_metadata=True
    centroid_data_attribute_representation='data_repr'
    centroid_data_batch_size=2048
    use_teacher_lbl_representation=False
    use_teacher_data_representation=False

    """ Load data """
    pkl_file = f'{pkl_dir}/processed/wikipedia_data-lnk_distilbert-base-uncased_xcs_256.pkl'

    if build_block:
        block = XCBlock.from_cfg(data_dir, 'data_lnk', dset='wikipedia', transform_type='oak', tokenizer='distilbert-base-uncased',
                padding=True, return_tensors='pt', num_labels=1, num_metadata=3, metadata_name='lnk', max_sequence_length=256)
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

    block.collator.tfms.tfms[0].n_labels = 1 
    block.collator.tfms.tfms[0].n_meta = 3
    block.collator.tfms.tfms[0].meta_name = 'lnk'
    
    block.train.dset.meta.lnk_meta.meta_info = None
    block.test.dset.meta.lnk_meta.meta_info = None

    """ Training arguements """
    args = XCLearningArguments(
        output_dir=output_dir,
        logging_first_step=True,
        per_device_train_batch_size=110,
        per_device_eval_batch_size=110,
        representation_num_beams=200,
        representation_accumulation_steps=10,
        save_strategy="steps",
        evaluation_strategy="steps",
        eval_steps=10_000,
        save_steps=10_000,
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

        free_parameter_warmup_steps=0,
        free_parameter_lr_coefficient=1000,

        clustering_devices=[4,5,6,7],

        use_memory_aggressively=False,

        use_centroid_label_representation=use_centroid_label_representation,
        use_centroid_data_metadata=use_centroid_data_metadata,
        centroid_data_attribute_representation=centroid_data_attribute_representation,
        centroid_data_batch_size=centroid_data_batch_size,
        use_teacher_lbl_representation=use_teacher_lbl_representation,
        use_teacher_data_representation=use_teacher_data_representation,

        use_data_metadata_for_representation=True,
    )

    """ Teacher model """
    m_teacher = TCH001(DistilBertConfig(), n_data=block.train.dset.n_data, n_lbl=block.n_lbl)

    n_clusters = 262144

    """ Student model """
    bsz = max(args.per_device_train_batch_size, args.per_device_eval_batch_size)*torch.cuda.device_count()

    m_student = OAK004.from_pretrained('sentence-transformers/msmarco-distilbert-base-v4', batch_size=bsz, num_batch_labels=5000,
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

    """ Distillation model """
    mname = f'{output_dir}/{os.path.basename(get_best_model(output_dir))}'
    model = DTL004.from_pretrained(mname, m_student=m_student, m_teacher=m_teacher, bsz=bsz, tn_targ=5000, margin=0.3, tau=0.1,
                   n_negatives=10, apply_softmax=True, teacher_data_student_label_loss_weight=1.0,
                   student_data_teacher_label_loss_weight=0.0, data_mse_loss_weight=0.1, label_mse_loss_weight=0.0)
    
    """ Training """
    metric = PrecRecl(block.n_lbl, block.test.data_lbl_filterer, prop=block.train.dset.data.data_lbl,
                      pk=10, rk=200, rep_pk=[1, 3, 5, 10], rep_rk=[10, 100, 200], pa=0.5, pb=0.4)

    learn = XCLearner(
        model=model, 
        args=args,
        train_dataset=block.train.dset,
        eval_dataset=block.test.dset,
        data_collator=block.collator,
        compute_metrics=metric,
    )
    
    train_rep, lbl_rep = learn.get_data_and_lbl_representation(learn.train_dataset)
    test_rep = learn._get_data_representation(learn.eval_dataset)

    c_model = CLS001(DistilBertConfig(), n_train=block.train.dset.n_data, n_test=block.test.dset.n_data, n_lbl=block.n_lbl,
               batch_size=bsz, num_batch_labels=5000, margin=0.3, num_negatives=10, tau=0.1, apply_softmax=True)
    c_model.init_representation(train_rep, test_rep, lbl_rep)

    fname = f'{os.path.dirname(mname)}/representation'
    c_model.save_pretrained(fname)

    exit()

    """ 
    inference
    """
    os.makedirs(f'{output_dir}/predictions', exist_ok=True)
    train_pred_file, test_pred_file = get_predictions(f'{output_dir}/predictions/', args)

    o = learn.predict(block.test.dset)
    with open(test_pred_file, 'wb') as file: pickle.dump(o, file)
    print(o.metrics)

    
