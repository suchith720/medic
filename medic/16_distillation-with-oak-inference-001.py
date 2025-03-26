# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/16_distillation-with-oak-inference.ipynb.

# %% auto 0
__all__ = ['get_predictions']

# %% ../nbs/16_distillation-with-oak-inference.ipynb 2
import os,torch, torch.multiprocessing as mp, pickle, numpy as np
from transformers import DistilBertConfig

from xcai.basics import *
from xcai.models.oak import OAK003
from xcai.models.distillation import DTL004,TCH001

from xclib.utils.sparse import retain_topk

from fastcore.utils import *

# %% ../nbs/16_distillation-with-oak-inference.ipynb 4
os.environ['CUDA_VISIBLE_DEVICES'] = '14,15'
os.environ['WANDB_MODE'] = 'disabled'

# %% ../nbs/16_distillation-with-oak-inference.ipynb 6
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
    

# %% ../nbs/16_distillation-with-oak-inference.ipynb 8
if __name__ == '__main__':
    build_block = False
    data_dir = '/data/datasets/'
    pkl_dir = '/home/aiscuser/scratch1/datasets/'

    dataset_name = 'wikiseealsotitles'
    output_dir = '/data/Projects/xc_nlg/outputs/86-distillation-for-wikiseealso-with-oak-7-3-4/'

    use_centroid_label_representation=False
    use_centroid_data_metadata=True
    centroid_data_attribute_representation='data_fused_repr'
    centroid_data_batch_size=2048
    use_teacher_lbl_representation=False
    use_teacher_data_representation=False

    """ Load data """
    # pkl_file = f'{pkl_dir}/processed/{dataset_name}_data-lnk_distilbert-base-uncased_xcs.pkl'
    pkl_file = f'{pkl_dir}/processed/{dataset_name}_data-cat-lnk_distilbert-base-uncased_xcs.pkl'
    if build_block:
        block = XCBlock.from_cfg(data_dir, 'data_lnk', dset=dataset_name, transform_type='xcs', tokenizer='distilbert-base-uncased', 
                                 sampling_features=[('lbl2data',4), ('lnk2data',3)], oversample=False)
        with open(pkl_file, 'wb') as file: pickle.dump(block, file)
    else:
        with open(pkl_file, 'rb') as file: block = pickle.load(file)

    """ Prune metadata """
    from xcai.data import MetaXCDataset

    nnz = block.train.dset.meta['cat_meta'].data_meta.getnnz(axis=0)
    idx = np.where(np.logical_or(nnz >= 100, nnz == 0))[0]

    meta_data = block.train.dset.meta['lnk_meta'].data_meta.T.tocsr()
    for row_num in idx:
        a = meta_data.indptr[row_num]
        b = meta_data.indptr[row_num+1]
        meta_data.data[a:b] = 0
    meta_data.eliminate_zeros()
    data_meta = meta_data.T.tocsr()

    data_meta = retain_topk(data_meta, k=5)
    # data_meta = retain_topk(block.train.dset.meta.lnk_meta.data_meta, k=5)
    lbl_meta = block.train.dset.meta.lnk_meta.lbl_meta
    block.train.dset.meta.lnk_meta.update_meta_matrix(data_meta, lbl_meta)

    meta_data = block.test.dset.meta['lnk_meta'].data_meta.T.tocsr()
    for row_num in idx:
        a = meta_data.indptr[row_num]
        b = meta_data.indptr[row_num+1]
        meta_data.data[a:b] = 0
    meta_data.eliminate_zeros()
    data_meta = meta_data.T.tocsr()
    
    data_meta = retain_topk(data_meta, k=3)
    # data_meta = retain_topk(block.test.dset.meta.lnk_meta.data_meta, k=3)
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

        use_centroid_label_representation=use_centroid_label_representation,
        use_centroid_data_metadata=use_centroid_data_metadata,
        centroid_data_attribute_representation=centroid_data_attribute_representation,
        centroid_data_batch_size=centroid_data_batch_size,
        use_teacher_lbl_representation=use_teacher_lbl_representation,
        use_teacher_data_representation=use_teacher_data_representation,
    )

    """ Teacher model """
    m_teacher = TCH001(DistilBertConfig(), n_data=block.train.dset.n_data, n_lbl=block.n_lbl)

    """ Student model """
    bsz = max(args.per_device_train_batch_size, args.per_device_eval_batch_size)*torch.cuda.device_count()

    m_student = OAK003.from_pretrained('sentence-transformers/msmarco-distilbert-base-v4', batch_size=bsz, num_batch_labels=5000,
                                       margin=0.3, num_negatives=5, tau=0.1, apply_softmax=True,
                                       
                                       data_aug_meta_prefix='lnk2data', lbl2data_aug_meta_prefix=None,
                                       data_pred_meta_prefix=None, lbl2data_pred_meta_prefix=None,
                                       
                                       num_metadata=block.train.dset.meta['lnk_meta'].n_meta, resize_length=5000,
                                       
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
                                   student_data_teacher_label_loss_weight=1.0, data_mse_loss_weight=0.1, label_mse_loss_weight=0.1)

    model.m_student.encoder.dr_head.activation = torch.nn.Identity()
    model.m_student.encoder.dr_fused_head.activation = torch.nn.Identity()
    model.m_student.encoder.meta_head.activation = torch.nn.Identity()


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

    os.makedirs(f'{output_dir}/predictions', exist_ok=True)
    train_pred_file, test_pred_file = get_predictions(f'{output_dir}/predictions/', args)

    o = learn.predict(block.test.dset)
    #with open(test_pred_file, 'wb') as file: pickle.dump(o, file)
    display_metric(o.metrics)
    print(o.metrics)

    if train_pred_file and False:
        o = learn.predict(block.train.dset)
        with open(train_pred_file, 'wb') as file: pickle.dump(o, file)
        display_metric(o.metrics)
        
    
