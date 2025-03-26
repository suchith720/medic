# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/09_combine-predictions.ipynb.

# %% auto 0
__all__ = ['PredictionArguements', 'get_predictions', 'get_sparse_predictions']

# %% ../nbs/09_combine-predictions.ipynb 2
import os,torch, torch.multiprocessing as mp, pickle, numpy as np
from dataclasses import dataclass
from transformers import DistilBertConfig

from xcai.basics import *
from xcai.analysis import *

from fastcore.utils import *

from xclib.utils.sparse import retain_topk
import xclib.evaluation.xc_metrics as xc_metrics

# %% ../nbs/09_combine-predictions.ipynb 4
@dataclass
class PredictionArguements:
    use_centroid_label_representation: bool = False
    use_centroid_data_metadata: bool = True
    centroid_data_attribute_representation: str = 'data_repr'
    centroid_data_batch_size: int = 2048
    use_teacher_lbl_representation: bool = False
    use_teacher_data_representation: bool = False
    

# %% ../nbs/09_combine-predictions.ipynb 5
def get_predictions(pred_dir, args):
    train_o, test_o = None, None
    
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
        
        if os.path.exists(train_pred_file):
            with open(train_pred_file, 'rb') as file: train_o = pickle.load(file)
    
    if os.path.exists(test_pred_file):
        with open(test_pred_file, 'rb') as file: test_o = pickle.load(file)
            
    return test_o, train_o
    

# %% ../nbs/09_combine-predictions.ipynb 6
def get_sparse_predictions(output_dir, use_centroid_label_representation, use_centroid_data_metadata, 
                           centroid_data_attribute_representation, centroid_data_batch_size, use_teacher_lbl_representation, 
                           use_teacher_data_representation, n_lbl):
    
    pred_dir = f'{output_dir}/predictions'
    
    args = PredictionArguements(
        use_centroid_label_representation=use_centroid_label_representation,
        use_centroid_data_metadata=use_centroid_data_metadata,
        centroid_data_attribute_representation=centroid_data_attribute_representation,
        centroid_data_batch_size=centroid_data_batch_size,
        use_teacher_lbl_representation=use_teacher_lbl_representation,
        use_teacher_data_representation=use_teacher_data_representation,
    )
    test_o, train_o = get_predictions(pred_dir, args)
    
    test_lbl = get_pred_sparse(test_o, n_lbl)
    train_lbl = get_pred_sparse(train_o, n_lbl)

    return test_lbl, train_lbl
    

# %% ../nbs/09_combine-predictions.ipynb 18
if __name__ == '__main__':
    build_block = False
    pkl_dir = '/home/aiscuser/scratch1/datasets/'
    data_dir = '/data/datasets/'

    dataset_name = 'wikipedia'
    # dataset_name = 'wikititles'

    """ Load data """
    # pkl_file = f'{pkl_dir}/processed/{dataset_name}_data_distilbert-base-uncased_xcs.pkl'
    pkl_file = f'{pkl_dir}/processed/{dataset_name}_data-lnk_distilbert-base-uncased_xcs_256.pkl'
    if build_block:
        block = XCBlock.from_cfg(data_dir, 'data', dset=dataset_name, transform_type='xcs', tokenizer='distilbert-base-uncased', 
                                 sampling_features=[('lbl2data',1)], oversample=False)
        with open(pkl_file, 'wb') as file: pickle.dump(block, file)
        exit()
    else:
        with open(pkl_file, 'rb') as file: block = pickle.load(file)
    
    block.collator.tfms.tfms[0].sampling_features = [('lbl2data',1)]
    block.collator.tfms.tfms[0].oversample = False

    """ Load predictions """
    # output_dir = '/home/aiscuser/scratch1/outputs/medic/05_extreme-classifiers-002'
    # output_dir = '/data/Projects/xc_nlg/outputs/86-distillation-for-wikiseealso-with-oak-7-3-4'

    # output_dir = '/home/aiscuser/scratch1/outputs/medic/05_extreme-classifiers-203'
    # output_dir = '/home/aiscuser/scratch1/outputs/medic/19_distillation-for-wikiseealso-with-oak-002'

    # output_dir = '/home/aiscuser/scratch1/outputs/medic/04_distillation-for-wikititles-with-oak-004'

    # output_dir = '/data/From_B/medic/33_momos-for-wikipedia-001'
    # output_dir = '/home/aiscuser/scratch1/outputs/medic/05_extreme-classifiers-302'

    output_dir = '/home/aiscuser/scratch1/outputs/medic/32_momos-for-wikititles-002'
    
    use_centroid_label_representation=False
    use_centroid_data_metadata=True
    centroid_data_attribute_representation='data_repr'
    centroid_data_batch_size=2048
    use_teacher_lbl_representation=False
    use_teacher_data_representation=False
    
    test_a, train_a = get_sparse_predictions(output_dir, use_centroid_label_representation, use_centroid_data_metadata, 
                                             centroid_data_attribute_representation, centroid_data_batch_size, use_teacher_lbl_representation, 
                                             use_teacher_data_representation, block.n_lbl)

    # output_dir = '/data/Projects/xc_nlg/outputs/86-distillation-for-wikiseealso-with-oak-7-3-4'

    # output_dir = '/home/aiscuser/scratch1/outputs/medic/19_distillation-for-wikiseealso-with-oak-002'

    # output_dir = '/home/aiscuser/scratch1/outputs/medic/04_distillation-for-wikititles-with-oak-004'

    # output_dir = '/data/From_B/medic/33_momos-for-wikipedia-001'

    output_dir = '/home/aiscuser/scratch1/outputs/medic/32_momos-for-wikititles-002'

    use_centroid_label_representation= False
    use_centroid_data_metadata=True
    centroid_data_attribute_representation='data_repr'
    centroid_data_batch_size=2048
    use_teacher_lbl_representation=True
    use_teacher_data_representation=False
    
    test_b, train_b = get_sparse_predictions(output_dir, use_centroid_label_representation, use_centroid_data_metadata, 
                                             centroid_data_attribute_representation, centroid_data_batch_size, use_teacher_lbl_representation, 
                                             use_teacher_data_representation, block.n_lbl)

    """ Fusion """
    def get_output(block, pred):
        output = {
            'targ_idx': torch.tensor(block.test.dset.data.data_lbl.indices),
            'targ_ptr': torch.tensor([q-p for p,q in zip(block.test.dset.data.data_lbl.indptr, block.test.dset.data.data_lbl.indptr[1:])]),
            'pred_idx': torch.tensor(pred.indices),
            'pred_ptr': torch.tensor([q-p for p,q in zip(pred.indptr, pred.indptr[1:])]),
            'pred_score': torch.tensor(pred.data),
        }
        return output
    
    metric = PrecRecl(block.n_lbl, block.test.data_lbl_filterer, prop=block.train.dset.data.data_lbl,
            pk=10, rk=200, rep_pk=[1, 3, 5, 10], rep_rk=[10, 100, 200], pa=0.5, pb=0.4)

    display_metric(metric(**get_output(block, test_a)), remove_prefix=False)
    display_metric(metric(**get_output(block, test_b)), remove_prefix=False)

    def score(alpha):
        x = test_a + alpha * test_b
        o = get_output(block, x)
        print(metric(**o))

    for a in [0.01, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5]:
        print(f"BETA::{a}")
        score(a)
    exit()

    prop = xc_metrics.compute_inv_propesity(block.train.dset.data.data_lbl, A=0.55, B=1.5)
    fuser = ScoreFusion(prop)
    fuser.fit(train_a, train_b, block.train.dset.data.data_lbl, n_samples=100_000)

    metric = PrecRecl(block.n_lbl, block.test.data_lbl_filterer, prop=block.train.dset.data.data_lbl,
            pk=10, rk=200, rep_pk=[1, 3, 5, 10], rep_rk=[10, 100, 200])

    for beta in np.linspace(0,2,20):
        pred = fuser.predict(test_a, test_b, beta=beta)
        output = get_output(block, pred)
        m = metric(**output)

        print(f"BETA::{beta:.2f}")
        print(m)
