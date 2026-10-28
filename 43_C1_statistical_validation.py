"""Stage C1: paired image-clustered inference for frozen B1/B2 runs.
Dependencies: numpy, pandas, scipy. Run: python 43_C1_statistical_validation.py --input /path --out /path
"""
import argparse, json, hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import ttest_1samp, t

METHODS=['AES128_GCM_PSK','AESGCM_XOR_Erasure_2of3']
CONTRASTS=[('full','static'),('bidding','static'),('bidding_ownership','bidding'),('bidding_ownership_assist','bidding_ownership'),('bidding_ownership_reassign','bidding_ownership'),('full','bidding_ownership_assist'),('full','bidding_ownership_reassign'),('full','bidding_ownership')]
METRICS=['success_rate','wire_ratio','mean_censored_ms']
KEY=['sha256','scenario','repeat','method']

def holm(p):
    a=np.array(p,dtype=float); o=np.argsort(a); r=np.empty(len(a)); m=len(a); high=0.
    for k,i in enumerate(o):
        high=max(high,min(1.,float(a[i])*(m-k)));r[i]=high
    return r

def infer(x, rng, boots):
    x=np.asarray(x,dtype=float);n=len(x);mu=x.mean();sd=x.std(ddof=1) if n>1 else np.nan
    if n<2:return mu,np.nan,np.nan,np.nan,np.nan
    # percentile cluster bootstrap over images
    b=np.empty(boots)
    for start in range(0,boots,250):
        size=min(250,boots-start)
        idx=rng.integers(0,n,size=(size,n));b[start:start+size]=x[idx].mean(axis=1)
    lo,hi=np.quantile(b,[.025,.975]);p=ttest_1samp(x,0).pvalue if sd>1e-13 else (1. if abs(mu)<1e-13 else 0.)
    return mu,lo,hi,float(p),sd

def resolve_input(folder, dataset, suffix):
    """Accept Experiment_B/B1/B1_... or a flat folder of B1/B2 files."""
    filename = f'{dataset}_{suffix}'
    candidates = [folder / dataset / filename, folder / filename]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    searched = '\n'.join('  ' + str(p) for p in candidates)
    raise FileNotFoundError(
        f'Missing {filename}. Stage C1 reads EXPERIMENT RESULTS, not raw images. '
        f'Checked:\n{searched}\n'
        'Pass --input the Experiment_B results folder containing B1 and B2.'
    )

def run(folder,out,boots,seed):
    out.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(seed)
    records=[];quality=[];descript=[];raw={}
    for dataset in ['B1','B2']:
        path=resolve_input(folder,dataset,'01_runs.csv');d=pd.read_csv(path)
        meta=json.loads(resolve_input(folder,dataset,'03_metadata.json').read_text(encoding='utf-8'))
        manifest=pd.read_csv(resolve_input(folder,dataset,'00_manifest.csv'))
        assert meta['complete'] and meta['completed_batches']==len(d)
        assert len(d)==len(manifest)*2*6*7*3
        assert d['sha256'].nunique()==len(manifest)
        assert d[KEY+['mode']].duplicated().sum()==0
        assert (d['jobs']==4).all() and (d['successes']<=d['jobs']).all()
        assert (d['committed']==d['released']).all()
        assert not d[['capacity_violations','reservation_leaks','exposure_violations']].to_numpy().any()
        quality.append(dict(dataset=dataset,images=d.sha256.nunique(),batches=len(d),jobs=int(d.jobs.sum()),complete=True,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),blocked=int(d.blocked_interventions.sum())))
        raw[dataset]=d
        for method in METHODS:
            z=d[d.method==method]
            for mode,g in z.groupby('mode'):
                descript.append(dict(dataset=dataset,method=method,mode=mode,images=g.sha256.nunique(),jobs=int(g.jobs.sum()),success_rate=g.successes.sum()/g.jobs.sum(),wire_ratio=g.wire_ratio.mean(),mean_censored_ms=g.mean_censored_ms.mean(),queued=int(g.queued_requests.sum())))
            for a,b in CONTRASTS:
                za=z[z['mode']==a].set_index(KEY).sort_index()
                zb=z[z['mode']==b].set_index(KEY).sort_index()
                assert za.index.equals(zb.index),f'unpaired {dataset} {method} {a} {b}'
                for metric in METRICS:
                    delta=(za[metric]-zb[metric]).rename('difference').reset_index()
                    # Average repeated/scenario measurements within each image before inference
                    by_image=delta.groupby('sha256')['difference'].mean().to_numpy()
                    mu,lo,hi,p,sd=infer(by_image,rng,boots)
                    records.append(dict(dataset=dataset,method=method,contrast=f'{a} - {b}',metric=metric,n_images=len(by_image),effect=mu,ci95_low=lo,ci95_high=hi,p_unadjusted=p,image_sd=sd,bootstrap_reps=boots))
    if set(raw['B1'].sha256)&set(raw['B2'].sha256):raise ValueError('Image SHA-256 overlap across datasets')
    r=pd.DataFrame(records)
    # Adjust family of all 8 contrasts for each (dataset, method, metric)
    r['p_holm']=np.nan
    for _,indices in r.groupby(['dataset','method','metric']).groups.items():r.loc[indices,'p_holm']=holm(r.loc[indices,'p_unadjusted'])
    r['significant_0_05']=r.p_holm<.05
    r.to_csv(out/'C1_01_paired_inference.csv',index=False)
    pd.DataFrame(descript).to_csv(out/'C1_00_descriptive.csv',index=False)
    pd.DataFrame(quality).to_csv(out/'C1_02_quality_checks.csv',index=False)
    # Cross-dataset unpaired comparison of effects; resample images independently in each dataset
    cross=[]
    for method in METHODS:
      for a,b in CONTRASTS:
        for metric in METRICS:
          arr=[]
          for dataset in ['B1','B2']:
            z=raw[dataset];z=z[z.method==method]
            za=z[z['mode']==a].set_index(KEY).sort_index();zb=z[z['mode']==b].set_index(KEY).sort_index()
            x=(za[metric]-zb[metric]).rename('d').reset_index().groupby('sha256')['d'].mean().to_numpy()
            arr.append(x)
          x,y=arr; diff=y.mean()-x.mean(); v=np.empty(boots)
          for start in range(0,boots,250):
            sz=min(250,boots-start)
            v[start:start+sz]=y[rng.integers(len(y),size=(sz,len(y)))].mean(axis=1)-x[rng.integers(len(x),size=(sz,len(x)))].mean(axis=1)
          lo,hi=np.quantile(v,[.025,.975])
          cross.append(dict(method=method,contrast=f'{a} - {b}',metric=metric,B1_effect=x.mean(),B2_effect=y.mean(),B2_minus_B1=diff,ci95_low=lo,ci95_high=hi))
    pd.DataFrame(cross).to_csv(out/'C1_03_cross_dataset_effects.csv',index=False)
    cfg={'method':'paired differences per image, averaging over 7 scenarios x 3 repeats; image-cluster bootstrap percentile 95% CI; image-level two-sided one-sample t test; Holm correction within each dataset/method/metric over 8 prespecified contrasts','bootstrap_repetitions':boots,'seed':seed,'independent_units':'image','cross_dataset':'unpaired bootstrap difference in image-mean effects; exploratory; dataset composition differs','caveats':['Simulated jobs are not independent observations','Timeout-censored completion time includes failures','Fixed 7 scenario distribution, not real-world prevalence','B2 has heterogeneous image dimensions and color modes','No formal evidence of independent ownership protocol or full J1-J6 optimization','Zero variance yields p=1 for exactly zero differences','P-values are approximate for image-level means; bootstrap CI is primary uncertainty estimate']}
    (out/'C1_04_methodology.json').write_text(json.dumps(cfg,indent=2),encoding='utf-8')
    print('PASS:',quality,'\nSaved C1 files to',out)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,default=Path('.'));p.add_argument('--out',type=Path,default=Path('C1_results'));p.add_argument('--bootstrap',type=int,default=3000);p.add_argument('--seed',type=int,default=4301)
    a=p.parse_args();run(a.input,a.out,a.bootstrap,a.seed)
