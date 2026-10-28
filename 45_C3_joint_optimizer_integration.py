#!/usr/bin/env python3
"""C3: development-only constrained joint configuration selection over frozen A3.1 simulator.
This is a finite-grid optimizer, NOT HHO and NOT a validated J1-J6 implementation.
No test/external image reads. The A3.1 simulator and transport are unmodified.
"""
import argparse,csv,hashlib,json,statistics,sys,platform,itertools,importlib.util
from collections import defaultdict
from pathlib import Path
from PIL import Image

HERE=Path(__file__).resolve().parent

def load(name):
 spec=importlib.util.spec_from_file_location('c3_'+name.split('_')[0],HERE/name)
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
 return h.hexdigest()

def save_csv(path,rows,fields=None):
 fields=fields or (list(rows[0]) if rows else ['status'])
 with path.open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

def pareto(rows):
 """Maximize success; minimize wire and censored time, within one scenario."""
 for r in rows:
  r['pareto']=int(not any(
   (q['success_rate']>=r['success_rate'] and q['wire_ratio']<=r['wire_ratio'] and q['censored_ms']<=r['censored_ms']) and
   (q['success_rate']>r['success_rate'] or q['wire_ratio']<r['wire_ratio'] or q['censored_ms']<r['censored_ms'])
   for q in rows if q is not r))

def aggregate(rows):
 out=[]
 groups=defaultdict(list)
 for r in rows:groups[(r['split'],r['scenario'],r['candidate_id'])].append(r)
 for (split,scenario,cid),v in sorted(groups.items()):
  j=sum(x['jobs'] for x in v)
  out.append(dict(split=split,scenario=scenario,candidate_id=cid,batches=len(v),images=len({x['sha256'] for x in v}),jobs=j,
   success_rate=sum(x['successes'] for x in v)/j,wire_ratio=statistics.mean(x['wire_ratio'] for x in v),
   censored_ms=statistics.mean(x['mean_censored_ms'] for x in v),
   capacity_violations=sum(x['capacity_violations'] for x in v),ownership_conflicts=sum(x['ownership_conflicts'] for x in v),
   reservation_leaks=sum(x['reservation_leaks'] for x in v),exposure_violations=sum(x['exposure_violations'] for x in v)))
 return out

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--data',type=Path,default=Path(r'D:\48\481\New Papers\Progressive_HHO_Cryptography\Data'))
 p.add_argument('--out',type=Path,default=Path('Stage_C3'))
 p.add_argument('--train-images',type=int,default=2,help='0 = all 200 train images')
 p.add_argument('--val-images',type=int,default=2,help='0 = all 100 val images')
 p.add_argument('--repeats',type=int,default=1);p.add_argument('--jobs',type=int,default=4)
 p.add_argument('--seed',type=int,default=4501)
 p.add_argument('--scenarios',nargs='+',default=['iid_0.10','burst_0.20','path_failure'])
 p.add_argument('--methods',nargs='+',default=['AES128_GCM_PSK','AESGCM_XOR_Erasure_2of3'])
 p.add_argument('--modes',nargs='+',default=['static','bidding_ownership_assist','bidding_ownership_reassign','full'])
 p.add_argument('--policies',nargs='+',default=['arq','fec_arq'])
 p.add_argument('--max-wire',type=float,default=2.5)
 p.add_argument('--max-time-ms',type=float,default=3000.)
 p.add_argument('--min-success',type=float,default=0.)
 p.add_argument('--weight-reliability',type=float,default=.65)
 p.add_argument('--weight-wire',type=float,default=.15)
 p.add_argument('--weight-time',type=float,default=.20)
 p.add_argument('--capacity',type=int,default=4);p.add_argument('--contention-capacity',type=int,default=2)
 p.add_argument('--mtu',type=int,default=1000);p.add_argument('--header-bytes',type=int,default=20)
 p.add_argument('--fec-group',type=int,default=4);p.add_argument('--max-retries',type=int,default=3)
 p.add_argument('--failed-path',type=int,default=1);p.add_argument('--failure-at-ms',type=float,default=180.)
 p.add_argument('--burst-persist',type=float,default=.85);p.add_argument('--timeout-ms',type=float,default=3000.)
 p.add_argument('--detection-ms',type=float,default=80.);p.add_argument('--queue-penalty-ms',type=float,default=20.)
 p.add_argument('--duplicate-path-penalty-ms',type=float,default=10.)
 p.add_argument('--max-interventions-per-job',type=int,default=3);p.add_argument('--max-events',type=int,default=100000)
 a=p.parse_args()
 if min(a.repeats,a.jobs,a.capacity,a.contention_capacity,a.max_events)<1 or min(a.train_images,a.val_images)<0:p.error('Invalid counts')
 if min(a.weight_reliability,a.weight_wire,a.weight_time)<0 or sum((a.weight_reliability,a.weight_wire,a.weight_time))<=0:p.error('Weights must be nonnegative with positive sum')
 a.path_rates=(20.,10.,15.);a.path_delays=(10.,40.,25.)
 sim=load('40_A3_1_capacity_aware.py');s33=load('33_expanded_baseline.py');s34=load('34_multipath_loss_simulator.py');s35=load('35_packet_recovery.py')
 for sc in a.scenarios:
  if sc not in sim.SCENARIOS:p.error('Unsupported scenario '+sc)
 for m in a.methods:
  if m not in sim.METHODS:p.error('Unsupported method '+m)
 for m in a.modes:
  if m not in sim.MODES:p.error('Unsupported mode '+m)
 for m in a.policies:
  if m not in ('none','fec','arq','fec_arq'):p.error('Unsupported policy '+m)
 candidates=[dict(candidate_id=f'C{i:03}',method=method,mode=mode,policy=policy)
             for i,(method,mode,policy) in enumerate(itertools.product(a.methods,a.modes,a.policies),1)]
 a.out.mkdir(parents=True,exist_ok=True)
 entries=[];seen=set()
 for split,limit in [('train',a.train_images),('val',a.val_images)]:
  folder=a.data/'BSR'/'BSDS500'/'data'/'images'/split
  if not folder.is_dir():raise FileNotFoundError(folder)
  paths=sorted(folder.glob('*.jpg'))
  if limit:paths=paths[:limit]
  if not paths:raise ValueError('No images in '+str(folder))
  for f in paths:
   digest=sha(f)
   if digest in seen:raise RuntimeError('Duplicate SHA across development splits: '+f.name)
   seen.add(digest)
   with Image.open(f) as im:
    w,h=im.size;mode=im.mode;im.verify()
   entries.append(dict(split=split,image=f.name,relative_path=f.relative_to(a.data).as_posix(),sha256=digest,width=w,height=h,mode=mode))
 save_csv(a.out/'C3_00_manifest.csv',entries)
 save_csv(a.out/'C3_01_candidates.csv',candidates)
 rows=[]
 for ix,e in enumerate(entries,1):
  f=a.data/e['relative_path']
  if sha(f)!=e['sha256']:raise RuntimeError('Source image changed: '+str(f))
  with Image.open(f) as im:rgb=im.convert('RGB').tobytes()
  for sc in a.scenarios:
   for rep in range(a.repeats):
    for c in candidates:
     a.policy=c['policy']
     # Policy is part of the comparison; stable A3.1 seeds otherwise held fixed.
     r=sim.execute(e,rgb,c['method'],c['mode'],sc,rep,a,s33,s34,s35,[])
     r.update(candidate_id=c['candidate_id'],policy=c['policy'])
     if r['committed']!=r['released'] or r['capacity_violations'] or r['reservation_leaks'] or r['ownership_conflicts'] or r['exposure_violations']:
      raise RuntimeError('Simulator integrity violation: '+str((e['image'],sc,c['candidate_id'])))
     rows.append(r)
  print(f'{ix}/{len(entries)} {e["split"]}/{e["image"]} complete',flush=True)
 save_csv(a.out/'C3_02_runs.csv',rows)
 stats=aggregate(rows)
 choices=[]
 for sc in a.scenarios:
  pool=[r for r in stats if r['split']=='train' and r['scenario']==sc]
  if len(pool)!=len(candidates):raise RuntimeError('Incomplete training grid for '+sc)
  pareto(pool)
  for r in pool:
   r['feasible']=int(r['wire_ratio']<=a.max_wire and r['censored_ms']<=a.max_time_ms and r['success_rate']>=a.min_success)
   # Explicit dimensionless scalarization with fixed scales, not data-fitted normalization.
   r['utility']=a.weight_reliability*r['success_rate']-a.weight_wire*(r['wire_ratio']/a.max_wire)-a.weight_time*(r['censored_ms']/a.max_time_ms)
  feasible=[r for r in pool if r['feasible']]
  if not feasible:raise RuntimeError(f'No feasible configuration for {sc}; widen constraints. No test data accessed.')
  winner=max(feasible,key=lambda r:(r['utility'],r['success_rate'],-r['wire_ratio'],-r['censored_ms'],-int(r['candidate_id'][1:])))
  c=next(c for c in candidates if c['candidate_id']==winner['candidate_id'])
  choices.append(dict(scenario=sc,**c,train_utility=winner['utility'],train_success=winner['success_rate'],train_wire=winner['wire_ratio'],train_ms=winner['censored_ms'],pareto=winner['pareto']))
 # Val evaluation is performed only after selection. All candidates were simulated on val
 # for reproducibility, but ONLY the training split determines choices.
 for r in stats:
  if r['split']=='val':r['pareto']='';r['feasible']='';r['utility']=''
 save_csv(a.out/'C3_03_aggregate.csv',stats)
 save_csv(a.out/'C3_04_train_selected.csv',choices)
 evaluation=[]
 for choice in choices:
  sc=choice['scenario']; cid=choice['candidate_id']
  chosen=next(r for r in stats if r['split']=='val' and r['scenario']==sc and r['candidate_id']==cid)
  # Fixed reference baseline: AES-GCM, static, FEC+ARQ if present; otherwise first candidate.
  base=next((c for c in candidates if c['method']=='AES128_GCM_PSK' and c['mode']=='static' and c['policy']=='fec_arq'),candidates[0])
  ref=next(r for r in stats if r['split']=='val' and r['scenario']==sc and r['candidate_id']==base['candidate_id'])
  evaluation.append(dict(scenario=sc,selected_id=cid,selected_method=choice['method'],selected_mode=choice['mode'],selected_policy=choice['policy'],baseline_id=base['candidate_id'],validation_images=chosen['images'],validation_jobs=chosen['jobs'],selected_success=chosen['success_rate'],baseline_success=ref['success_rate'],delta_success_pp=100*(chosen['success_rate']-ref['success_rate']),selected_wire=chosen['wire_ratio'],baseline_wire=ref['wire_ratio'],delta_wire=chosen['wire_ratio']-ref['wire_ratio'],selected_ms=chosen['censored_ms'],baseline_ms=ref['censored_ms'],delta_ms=chosen['censored_ms']-ref['censored_ms']))
 save_csv(a.out/'C3_05_validation_comparison.csv',evaluation)
 metadata=dict(stage='C3 finite-grid constrained joint configuration selection (integration prototype)',seed=a.seed,train_images=sum(e['split']=='train' for e in entries),validation_images=sum(e['split']=='val' for e in entries),heldout_test_images_used=0,external_images_used=0,selection_split='train only',validation_split='val (reported only)',candidate_count=len(candidates),scenarios=a.scenarios,repeats=a.repeats,jobs=a.jobs,weights={'reliability':a.weight_reliability,'wire':a.weight_wire,'censored_time':a.weight_time},constraints={'min_success':a.min_success,'max_wire':a.max_wire,'max_time_ms':a.max_time_ms},simulator_code_sha256=sha(HERE/'40_A3_1_capacity_aware.py'),python=sys.version,platform=platform.platform(),limitations=['Finite-grid selection over method, organizational mode and packet recovery policy; NOT HHO and NOT a J1-J6 optimizer','A3.1 fixed path selection, capacity and threshold logic; not full joint allocation','Simulated packet losses, idealized queueing, abstract ownership and organizational interventions','Validation candidates are computed for audit, but not used for selection','Success, latency and wire overhead only; no independently measured security objective','No held-out test or external data used','Finite validation sample may be unstable','Packet policy changes the simulated erasure sequence in A3.1, so comparisons are not strictly common-random-number matched across policies'])
 (a.out/'C3_06_methodology.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
 print(json.dumps({'status':'COMPLETE','output':str(a.out),'train_images':metadata['train_images'],'validation_images':metadata['validation_images'],'batches':len(rows),'selected':choices},indent=2))

if __name__=='__main__':main()
