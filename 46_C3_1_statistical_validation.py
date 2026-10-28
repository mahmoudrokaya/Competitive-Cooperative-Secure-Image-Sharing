#!/usr/bin/env python3
"""C3.1: validate full development grid with image-level paired inference.
No access to raw images or held-out datasets. Selection must be frozen from train.
"""
import argparse, json, hashlib
from pathlib import Path
import numpy as np
import pandas as pd

def holm(p):
    p=np.asarray(p,float); n=len(p); order=np.argsort(p); adjusted=np.empty(n); running=0.
    for k,i in enumerate(order):
        running=max(running,(n-k)*p[i]); adjusted[i]=min(1.,running)
    return adjusted

def infer(x, rng, boot, perms):
    x=np.asarray(x,float); n=len(x); mean=float(x.mean())
    if np.all(x==0): return mean,0.,0.,1.,0
    means=np.empty(boot)
    for i in range(boot):means[i]=x[rng.integers(0,n,n)].mean()
    lo,hi=np.quantile(means,[.025,.975])
    extreme=0
    for i in range(perms):
        signs=rng.choice(np.array([-1.,1.]),size=n)
        extreme += abs(float(np.mean(x*signs)))>=abs(mean)-1e-12
    return mean,float(lo),float(hi),(extreme+1)/(perms+1),int(np.sum(x!=0))

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input',type=Path,required=True,help='C3.1 full-grid results folder')
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--bootstrap',type=int,default=3000)
    ap.add_argument('--permutations',type=int,default=10000)
    ap.add_argument('--seed',type=int,default=4601)
    ap.add_argument('--allow-partial',action='store_true',help='Development/debug only: bypass 200/100 partition count checks')
    a=ap.parse_args()
    if min(a.bootstrap,a.permutations)<1:ap.error('bootstrap and permutations must be positive')
    a.out.mkdir(parents=True,exist_ok=True)
    files={key:a.input/filename for key,filename in {
      'manifest':'C3_00_manifest.csv','candidates':'C3_01_candidates.csv',
      'runs':'C3_02_runs.csv','selected':'C3_04_train_selected.csv',
      'comparison':'C3_05_validation_comparison.csv','methodology':'C3_06_methodology.json'}.items()}
    for key,path in files.items():
        if not path.is_file():raise FileNotFoundError(f'Missing {key}: {path}')
    manifest=pd.read_csv(files['manifest']); candidates=pd.read_csv(files['candidates'])
    runs=pd.read_csv(files['runs']); selected=pd.read_csv(files['selected'])
    meta=json.loads(files['methodology'].read_text(encoding='utf-8-sig'))
    required=['split','sha256','scenario','candidate_id','repeat','jobs','successes','wire_ratio','mean_censored_ms',
              'capacity_violations','ownership_conflicts','reservation_leaks','exposure_violations','committed','released']
    missing=set(required)-set(runs.columns)
    if missing:raise ValueError(f'Missing run columns: {sorted(missing)}')
    counts=manifest.groupby('split')['sha256'].nunique().to_dict()
    if not a.allow_partial and (counts.get('train')!=200 or counts.get('val')!=100):
        raise ValueError(f'Full development requires train=200,val=100; got {counts}. Rerun C3 with --train-images 0 --val-images 0')
    if manifest['sha256'].duplicated().any():raise ValueError('Duplicate image hash in manifest')
    if set(runs['sha256'])!=set(manifest['sha256']):raise ValueError('Run image hashes differ from manifest')
    if not set(runs['split']).issubset({'train','val'}):raise ValueError('Unexpected split in runs')
    if set(runs['candidate_id'])!=set(candidates['candidate_id']):raise ValueError('Candidate mismatch')
    if selected['scenario'].duplicated().any():raise ValueError('Duplicate selected scenario')
    scenarios=sorted(runs['scenario'].unique()); cids=sorted(candidates['candidate_id'].unique()); reps=sorted(runs['repeat'].unique())
    if len(reps)!=int(meta['repeats']):raise ValueError('Unexpected repeats count')
    if set(selected['scenario'])!=set(scenarios):raise ValueError('Selected scenario mismatch')
    expected=len(manifest)*len(scenarios)*len(cids)*len(reps)
    keys=['split','sha256','scenario','candidate_id','repeat']
    if len(runs)!=expected or runs.duplicated(keys).any():raise ValueError(f'Incomplete or duplicate grid: {len(runs)} rows vs expected {expected}')
    if not (runs['jobs']>0).all():raise ValueError('Invalid job counts')
    if ((runs['successes']<0)|(runs['successes']>runs['jobs'])).any():raise ValueError('Invalid success counts')
    if ((runs['committed']!=runs['released']) | (runs[['capacity_violations','ownership_conflicts','reservation_leaks','exposure_violations']]!=0).any(axis=1)).any():
        raise ValueError('Resource integrity violations detected')
    # Recompute selected configuration solely from training observations.
    weights=meta['weights']; constraints=meta['constraints']
    train=runs[runs.split=='train'].groupby(['scenario','candidate_id'],as_index=False).agg(
        successes=('successes','sum'),jobs=('jobs','sum'),wire=('wire_ratio','mean'),ms=('mean_censored_ms','mean'))
    train['success']=train.successes/train.jobs
    train['feasible']=(train.success>=constraints['min_success'])&(train.wire<=constraints['max_wire'])&(train.ms<=constraints['max_time_ms'])
    train['utility']=(weights['reliability']*train.success-weights['wire']*train.wire/constraints['max_wire']-
                      weights['censored_time']*train.ms/constraints['max_time_ms'])
    audit=[]
    for scenario in scenarios:
        pool=train[(train.scenario==scenario)&train.feasible].copy()
        if pool.empty:raise ValueError(f'No feasible candidates in {scenario}')
        pool=pool.sort_values(['utility','success','wire','ms','candidate_id'],ascending=[False,False,True,True,True])
        expected_cid=str(pool.iloc[0]['candidate_id'])
        actual_cid=str(selected.loc[selected.scenario==scenario,'candidate_id'].iloc[0])
        if expected_cid!=actual_cid:raise ValueError(f'Selection mismatch for {scenario}: training recomputation {expected_cid}, supplied {actual_cid}')
        audit.append({'scenario':scenario,'recomputed_selected':expected_cid,'matches_saved_selection':True,'feasible_candidates':len(pool)})
    baseline=candidates[(candidates.method=='AES128_GCM_PSK')&(candidates['mode']=='static')&(candidates.policy=='fec_arq')]
    if len(baseline)!=1:raise ValueError('Fixed baseline AES-GCM/static/fec_arq missing or duplicated')
    baseline_id=str(baseline.iloc[0].candidate_id)
    val=runs[runs.split=='val'].copy()
    # Each image is one statistical sampling unit; average its repeats. Jobs may vary: use total successes/jobs per image.
    image=val.groupby(['scenario','candidate_id','sha256'],as_index=False).agg(
        successes=('successes','sum'),jobs=('jobs','sum'),wire=('wire_ratio','mean'),ms=('mean_censored_ms','mean'))
    image['success']=image.successes/image.jobs
    rng=np.random.default_rng(a.seed)
    results=[]; diffs=[]
    metrics=[('success','pp',100.),('wire','ratio',1.),('ms','ms',1.)]
    for scenario in scenarios:
        chosen_id=str(selected.loc[selected.scenario==scenario,'candidate_id'].iloc[0])
        sub=image[image.scenario==scenario]
        chosen=sub[sub.candidate_id==chosen_id].set_index('sha256')
        base=sub[sub.candidate_id==baseline_id].set_index('sha256')
        if set(chosen.index)!=set(base.index) or len(chosen)!=counts['val']:
            raise ValueError(f'Unpaired/incomplete validation images in {scenario}')
        chosen=chosen.sort_index();base=base.loc[chosen.index]
        for metric,unit,scale in metrics:
            delta=(chosen[metric]-base[metric])*scale
            mean,lo,hi,p,nonzero=infer(delta.to_numpy(),rng,a.bootstrap,a.permutations)
            results.append({'scenario':scenario,'selected_id':chosen_id,'baseline_id':baseline_id,'metric':metric,
                            'unit':unit,'validation_images':len(delta),'selected_mean':float(chosen[metric].mean()*scale),
                            'baseline_mean':float(base[metric].mean()*scale),'delta':mean,'ci95_low':lo,'ci95_high':hi,
                            'p_raw':p,'nonzero_image_differences':nonzero})
            diffs.extend({'scenario':scenario,'sha256':sha,'metric':metric,'delta':float(d)} for sha,d in delta.items())
    result=pd.DataFrame(results)
    # Prespecified family: all 3 metrics x all evaluated scenarios.
    result['p_holm']=holm(result.p_raw.to_numpy())
    result['significant_holm_0_05']=result.p_holm<.05
    pd.DataFrame(audit).to_csv(a.out/'C31_00_selection_audit.csv',index=False)
    result.to_csv(a.out/'C31_01_paired_validation_inference.csv',index=False)
    pd.DataFrame(diffs).to_csv(a.out/'C31_02_image_differences.csv',index=False)
    integrity={'status':'PASS','manifest_counts':counts,'candidate_count':len(cids),'scenario_count':len(scenarios),
               'repeat_count':len(reps),'observed_batches':len(runs),'expected_batches':expected,
               'baseline_id':baseline_id,'selected_verified_from_train_only':True,'heldout_test_images_used':meta.get('heldout_test_images_used'),
               'external_images_used':meta.get('external_images_used'),'note':'Counts and manifest labels are audited; original image bytes are not independently rehashed here.'}
    if integrity['heldout_test_images_used']!=0 or integrity['external_images_used']!=0:raise ValueError('Methodology reports test/external use')
    (a.out/'C31_03_integrity.json').write_text(json.dumps(integrity,indent=2),encoding='utf-8')
    methodology={'seed':a.seed,'bootstrap':a.bootstrap,'sign_flip_permutations':a.permutations,
      'sampling_unit':'unique image SHA256; repeat results aggregated per image',
      'confidence_intervals':'paired image bootstrap percentile, 95%',
      'test':'paired sign-flip Monte Carlo two-sided; p=(extreme+1)/(permutations+1)',
      'multiplicity':'Holm familywise across 3 metrics times number of scenarios',
      'contrast':'train-selected scenario-specific candidate versus fixed AES-GCM/static/FEC+ARQ',
      'success_unit':'percentage points; image-level successes divided by image-level jobs',
      'interpretation':'validation simulation; not held-out final test; no HHO/J1-J6; policy loss traces may differ',
      'source_metadata':str(files['methodology'])}
    (a.out/'C31_04_methodology.json').write_text(json.dumps(methodology,indent=2),encoding='utf-8')
    print(json.dumps({'status':'PASS','rows':len(runs),'selected':audit,'output':str(a.out)},indent=2))

if __name__=='__main__':main()
