#!/usr/bin/env python3
"""Step 35: fixed packet-level FEC/ARQ transport benchmark; no GIS/HHO changes.
Research simulation: deterministic erasures, ideal feedback, no queues/jitter/sockets.
"""
import argparse, csv, hashlib, json, math, random, statistics
from pathlib import Path
from collections import defaultdict
from PIL import Image
import importlib.util

SCHEMES=['XOR_2of2','OR_2of2','RandomGrid_OR_2of2','Shamir_GF256_2of3','AES128_GCM_PSK','X25519_HKDF_AES128_GCM','AESGCM_XOR_Erasure_2of3']
POLICIES=['none','fec','arq','fec_arq']
FIELDS=['split','image','scheme','policy','scenario','loss_rate','repeat','payload_bytes','wire_bytes','wire_ratio','packets_sent','packets_lost','packets_recovered_fec','retransmitted_packets','fragments_complete','fragments_required','recovered','exact','completion_ms','visual_contrast','failure_reason']

def load_module(path,name):
    spec=importlib.util.spec_from_file_location(name,str(path))
    if not spec or not spec.loader:raise RuntimeError(f'Cannot load {path}')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def rng_for(seed,scenario,rate,rep,path,packet_id,attempt):
    key=f'{seed}|{scenario}|{rate:.9f}|{rep}|{path}|{packet_id}|{attempt}'.encode()
    return random.Random(int.from_bytes(hashlib.sha256(key).digest()[:8],'big'))

def erasure(seed,scenario,rate,rep,path,packet_id,attempt,failed_path,burst_persist):
    if scenario=='path_failure':return path==failed_path
    if rate==0:return False
    if scenario=='iid':return rng_for(seed,scenario,rate,rep,path,packet_id,attempt).random()<rate
    # Correlated loss: Markov state along packet IDs, with independent trace per attempt.
    # Compute state up to packet_id using cached per-path trace, rather than treating
    # individual packets as independent in a burst scenario.
    raise RuntimeError('burst handled by trace generator')

def make_trace(seed,scenario,rate,rep,path,attempt,n,failed_path,persist):
    if scenario=='path_failure':return [path==failed_path]*n
    if scenario=='iid':return [erasure(seed,scenario,rate,rep,path,i,attempt,failed_path,persist) for i in range(n)]
    seed_data=f'{seed}|{scenario}|{rate:.9f}|{rep}|{path}|attempt={attempt}'.encode()
    rng=random.Random(int.from_bytes(hashlib.sha256(seed_data).digest()[:8],'big'))
    bad=False; result=[]
    for _ in range(n):
        if bad:bad=rng.random()<persist
        else:bad=rng.random()<min(1.0,rate*(1-persist)/max(1e-12,1-rate))
        result.append(bad)
    return result

def xor_bytes(chunks,mtu):
    out=bytearray(mtu)
    for ch in chunks:
        for i,b in enumerate(ch):out[i]^=b
    return bytes(out)

def transport(blob,path,policy,scenario,rate,rep,args):
    """One fragment over one fixed path. Each FEC group has K source packets
    and one XOR parity packet. ARQ retries only unresolved source packets.
    Fragment length is known to the receiver (ideal metadata channel).
    """
    mtu=args.mtu; k=args.fec_group
    src=[blob[i:i+mtu] for i in range(0,len(blob),mtu)] or [b'']
    groups=[list(range(i,min(i+k,len(src)))) for i in range(0,len(src),k)]
    has_fec=policy in ('fec','fec_arq');has_arq=policy in ('arq','fec_arq')
    # Logical packet IDs fixed across policies for common erasure traces:
    # source IDs 0..N-1, parity IDs N..N+groups-1.
    n=len(src);total_ids=n+len(groups)
    trace0=make_trace(args.seed,scenario,rate,rep,path,0,total_ids,args.failed_path,args.burst_persist)
    missing=set();lost=0;sent=0;wire=0;fec_fixed=0;retry_count=0
    # Track rounds of transmissions; per-path serial link, feedback round trip.
    rounds=1;packet_payloads={}
    for i,chunk in enumerate(src):
        sent+=1;wire+=len(chunk)+args.header_bytes
        if trace0[i]:lost+=1;missing.add(i)
        else:packet_payloads[i]=chunk
    parity={}
    if has_fec:
        for gi,group in enumerate(groups):
            p=xor_bytes([src[i] for i in group],mtu)
            sent+=1;wire+=len(p)+args.header_bytes
            if trace0[n+gi]:lost+=1
            else:parity[gi]=p
    def repair():
        nonlocal fec_fixed
        if not has_fec:return
        for gi,group in enumerate(groups):
            lost_group=[i for i in group if i in missing]
            if len(lost_group)==1 and gi in parity:
                missing_id=lost_group[0]
                padded=xor_bytes([parity[gi]]+[packet_payloads[i] for i in group if i!=missing_id],mtu)
                recovered=padded[:len(src[missing_id])]
                packet_payloads[missing_id]=recovered
                missing.remove(missing_id);fec_fixed+=1
    repair()
    if has_arq:
        for attempt in range(1,args.max_retries+1):
            if not missing:break
            rounds+=1
            trace=make_trace(args.seed,scenario,rate,rep,path,attempt,total_ids,args.failed_path,args.burst_persist)
            for i in sorted(missing):
                chunk=src[i];sent+=1;retry_count+=1;wire+=len(chunk)+args.header_bytes
                if trace[i]:lost+=1
                else:packet_payloads[i]=chunk
            missing.difference_update(packet_payloads.keys())
            repair()
    complete=not missing
    if complete:
        restored=b''.join(packet_payloads[i] for i in range(n))
        if restored!=blob:raise AssertionError('Transport silently corrupted a fragment')
    rate_mbps=args.path_rates[path];delay=args.path_delays[path]
    # Conservative sequential per-path serialization, one propagation delay
    # for initial data and one idealized RTT for each ARQ round.
    latency=delay+wire*8/(rate_mbps*1000)+(rounds-1)*2*delay
    return (blob if complete else None),wire,sent,lost,fec_fixed,retry_count,latency

def write_csv(path,rows,fields):
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def selftest(step33,step34,args):
    step33.selftest()
    for length in (1,17,99,100,101,401,1001):
        b=bytes((i*31+7)%256 for i in range(length))
        for policy in POLICIES:
            for scenario in ('iid','burst','path_failure'):
                result=transport(b,0,policy,scenario,0,0,args)
                assert result[0]==b,(length,policy,scenario)
            if policy in ('fec','fec_arq'):
                # Deterministic recovery primitive test, one erased source.
                chunks=[b[i:i+args.mtu] for i in range(0,len(b),args.mtu)]
                if len(chunks)>1:
                    parity=xor_bytes(chunks[:args.fec_group],args.mtu)
                    restored=xor_bytes([parity]+chunks[1:args.fec_group],args.mtu)[:len(chunks[0])]
                    assert restored==chunks[0]
    # Threshold recovery over serialized, delivered shares.
    for scheme in SCHEMES:
        data=bytes(range(33));bits=bytes(i%2 for i in range(33))
        shares,decode,target,required=step34.make_shares(step33,scheme,data,bits)
        for chosen in (shares[:required],shares[-required:]):
            got=decode(dict(chosen))
            if scheme=='RandomGrid_OR_2of2':assert len(got)==len(bits)
            else:assert got==target
    print('PASS: Step 35 packet recovery, FEC algebra, transport integrity, and threshold tests')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',required=False,default='')
    p.add_argument('--step33',default=str(Path(__file__).resolve().parent/'33_expanded_baseline.py'))
    p.add_argument('--step34',default=str(Path(__file__).resolve().parent/'34_multipath_loss_simulator.py'))
    p.add_argument('--out',default='Step35_Packet_Recovery')
    p.add_argument('--max-images',type=int,default=2);p.add_argument('--repeats',type=int,default=3)
    p.add_argument('--seed',type=int,default=3501);p.add_argument('--loss-rates',default='0,0.01,0.05,0.10,0.20')
    p.add_argument('--mtu',type=int,default=1000);p.add_argument('--header-bytes',type=int,default=20)
    p.add_argument('--fec-group',type=int,default=4);p.add_argument('--max-retries',type=int,default=3)
    p.add_argument('--failed-path',type=int,default=1);p.add_argument('--burst-persist',type=float,default=.85)
    p.add_argument('--self-test',action='store_true');p.add_argument('--include-test',action='store_true')
    args=p.parse_args()
    if args.mtu<1 or args.fec_group<2 or args.max_retries<0 or args.repeats<1 or args.max_images<0 or args.header_bytes<0 or args.failed_path not in (0,1,2) or not 0<=args.burst_persist<1:p.error('Invalid parameter')
    try:losses=[float(x) for x in args.loss_rates.split(',')];assert losses and all(0<=x<1 for x in losses)
    except (ValueError,AssertionError):p.error('Invalid --loss-rates')
    args.path_rates=(20.,10.,15.);args.path_delays=(10.,40.,25.)
    m=load_module(args.step33,'step33_reference');s=load_module(args.step34,'step34_reference')
    selftest(m,s,args)
    if args.self_test:return
    root=Path(args.data);out=Path(args.out)
    if not root.is_dir():p.error(f'Data directory missing: {root}')
    out.mkdir(parents=True,exist_ok=True)
    rows=[];manifest=[];issues=[]
    for split in ['train','val']+(['test'] if args.include_test else []):
        folder=root/'BSR'/'BSDS500'/'data'/'images'/split
        if not folder.is_dir():issues.append(f'Missing {folder}');continue
        files=sorted(folder.glob('*.jpg'))
        if args.max_images:files=files[:args.max_images]
        for image_path in files:
            try:
                with Image.open(image_path) as img:
                    rgb=img.convert('RGB').tobytes();bits=bytes(v<128 for v in img.convert('L').tobytes());w,h=img.size
                manifest.append(dict(split=split,image=image_path.name,width=w,height=h,sha256=hashlib.sha256(image_path.read_bytes()).hexdigest()))
                for rep in range(args.repeats):
                    for scheme in SCHEMES:
                        shares,decode,target,required=s.make_shares(m,scheme,rgb,bits)
                        for scenario,loss in ([('iid',x) for x in losses]+[('burst',x) for x in losses]+[('path_failure',0.)]):
                            for policy in POLICIES:
                                received={};wire=sent=lost=fixed=retries=0;arrivals=[]
                                for path_id,blob in shares:
                                    got,wbytes,npack,nlost,nfixed,nretry,lat=transport(blob,path_id,policy,scenario,loss,rep,args)
                                    wire+=wbytes;sent+=npack;lost+=nlost;fixed+=nfixed;retries+=nretry
                                    if got is not None:received[path_id]=got;arrivals.append((lat,path_id))
                                ok=len(received)>=required;decoded=None;reason=''
                                if ok:
                                    try:decoded=decode(received)
                                    except Exception as ex:ok=False;reason='decode:'+type(ex).__name__
                                if not ok and not reason:reason='insufficient_complete_fragments'
                                exact=None if decoded is None or scheme=='RandomGrid_OR_2of2' else int(decoded==target)
                                _,_,contrast=s.visual_metrics(scheme,shares,received,bits,decoded)
                                completion=''
                                if ok:
                                    completion=round(sorted(t for t,_ in arrivals)[required-1],6)
                                rows.append(dict(split=split,image=image_path.name,scheme=scheme,policy=policy,scenario=scenario,loss_rate=loss,repeat=rep,payload_bytes=len(target),wire_bytes=wire,wire_ratio=round(wire/len(target),6),packets_sent=sent,packets_lost=lost,packets_recovered_fec=fixed,retransmitted_packets=retries,fragments_complete=len(received),fragments_required=required,recovered=int(ok),exact='' if exact is None else exact,completion_ms=completion,visual_contrast='' if contrast is None else round(contrast,6),failure_reason=reason))
            except Exception as ex:issues.append(f'{split}/{image_path.name}: {type(ex).__name__}: {ex}')
    write_csv(out/'35_01_runs.csv',rows,FIELDS)
    write_csv(out/'35_02_manifest.csv',manifest,['split','image','width','height','sha256'])
    grouped=defaultdict(list)
    for r in rows:grouped[(r['scheme'],r['policy'],r['scenario'],r['loss_rate'])].append(r)
    summary=[]
    for (scheme,policy,scenario,loss),rr in sorted(grouped.items()):
        successes=[r for r in rr if r['recovered']]
        summary.append(dict(scheme=scheme,policy=policy,scenario=scenario,loss_rate=loss,runs=len(rr),recovery_fraction=round(len(successes)/len(rr),6),mean_wire_ratio=round(statistics.mean(r['wire_ratio'] for r in rr),6),median_completion_ms=round(statistics.median(r['completion_ms'] for r in successes),6) if successes else '',mean_retransmitted_packets=round(statistics.mean(r['retransmitted_packets'] for r in rr),3),mean_fec_recovered_packets=round(statistics.mean(r['packets_recovered_fec'] for r in rr),3),mean_visual_contrast=round(statistics.mean(float(r['visual_contrast']) for r in successes if r['visual_contrast']!=''),6) if any(r['visual_contrast']!='' for r in successes) else ''))
    write_csv(out/'35_03_summary.csv',summary,['scheme','policy','scenario','loss_rate','runs','recovery_fraction','mean_wire_ratio','median_completion_ms','mean_retransmitted_packets','mean_fec_recovered_packets','mean_visual_contrast'])
    (out/'35_04_issues.txt').write_text('\n'.join(issues) if issues else 'No issues reported.\n',encoding='utf-8')
    metadata=dict(images=len(manifest),runs=len(rows),schemes=SCHEMES,policies=POLICIES,scenarios=['iid','burst','path_failure'],loss_rates=losses,repeats=args.repeats,seed=args.seed,mtu=args.mtu,header_bytes=args.header_bytes,fec_group=args.fec_group,max_retries=args.max_retries,failed_path=args.failed_path,burst_persist=args.burst_persist,issues=len(issues),limitations=['Deterministic simulation, not UDP/Mininet','Fixed paths; no GIS/HHO code imported or modified','XOR single-parity FEC corrects one lost source packet per group if parity arrives','Selective ARQ uses ideal immediate missing-packet feedback and idealized RTT, no control-message bytes','Burst retransmission attempts use separately seeded correlated traces','No queuing, jitter, congestion, packet reordering, coding CPU, or key exchange time','Whole-fragment completion required before threshold reconstruction','No adaptive routing, failover, or organizational intelligence','OR/random-grid reconstruction is visual, not exact RGB','Method selection uses train/val only; do not include test during screening','Research prototype, not production cryptography'])
    (out/'35_05_metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print(json.dumps(dict(output=str(out),images=len(manifest),runs=len(rows),schemes=len(SCHEMES),policies=len(POLICIES),issues=len(issues)),indent=2))

if __name__=='__main__':main()
