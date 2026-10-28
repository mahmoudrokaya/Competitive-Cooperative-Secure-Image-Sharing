#!/usr/bin/env python3
"""Step 34: deterministic packet-erasure simulation for Step 33 schemes.
Research simulation only; NO actual sockets, Mininet, cryptographic deployment,
GIS/HHO imports or source modifications. Training/validation only by default.
"""
import argparse, csv, hashlib, json, math, random, statistics, sys
from pathlib import Path
from collections import defaultdict
from PIL import Image
import importlib.util

HERE=Path(__file__).resolve().parent
DEFAULT_DATA=r'D:\48\481\New Papers\Progressive HHO-Based and Hybrid Multi-Objective Optimization for Color Visual Cryptography\Data'
SCHEMES=['XOR_2of2','OR_2of2','RandomGrid_OR_2of2','Shamir_GF256_2of3','AES128_GCM_PSK','X25519_HKDF_AES128_GCM','AESGCM_XOR_Erasure_2of3']
FIELDS=['split','image','scheme','scenario','loss_rate','repeat','payload_bytes','wire_bytes','wire_ratio','packets_sent','packets_lost','fragments_complete','fragments_required','recovered','exact','completion_ms','failure_reason','visual_black_mean','visual_white_mean','visual_contrast']

def load_step33(path):
    spec=importlib.util.spec_from_file_location('step33_reference',str(path))
    if spec is None or spec.loader is None:raise RuntimeError('Cannot import Step33 module')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m

def write_csv(path,rows,fields):
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def make_shares(m,scheme,data,bits):
    """Return [(path_id, bytes)], decoder, target, required fragment count, notes.
    Fixed path mapping is a baseline, NOT an adaptive organizational policy.
    """
    if scheme=='XOR_2of2':
        shares=m.xor_split(data)
        return list(enumerate(shares)),lambda d:m.xor_join((d[0],d[1])),data,2
    if scheme=='OR_2of2':
        shares=m.or_split(bits)
        return list(enumerate(shares)),lambda d:m.or_join((d[0],d[1])),bits,2
    if scheme=='RandomGrid_OR_2of2':
        shares=m.random_grid_split(bits)
        return list(enumerate(shares)),lambda d:m.random_grid_visual_overlay((d[0],d[1])),bits,2
    if scheme=='Shamir_GF256_2of3':
        shares=m.shamir_2of3_split(data)
        return [(i-1,shares[i]) for i in (1,2,3)],lambda d:m.shamir_2of3_join({i+1:b for i,b in sorted(d.items())[:2]}),data,2
    if scheme=='AES128_GCM_PSK':
        (key,nonce,ct),_=m.aes_encrypt(data)
        blob=nonce+ct
        return [(0,blob)],lambda d:m.AESGCM(key).decrypt(d[0][:12],d[0][12:],None),data,1
    if scheme=='X25519_HKDF_AES128_GCM':
        (recipient,pub,salt,nonce,ct),_=m.hpke_like_encrypt(data)
        blob=pub+salt+nonce+ct
        def decode(d):
            x=d[0]; return m.hpke_like_decrypt((recipient,x[:32],x[32:48],x[48:60],x[60:]))
        return [(0,blob)],decode,data,1
    if scheme=='AESGCM_XOR_Erasure_2of3':
        (key,nonce,n,frags),_=m.encrypted_erasure_split(data)
        # Shared nonce/length are sent in EACH fragment, not counted only once.
        # Key is assumed pre-shared and NOT transmitted.
        import struct
        shares=[(i,nonce+struct.pack('>I',n)+frags[i]) for i in (0,1,2)]
        def decode(d):
            chosen={i:v[16:] for i,v in d.items()}
            return m.encrypted_erasure_join((key,nonce,n,chosen),tuple(sorted(chosen)[:2]))
        return shares,decode,data,2
    raise ValueError(scheme)

def packet_trace(seed,scenario,loss,rep,path,n_packets,burst_persist):
    # Common random numbers across schemes: path, repetition and packet index share
    # the same random draws regardless of scheme, enabling paired comparisons.
    key=f'{seed}|{scenario}|{loss:.9f}|{rep}|{path}'.encode()
    rng=random.Random(int.from_bytes(hashlib.sha256(key).digest()[:8],'big'))
    bad=False; result=[]
    for _ in range(n_packets):
        if scenario=='burst':
            # Two-state model with stationary loss probability ~= loss.
            # P(bad->bad)=persist; P(good->bad)=loss*(1-persist)/(1-loss).
            if bad:bad=rng.random()<burst_persist
            else:bad=rng.random()<min(1.,loss*(1-burst_persist)/max(1e-12,1-loss))
            result.append(bad)
        else:result.append(rng.random()<loss)
    return result

def simulate(shares,scenario,loss,rep,args):
    received={};total_wire=0;sent=0;lost=0;arrivals=[]
    for path_id,blob in shares:
        chunks=[blob[i:i+args.mtu] for i in range(0,len(blob),args.mtu)] or [b'']
        trace=packet_trace(args.seed,scenario,loss,rep,path_id,len(chunks),args.burst_persist)
        if scenario=='path_failure' and path_id==args.failed_path:trace=[True]*len(chunks)
        # One packet header of specified bytes; no retransmissions.
        total_wire+=len(blob)+len(chunks)*args.header_bytes
        sent+=len(chunks);lost+=sum(trace)
        if not any(trace):
            received[path_id]=blob
            rate=args.path_rates_mbps[path_id%len(args.path_rates_mbps)]
            delay=args.path_delays_ms[path_id%len(args.path_delays_ms)]
            # Serial transmission on each independent path; completion at final packet.
            arrivals.append(delay+(len(blob)+len(chunks)*args.header_bytes)*8/(rate*1000))
    return received,total_wire,sent,lost,max(arrivals) if arrivals else None

def visual_metrics(scheme,shares,received,bits,decoded):
    # Meaningful ONLY if all shares arrived. Black=1; OR overlay black density
    # differs for black and white source pixels. Report empirical separation.
    if decoded is None or scheme not in ('OR_2of2','RandomGrid_OR_2of2'):return (None,None,None)
    if scheme=='OR_2of2':
        density=[(decoded[2*i]+decoded[2*i+1])/2 for i in range(len(bits))] if len(decoded)==2*len(bits) else []
    else:density=list(decoded)
    blacks=[v for v,b in zip(density,bits) if b==1]
    whites=[v for v,b in zip(density,bits) if b==0]
    bm=statistics.mean(blacks) if blacks else None
    wm=statistics.mean(whites) if whites else None
    return bm,wm,(bm-wm if bm is not None and wm is not None else None)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',default=DEFAULT_DATA);p.add_argument('--step33',default=str(HERE/'33_expanded_baseline.py'))
    p.add_argument('--out',default='Step34_Multipath');p.add_argument('--max-images',type=int,default=2)
    p.add_argument('--repeats',type=int,default=3);p.add_argument('--seed',type=int,default=3401)
    p.add_argument('--loss-rates',default='0,0.01,0.05,0.10,0.20')
    p.add_argument('--mtu',type=int,default=1000);p.add_argument('--header-bytes',type=int,default=20)
    p.add_argument('--burst-persist',type=float,default=.85);p.add_argument('--failed-path',type=int,default=1)
    p.add_argument('--include-test',action='store_true',help='Do not use for method screening')
    p.add_argument('--self-test',action='store_true')
    args=p.parse_args()
    if args.mtu<1 or args.header_bytes<0 or args.repeats<1 or args.max_images<0 or not 0<=args.burst_persist<1 or args.failed_path not in (0,1,2):p.error('Invalid parameter')
    try:losses=[float(x) for x in args.loss_rates.split(',')];assert losses and all(0<=x<1 for x in losses)
    except (ValueError,AssertionError):p.error('loss-rates must be comma-separated fractions in [0,1)')
    args.path_rates_mbps=(20.,10.,15.);args.path_delays_ms=(10.,40.,25.)
    m=load_step33(Path(args.step33));m.selftest()
    # Explicit correctness checks of serialized transport reconstruction.
    for size in (1,31,1001):
        data=bytes((i*17)%256 for i in range(size));bits=bytes(i%2 for i in range(size))
        for scheme in SCHEMES:
            shares,decode,target,k=make_shares(m,scheme,data,bits)
            for ids in ([i for i,_ in shares][:k], [i for i,_ in shares][-k:]):
                got=decode(dict((i,b) for i,b in shares if i in ids))
                if scheme=='RandomGrid_OR_2of2':assert len(got)==len(bits)
                else:assert got==target,(scheme,size,ids)
    print('PASS: serialized transport and threshold reconstruction tests')
    if args.self_test:return
    root=Path(args.data);out=Path(args.out)
    if not root.is_dir():p.error(f'Data directory missing: {root}')
    out.mkdir(parents=True,exist_ok=True)
    rows=[];manifest=[];issues=[]
    for split in (['train','val']+(['test'] if args.include_test else [])):
        folder=root/'BSR'/'BSDS500'/'data'/'images'/split
        if not folder.is_dir():issues.append(f'Missing {folder}');continue
        files=sorted(folder.glob('*.jpg'))
        if args.max_images:files=files[:args.max_images]
        for path in files:
            try:
                with Image.open(path) as img:
                    data=img.convert('RGB').tobytes()
                    bits=bytes(v<128 for v in img.convert('L').tobytes())
                    w,h=img.size
                manifest.append({'split':split,'image':path.name,'width':w,'height':h,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
                # Generate fresh shares per image and repetition; reuse across network conditions.
                for rep in range(args.repeats):
                    for scheme in SCHEMES:
                        shares,decode,target,required=make_shares(m,scheme,data,bits)
                        for scenario,rate in ([('iid',x) for x in losses]+[('burst',x) for x in losses]+[('path_failure',0.)]):
                            received,wire,sent,lost,lat=simulate(shares,scenario,rate,rep,args)
                            ok=len(received)>=required;decoded=None;reason=''
                            if ok:
                                try:decoded=decode(received)
                                except Exception as ex:ok=False;reason=f'decode:{type(ex).__name__}'
                            if not ok and not reason:reason='insufficient_complete_fragments'
                            exact=(decoded==target) if decoded is not None and scheme!='RandomGrid_OR_2of2' else None
                            bm,wm,contrast=visual_metrics(scheme,shares,received,bits,decoded)
                            rows.append(dict(split=split,image=path.name,scheme=scheme,scenario=scenario,loss_rate=rate,repeat=rep,payload_bytes=len(target),wire_bytes=wire,wire_ratio=round(wire/len(target),6),packets_sent=sent,packets_lost=lost,fragments_complete=len(received),fragments_required=required,recovered=int(ok),exact=int(exact) if exact is not None else '',completion_ms=round(lat,6) if ok and lat is not None else '',failure_reason=reason,visual_black_mean=round(bm,6) if bm is not None else '',visual_white_mean=round(wm,6) if wm is not None else '',visual_contrast=round(contrast,6) if contrast is not None else ''))
            except Exception as ex:issues.append(f'{split}/{path.name}: {type(ex).__name__}: {ex}')
    write_csv(out/'34_01_runs.csv',rows,FIELDS)
    write_csv(out/'34_02_manifest.csv',manifest,['split','image','width','height','sha256'])
    groups=defaultdict(list)
    for r in rows:groups[(r['scheme'],r['scenario'],r['loss_rate'])].append(r)
    summaries=[]
    for (scheme,scenario,rate),items in sorted(groups.items()):
        success=[r for r in items if r['recovered']]
        summaries.append(dict(scheme=scheme,scenario=scenario,loss_rate=rate,runs=len(items),recovery_fraction=round(len(success)/len(items),6),mean_wire_ratio=round(statistics.mean(r['wire_ratio'] for r in items),6),median_completion_ms=round(statistics.median(r['completion_ms'] for r in success),6) if success else '',mean_packet_loss_fraction=round(statistics.mean(r['packets_lost']/r['packets_sent'] for r in items),6),mean_visual_contrast=round(statistics.mean(float(r['visual_contrast']) for r in success if r['visual_contrast']!=''),6) if any(r['visual_contrast']!='' for r in success) else ''))
    write_csv(out/'34_03_summary.csv',summaries,['scheme','scenario','loss_rate','runs','recovery_fraction','mean_wire_ratio','median_completion_ms','mean_packet_loss_fraction','mean_visual_contrast'])
    (out/'34_04_issues.txt').write_text('\n'.join(issues) if issues else 'No issues reported.\n',encoding='utf-8')
    meta={'images':len(manifest),'runs':len(rows),'schemes':SCHEMES,'scenarios':['iid','burst','path_failure'],'loss_rates':losses,'repeats':args.repeats,'seed':args.seed,'mtu_payload_bytes':args.mtu,'header_bytes_per_packet':args.header_bytes,'path_delays_ms':args.path_delays_ms,'path_rates_mbps':args.path_rates_mbps,'failed_path':args.failed_path,'burst_persist':args.burst_persist,'issues':len(issues),'limitations':['Synthetic packet erasures only; no UDP, retransmission, queuing, jitter, congestion, or real Mininet','Fixed path assignment; no GIS-inspired controller or HHO changes','A fragment is usable only when every packet of that fragment arrives; no partial-image recovery','Completion latency is propagation plus serialization for complete fragments; excludes encode/decode CPU, packetization, scheduling and queueing','Each share/fragment uses one path; AES methods use one path and no failover','Single-path AES key pre-shared; X25519 private key local; erasure encryption key pre-shared','Visual OR and random-grid schemes require contrast interpretation; exact RGB recovery is not applicable','Random grid reconstruction cannot be called exact secret recovery','Method selection must not use held-out test images','Common random-number traces across methods; packet count differs with expansion','Path failure affects path index '+str(args.failed_path),'This is a research prototype; not production cryptography']}
    (out/'34_05_metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(out),'images':len(manifest),'runs':len(rows),'schemes':len(SCHEMES),'issues':len(issues)},indent=2))
if __name__=='__main__':main()
