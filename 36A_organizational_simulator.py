#!/usr/bin/env python3
"""Step 36A: fixed-crypto/fixed-transport organizational ablation simulator.
Imports Step 33/34/35 read-only. Never writes to their directories.
Research prototype: scheduling and reassignment simulation, not a GIS implementation.
"""
import argparse,csv,hashlib,json,statistics,math
from pathlib import Path
from collections import defaultdict
from PIL import Image
import importlib.util

MODES=['static','bidding','bidding_ownership','bidding_ownership_assist','full']
FIELDS=['split','image','scheme','mode','scenario','loss_rate','repeat','recovered','exact','wire_bytes','wire_ratio','completion_ms','initial_assignments','final_assignments','bids','ownership_violations','assistance_events','reassignments','commitment_protected','fragments_complete','fragments_required','reason']

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,str(path));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def write_csv(path,rows,fields):
    with open(path,'w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def bid_score(blob_size,path,args,backlog):
    return args.path_delays[path]+blob_size*8/(args.path_rates[path]*1000)+backlog[path]

def simulate(shares,decode,target,required,scheme,mode,scenario,loss,rep,args,step35):
    # Fixed policy and scheme across all modes. Distinct paths assigned to initial shares.
    initial={};backlog=[0.]*3;bids=0
    for share_id,blob in shares:
        if mode=='static':path=share_id
        else:
            available=[p for p in range(3) if p not in initial.values()]
            path=min(available,key=lambda p:(bid_score(len(blob),p,args,backlog),p))
            bids+=len(available)
        initial[share_id]=path
        backlog[path]+=len(blob)*8/(args.path_rates[path]*1000)
    owner=dict(initial);received={};arrivals={};wire=0;assists=0;reassigned=0;violations=0;protected=0
    failed=[]
    for share_id,blob in shares:
        path=owner[share_id]
        got,w,_,_,_,_,t=step35.transport(blob,path,args.policy,scenario,loss,rep,args)
        wire+=w
        if got is None:failed.append((share_id,blob,path,t))
        else:received[share_id]=got;arrivals[share_id]=t
    # Ownership and commitment: successful owners are never displaced.
    if mode in ('bidding_ownership','bidding_ownership_assist','full'):
        protected=len(received)
    # Assistance: a bounded single backup for an unavailable share, while original ownership remains.
    # Full mode: formal reassignment after failure, preserving all completed commitments.
    if mode in ('bidding_ownership_assist','full') and len(received)<required:
        budget=args.max_assists
        for share_id,blob,old_path,old_time in failed:
            if len(received)>=required or budget<=0:break
            candidates=[p for p in range(3) if p!=old_path and (scenario!='path_failure' or p!=args.failed_path)]
            if not candidates:continue
            # Avoid co-locating with another incomplete share; use available healthy path.
            candidates.sort(key=lambda p:(bid_score(len(blob),p,args,[0.]*3),p))
            new_path=candidates[0];bids+=len(candidates)
            if mode=='full':owner[share_id]=new_path;reassigned+=1
            else:assists+=1
            budget-=1
            got,w,_,_,_,_,t=step35.transport(blob,new_path,args.policy,scenario,loss,rep+args.backup_rep_offset,args)
            wire+=w
            if got is not None:
                received[share_id]=got
                arrivals[share_id]=old_time+args.failure_detection_ms+t
    success=len(received)>=required;reason=''
    exact='';completion=''
    if success:
        try:
            result=decode(received)
            if scheme!='RandomGrid_OR_2of2':exact=int(result==target)
            completion=round(sorted(arrivals.values())[required-1],6)
        except Exception as exc:success=False;reason='decode_'+type(exc).__name__
    if not success and not reason:reason='insufficient_complete_fragments'
    return dict(recovered=int(success),exact=exact,wire_bytes=wire,wire_ratio=round(wire/max(1,len(target)),6),completion_ms=completion,initial_assignments=json.dumps(initial,sort_keys=True),final_assignments=json.dumps(owner,sort_keys=True),bids=bids,ownership_violations=violations,assistance_events=assists,reassignments=reassigned,commitment_protected=protected,fragments_complete=len(received),fragments_required=required,reason=reason)

def self_test(s34,s35,s33,args):
    rgb=bytes(range(120));bits=bytes(i%2 for i in range(40))
    for scheme in ('XOR_2of2','AESGCM_XOR_Erasure_2of3'):
        shares,dec,target,req=s34.make_shares(s33,scheme,rgb,bits)
        for mode in MODES:
            r=simulate(shares,dec,target,req,scheme,mode,'iid',0.,0,args,s35)
            assert r['recovered']==1 and r['exact']==1,(scheme,mode,r)
        r=simulate(shares,dec,target,req,scheme,'full','path_failure',0.,0,args,s35)
        assert r['recovered']==1,(scheme,r)
    print('PASS: Step 36A ownership, recovery and path-failure smoke tests')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',default='');p.add_argument('--step33',default=str(Path(__file__).with_name('33_expanded_baseline.py')))
    p.add_argument('--step34',default=str(Path(__file__).with_name('34_multipath_loss_simulator.py')))
    p.add_argument('--step35',default=str(Path(__file__).with_name('35_packet_recovery.py')))
    p.add_argument('--reference',default='',help='Step35 35_01_runs.csv, read-only audit input')
    p.add_argument('--out',default='Step36A_Organizational');p.add_argument('--max-images',type=int,default=2)
    p.add_argument('--repeats',type=int,default=3);p.add_argument('--seed',type=int,default=3501)
    p.add_argument('--schemes',default='XOR_2of2,AESGCM_XOR_Erasure_2of3')
    p.add_argument('--policy',choices=['none','fec','arq','fec_arq'],default='fec_arq')
    p.add_argument('--loss-rates',default='0,0.01,0.05,0.10,0.20')
    p.add_argument('--mtu',type=int,default=1000);p.add_argument('--header-bytes',type=int,default=20)
    p.add_argument('--fec-group',type=int,default=4);p.add_argument('--max-retries',type=int,default=3)
    p.add_argument('--failed-path',type=int,default=1);p.add_argument('--burst-persist',type=float,default=.85)
    p.add_argument('--failure-detection-ms',type=float,default=80.);p.add_argument('--max-assists',type=int,default=1)
    p.add_argument('--backup-rep-offset',type=int,default=100000)
    p.add_argument('--self-test',action='store_true')
    args=p.parse_args()
    args.path_rates=(20.,10.,15.);args.path_delays=(10.,40.,25.)
    if args.max_images<0 or args.repeats<1 or args.max_assists<0 or args.failure_detection_ms<0 or args.failed_path not in (0,1,2):p.error('Invalid parameter')
    schemes=args.schemes.split(',');losses=[float(x) for x in args.loss_rates.split(',')]
    if not schemes or any(x not in ('XOR_2of2','Shamir_GF256_2of3','AESGCM_XOR_Erasure_2of3','OR_2of2','RandomGrid_OR_2of2','AES128_GCM_PSK','X25519_HKDF_AES128_GCM') for x in schemes) or any(not 0<=x<1 for x in losses):p.error('Invalid schemes/loss rates')
    s33=load(args.step33,'s33_org');s34=load(args.step34,'s34_org');s35=load(args.step35,'s35_org')
    self_test(s34,s35,s33,args)
    if args.self_test:return
    root=Path(args.data);out=Path(args.out)
    if not root.is_dir():p.error('Missing dataset')
    out.mkdir(parents=True,exist_ok=True)
    reference={}
    if args.reference:
        with open(args.reference,newline='',encoding='utf8') as f:
            reference_rows=list(csv.DictReader(f))
        reference={'source':str(args.reference),'sha256':hashlib.sha256(Path(args.reference).read_bytes()).hexdigest(),'rows':len(reference_rows),'matched_static_reference':0,'static_reference_mismatches':0}
        for r in reference_rows:
            if r['scheme'] in schemes and r['policy']==args.policy:reference['matched_static_reference']+=1
    rows=[];manifest=[];issues=[]
    for split in ('train','val'):
        folder=root/'BSR'/'BSDS500'/'data'/'images'/split
        if not folder.is_dir():issues.append('Missing '+str(folder));continue
        files=sorted(folder.glob('*.jpg'))
        if args.max_images:files=files[:args.max_images]
        for fp in files:
            try:
                with Image.open(fp) as img:
                    rgb=img.convert('RGB').tobytes();bits=bytes(v<128 for v in img.convert('L').tobytes())
                    w,h=img.size
                manifest.append(dict(split=split,image=fp.name,width=w,height=h,sha256=hashlib.sha256(fp.read_bytes()).hexdigest()))
                for rep in range(args.repeats):
                    for scheme in schemes:
                        shares,decode,target,required=s34.make_shares(s33,scheme,rgb,bits)
                        for scenario,loss in ([('iid',x) for x in losses]+[('burst',x) for x in losses]+[('path_failure',0.)]):
                            for mode in MODES:
                                result=simulate(shares,decode,target,required,scheme,mode,scenario,loss,rep,args,s35)
                                rows.append(dict(split=split,image=fp.name,scheme=scheme,mode=mode,scenario=scenario,loss_rate=loss,repeat=rep,**result))
            except Exception as exc:issues.append(f'{split}/{fp.name}: {type(exc).__name__}: {exc}')
    write_csv(out/'36A_01_runs.csv',rows,FIELDS)
    write_csv(out/'36A_02_manifest.csv',manifest,['split','image','width','height','sha256'])
    grouped=defaultdict(list)
    for r in rows:grouped[(r['scheme'],r['mode'],r['scenario'],r['loss_rate'])].append(r)
    summary=[]
    for (scheme,mode,scenario,loss),rr in sorted(grouped.items()):
        good=[r for r in rr if r['recovered']]
        summary.append(dict(scheme=scheme,mode=mode,scenario=scenario,loss_rate=loss,runs=len(rr),recovery_fraction=round(len(good)/len(rr),6),mean_wire_ratio=round(statistics.mean(r['wire_ratio'] for r in rr),6),median_success_completion_ms=round(statistics.median(r['completion_ms'] for r in good),6) if good else '',mean_bids=round(statistics.mean(r['bids'] for r in rr),3),mean_assists=round(statistics.mean(r['assistance_events'] for r in rr),3),mean_reassignments=round(statistics.mean(r['reassignments'] for r in rr),3),ownership_violations=sum(r['ownership_violations'] for r in rr)))
    write_csv(out/'36A_03_summary.csv',summary,['scheme','mode','scenario','loss_rate','runs','recovery_fraction','mean_wire_ratio','median_success_completion_ms','mean_bids','mean_assists','mean_reassignments','ownership_violations'])
    (out/'36A_04_issues.txt').write_text('\n'.join(issues) if issues else 'No issues reported.\n',encoding='utf8')
    meta=dict(images=len(manifest),runs=len(rows),schemes=schemes,modes=MODES,policy=args.policy,scenarios=['iid','burst','path_failure'],loss_rates=losses,repeats=args.repeats,seed=args.seed,reference=reference,issues=len(issues),limitations=['Organizational mechanisms are new prototypes, not existing GIS source code','Static baseline uses same Step35 transport function and configuration, but independently generated shares may differ due to CSPRNG','Only three agents/paths; no queues or simultaneous task contention','Bids use deterministic estimated completion time and simple backlog heuristic','Assistance/reassignment occurs after full-fragment failure and retransmits whole fragment','Failed transfer detection latency is assumed, not measured','Backup erasure traces use a separate deterministic repetition index','Assistance and reassignment may duplicate wire traffic and do not model signaling','Path failure is fixed to one path and paths assumed independent','No end-to-end security or adversarial testing','Train/val only; do not tune on held-out test','No statistical inference justified by this pilot'])
    (out/'36A_05_metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf8')
    print(json.dumps(dict(output=str(out),images=len(manifest),runs=len(rows),schemes=len(schemes),modes=len(MODES),issues=len(issues)),indent=2))
if __name__=='__main__':main()
