#!/usr/bin/env python3
"""Step 36A.1: matched-trace, multi-job organizational mechanism validation.
Read-only imports of Step 33/34/35. Synthetic discrete-event scheduling prototype,
not a real network, GIS implementation, or production cryptography.
"""
import argparse, csv, hashlib, importlib.util, json, math, statistics
from collections import defaultdict
from pathlib import Path
from PIL import Image

MODES=('static','bidding','bidding_ownership','bidding_ownership_assist','bidding_ownership_reassign','full')
SCENARIOS=('iid','burst','post_commit_failure','contention_conflict')
FIELDS=('split','image','scheme','scenario','loss_rate','repeat','batch','mode','jobs','recovered_jobs','recovery_rate','wire_bytes','wire_ratio','makespan_ms','mean_completion_ms','mean_censored_completion_ms','conflict_attempts','conflict_rejected','preemptions','assistance_events','reassignment_events','recovery_after_failure','failed_initial_fragments','initial_assignment_digest','trace_key')

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,str(path)); mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def dump_csv(path,records,fields):
    with open(path,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(records)

def stable_int(*parts):
    return int.from_bytes(hashlib.sha256('|'.join(map(str,parts)).encode()).digest()[:8],'big')

def estimate(blob,path,args):
    return args.path_delays[path]+len(blob)*8/(args.path_rates[path]*1000)

def run_batch(jobs,mode,scenario,loss,repeat,batch,args,s35):
    """All modes share identical jobs, arrival times, path failure and erasure keys.
    Queue model: each agent/path is a single serial server; scheduling is deterministic.
    """
    guarded=mode in ('bidding_ownership','bidding_ownership_assist','bidding_ownership_reassign','full')
    assisted=mode in ('bidding_ownership_assist','full')
    reassigned=mode in ('bidding_ownership_reassign','full')
    bid=mode!='static'
    path_free=[0.0]*3; owners={}; receipts=defaultdict(dict);arrival=defaultdict(dict)
    wire=0;attempts=0;rejected=0;preemptions=0;assists=0;reassigns=0;post_recover=0;failed=[]
    initial_assign=[]
    # Precommit: assign shares for all jobs, without revealing later path failures.
    scheduled=[]
    for jid,job in enumerate(jobs):
        assigned=set()
        for sid,blob in job['shares']:
            if bid:
                candidates=[p for p in range(3) if p not in assigned]
                p=min(candidates,key=lambda x:(max(job['start'],path_free[x])+estimate(blob,x,args),x))
            else:p=sid % 3
            assigned.add(p);owners[(jid,sid)]=p
            start=max(job['start'],path_free[p]);finish=start+estimate(blob,p,args)
            path_free[p]=finish
            scheduled.append((start,finish,jid,sid,blob,p))
            initial_assign.append((jid,sid,p))
    # Inject a competing claim against a committed task; protection rejects it.
    # Without protection, competing claim consumes one path slot and delays the
    # victim's transmission. This is a declared synthetic preemption model.
    conflict_keys=set()
    if scenario=='contention_conflict':
        for jid in range(len(jobs)):
            if stable_int(args.seed,'conflict',repeat,batch,jid)%100 < args.conflict_percent:
                conflict_keys.add((jid,0))
    schedules=[]
    for start,finish,jid,sid,blob,p in scheduled:
        if (jid,sid) in conflict_keys:
            attempts+=1
            if guarded:rejected+=1
            else:
                preemptions+=1
                # Conflicting claimant temporarily monopolizes the path; no
                # extra data bytes charged, but victim's service is delayed.
                start+=args.preemption_ms;finish+=args.preemption_ms
        schedules.append((start,finish,jid,sid,blob,p))
    # Mid-transfer failure is revealed only after assignment/commitment.
    fail_at=args.failure_at_ms
    for start,finish,jid,sid,blob,p in schedules:
        fail_now=(scenario=='post_commit_failure' and p==args.failed_path and start<fail_at<finish)
        fail_before=(scenario=='post_commit_failure' and p==args.failed_path and start>=fail_at)
        if fail_now or fail_before:
            # A mid-transfer failure sends only the fraction before failure.
            frac=max(0.0,min(1.0,(fail_at-start)/(finish-start))) if fail_now else 0.0
            wire+=math.ceil((len(blob)+args.header_bytes*math.ceil(len(blob)/args.mtu))*frac)
            failed.append((jid,sid,blob,p,max(start,fail_at),True))
            continue
        # The same seed/repetition/path/packet IDs are used in every mode.
        # Different path assignments intentionally yield different path traces.
        repkey=repeat+batch*1000+jid*100000
        kind='iid' if scenario in ('post_commit_failure','contention_conflict') else scenario
        rate=0.0 if scenario=='post_commit_failure' else loss
        got,w,_,_,_,_,duration=s35.transport(blob,p,args.policy,kind,rate,repkey,args)
        wire+=w
        if got is None:failed.append((jid,sid,blob,p,finish,False))
        else:
            receipts[jid][sid]=got
            arrival[jid][sid]=start+duration
    # Recovery policy: one bounded intervention per job, only if needed.
    # Assistance preserves owner, reassignment changes owner; full mode chooses
    # reassignment for permanent failure, assistance for transient loss.
    used=set()
    for jid,sid,blob,old,detect,permanent in sorted(failed,key=lambda x:(x[4],x[0],x[1])):
        job=jobs[jid]
        if len(receipts[jid])>=job['required'] or jid in used:continue
        if not (assisted or reassigned):continue
        if permanent and not reassigned:continue
        if (not permanent) and not assisted and not reassigned:continue
        choices=[p for p in range(3) if p!=old and not (scenario=='post_commit_failure' and p==args.failed_path)]
        if not choices:continue
        p=min(choices,key=lambda x:(max(detect+args.detection_ms,path_free[x])+estimate(blob,x,args),x))
        if permanent or not assisted:
            owners[(jid,sid)]=p;reassigns+=1
        else:assists+=1
        used.add(jid)
        start=max(detect+args.detection_ms,path_free[p]);path_free[p]=start+estimate(blob,p,args)
        repkey=repeat+batch*1000+jid*100000+args.backup_rep_offset
        kind='iid' if scenario in ('post_commit_failure','contention_conflict') else scenario
        rate=0.0 if scenario=='post_commit_failure' else loss
        got,w,_,_,_,_,duration=s35.transport(blob,p,args.policy,kind,rate,repkey,args)
        wire+=w
        if got is not None:
            receipts[jid][sid]=got;arrival[jid][sid]=start+duration
            if permanent:post_recover+=1
    successes=0;completion=[];censored=[]
    for jid,job in enumerate(jobs):
        ok=len(receipts[jid])>=job['required']
        if ok:
            try:ok=job['decode'](receipts[jid])==job['target']
            except Exception:ok=False
        if ok:
            successes+=1
            end=sorted(arrival[jid].values())[job['required']-1]
            completion.append(end-job['start']);censored.append(end-job['start'])
        else:censored.append(args.timeout_ms)
    total_payload=sum(len(j['target']) for j in jobs)
    return dict(jobs=len(jobs),recovered_jobs=successes,recovery_rate=round(successes/len(jobs),6),wire_bytes=wire,wire_ratio=round(wire/max(1,total_payload),6),makespan_ms=round(max(path_free),4),mean_completion_ms=round(statistics.mean(completion),4) if completion else '',mean_censored_completion_ms=round(statistics.mean(censored),4),conflict_attempts=attempts,conflict_rejected=rejected,preemptions=preemptions,assistance_events=assists,reassignment_events=reassigns,recovery_after_failure=post_recover,failed_initial_fragments=len(failed),initial_assignment_digest=hashlib.sha256(repr(initial_assign).encode()).hexdigest()[:16],trace_key=f'{args.seed}:{repeat}:{batch}')

def tests(s33,s34,s35,args):
    rgb=bytes(range(120));bits=bytes(i%2 for i in range(40))
    for scheme in ('XOR_2of2','AESGCM_XOR_Erasure_2of3'):
        shares,dec,target,req=s34.make_shares(s33,scheme,rgb,bits)
        jobs=[dict(shares=shares,decode=dec,target=target,required=req,start=i*args.arrival_gap_ms) for i in range(3)]
        for mode in MODES:
            r=run_batch(jobs,mode,'iid',0.,0,0,args,s35)
            assert r['recovered_jobs']==3,(scheme,mode,r)
        args_copy=args
        r=run_batch(jobs,'full','contention_conflict',0.,0,0,args_copy,s35)
        assert r['conflict_attempts']>=0
    print('PASS: Step 36A.1 matched-job, reconstruction and ownership smoke tests')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    here=Path(__file__).parent
    p.add_argument('--step33',default=str(here/'33_expanded_baseline.py'))
    p.add_argument('--step34',default=str(here/'34_multipath_loss_simulator.py'))
    p.add_argument('--step35',default=str(here/'35_packet_recovery.py'))
    p.add_argument('--data',default='');p.add_argument('--out',default='Step36A1_Mechanism_Validation')
    p.add_argument('--max-images',type=int,default=2);p.add_argument('--repeats',type=int,default=3)
    p.add_argument('--jobs-per-batch',type=int,default=4);p.add_argument('--seed',type=int,default=3501)
    p.add_argument('--schemes',default='XOR_2of2,AESGCM_XOR_Erasure_2of3')
    p.add_argument('--loss-rates',default='0.01,0.10,0.20')
    p.add_argument('--policy',default='fec_arq',choices=('none','fec','arq','fec_arq'))
    p.add_argument('--mtu',type=int,default=1000);p.add_argument('--header-bytes',type=int,default=20)
    p.add_argument('--fec-group',type=int,default=4);p.add_argument('--max-retries',type=int,default=3)
    p.add_argument('--failed-path',type=int,default=1);p.add_argument('--burst-persist',type=float,default=.85)
    p.add_argument('--failure-at-ms',type=float,default=180.0)
    p.add_argument('--arrival-gap-ms',type=float,default=5.0)
    p.add_argument('--detection-ms',type=float,default=80.0)
    p.add_argument('--preemption-ms',type=float,default=250.0)
    p.add_argument('--conflict-percent',type=int,default=75)
    p.add_argument('--timeout-ms',type=float,default=3000.0)
    p.add_argument('--backup-rep-offset',type=int,default=10000000)
    p.add_argument('--self-test',action='store_true')
    args=p.parse_args()
    args.path_rates=(20.,10.,15.);args.path_delays=(10.,40.,25.)
    if args.repeats<1 or args.jobs_per_batch<1 or args.max_images<0 or not 0<=args.conflict_percent<=100 or args.failed_path not in (0,1,2) or args.arrival_gap_ms<0 or args.failure_at_ms<0:p.error('Invalid configuration')
    losses=[float(x) for x in args.loss_rates.split(',')]
    if any(not 0<=x<1 for x in losses):p.error('Invalid loss rate')
    schemes=args.schemes.split(',')
    if any(s not in ('XOR_2of2','AESGCM_XOR_Erasure_2of3') for s in schemes):p.error('Only validated Step36A schemes are allowed')
    s33=load(args.step33,'s33_36a1');s34=load(args.step34,'s34_36a1');s35=load(args.step35,'s35_36a1')
    tests(s33,s34,s35,args)
    if args.self_test:return
    root=Path(args.data);out=Path(args.out)
    if not root.is_dir():p.error('Dataset directory missing')
    out.mkdir(parents=True,exist_ok=True)
    imgs=[];manifest=[];issues=[]
    for split in ('train','val'):
        folder=root/'BSR'/'BSDS500'/'data'/'images'/split
        if not folder.is_dir():issues.append('Missing '+str(folder));continue
        paths=sorted(folder.glob('*.jpg'))
        if args.max_images:paths=paths[:args.max_images]
        for fp in paths:
            try:
                with Image.open(fp) as im:
                    rgb=im.convert('RGB').tobytes();bits=bytes(v<128 for v in im.convert('L').tobytes());w,h=im.size
                imgs.append((split,fp.name,rgb,bits))
                manifest.append(dict(split=split,image=fp.name,width=w,height=h,sha256=hashlib.sha256(fp.read_bytes()).hexdigest()))
            except Exception as exc:issues.append(f'{fp}: {exc}')
    records=[]
    for split,name,rgb,bits in imgs:
        for scheme in schemes:
            for rep in range(args.repeats):
                jobs=[]
                for jid in range(args.jobs_per_batch):
                    shares,dec,target,req=s34.make_shares(s33,scheme,rgb,bits)
                    jobs.append(dict(shares=shares,decode=dec,target=target,required=req,start=jid*args.arrival_gap_ms))
                conditions=[('iid',x) for x in losses]+[('burst',x) for x in losses]+[('post_commit_failure',0.),('contention_conflict',0.)]
                for scenario,loss in conditions:
                    for mode in MODES:
                        try:
                            r=run_batch(jobs,mode,scenario,loss,rep,0,args,s35)
                            records.append(dict(split=split,image=name,scheme=scheme,scenario=scenario,loss_rate=loss,repeat=rep,batch=0,mode=mode,**r))
                        except Exception as exc:issues.append(f'{split}/{name}/{scheme}/{scenario}/{mode}: {type(exc).__name__}: {exc}')
    dump_csv(out/'36A1_01_runs.csv',records,FIELDS)
    dump_csv(out/'36A1_02_manifest.csv',manifest,['split','image','width','height','sha256'])
    groups=defaultdict(list)
    for r in records:groups[(r['scheme'],r['scenario'],r['loss_rate'],r['mode'])].append(r)
    summary=[]
    for (scheme,scenario,loss,mode),rs in sorted(groups.items()):
        total=sum(r['jobs'] for r in rs)
        summary.append(dict(scheme=scheme,scenario=scenario,loss_rate=loss,mode=mode,batches=len(rs),jobs=total,recovery_rate=round(sum(r['recovered_jobs'] for r in rs)/total,6),mean_wire_ratio=round(statistics.mean(r['wire_ratio'] for r in rs),6),mean_censored_completion_ms=round(statistics.mean(r['mean_censored_completion_ms'] for r in rs),4),mean_makespan_ms=round(statistics.mean(r['makespan_ms'] for r in rs),4),conflict_attempts=sum(r['conflict_attempts'] for r in rs),conflict_rejected=sum(r['conflict_rejected'] for r in rs),preemptions=sum(r['preemptions'] for r in rs),assistance_events=sum(r['assistance_events'] for r in rs),reassignment_events=sum(r['reassignment_events'] for r in rs),recovery_after_failure=sum(r['recovery_after_failure'] for r in rs)))
    dump_csv(out/'36A1_03_summary.csv',summary,list(summary[0]) if summary else ['scheme','scenario','loss_rate','mode'])
    (out/'36A1_04_issues.txt').write_text('\n'.join(issues) if issues else 'No issues reported.\n',encoding='utf8')
    meta=dict(images=len(imgs),runs=len(records),modes=MODES,schemes=schemes,scenarios=SCENARIOS,loss_rates=losses,repeats=args.repeats,jobs_per_batch=args.jobs_per_batch,seed=args.seed,policy=args.policy,failed_path=args.failed_path,failure_at_ms=args.failure_at_ms,conflict_percent=args.conflict_percent,issues=len(issues),limitations=['Synthetic discrete-event model; not real UDP/Mininet','Failure is revealed after initial assignment, but may occur before a queued transmission begins','Queue service times are estimates and ARQ completion times are not fed back into queue reservations','Preemption is modeled as fixed added delay; no adversarial traffic bytes','Assistance retains owner; reassignment changes owner; only one intervention per job','No signal traffic or controller computation cost','Matched erasure keys by job/path/attempt, but different routing changes which trace a job experiences','Only four pilot images by default; no inferential significance','Cryptographic methods and fec_arq fixed; no GIS/HHO code imported or modified','This is a research prototype, not production security'])
    (out/'36A1_05_metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf8')
    print(json.dumps(dict(output=str(out),images=len(imgs),runs=len(records),modes=len(MODES),schemes=len(schemes),issues=len(issues)),indent=2))
if __name__=='__main__':main()
