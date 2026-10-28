#!/usr/bin/env python3
"""Read-only source dataset benchmark: XOR 2-of-2, Naor-Shamir OR 2-of-2, AES-GCM (optional).
No network transport; cryptographic correctness and local computational cost only.
"""
import argparse,csv,hashlib,json,secrets,time,statistics
from pathlib import Path

def xor_split(b):
    a=secrets.token_bytes(len(b)); return a,bytes(x^y for x,y in zip(a,b))
def xor_join(a,b): return bytes(x^y for x,y in zip(a,b))
def or_split(binary):
    a=bytearray();b=bytearray()
    for bit in binary:
        p=secrets.randbits(1)
        a.extend((p,1-p))
        b.extend((1-p,p) if bit else (p,1-p))
    return bytes(a),bytes(b)
def or_join(a,b):
    return bytes(int((a[i]|b[i])+(a[i+1]|b[i+1])==2) for i in range(0,len(a),2))
def timed(f):
    t=time.perf_counter_ns(); result=f(); return result,(time.perf_counter_ns()-t)/1e6

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--data',default=r'D:\48\481\New Papers\Progressive HHO-Based and Hybrid Multi-Objective Optimization for Color Visual Cryptography\Data')
    ap.add_argument('--out',default='Step32_Method_Screening')
    ap.add_argument('--max-images',type=int,default=0,help='0 means all canonical images')
    ap.add_argument('--repeats',type=int,default=3)
    ap.add_argument('--include-test',action='store_true',help='Opt in to held-out test evaluation only after method selection is frozen')
    args=ap.parse_args()
    if args.repeats<1: ap.error('--repeats must be >= 1')
    try: from PIL import Image
    except ImportError: ap.error('Install Pillow: python -m pip install pillow')
    try: from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError: AESGCM=None
    root=Path(args.data); out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    if not root.is_dir(): ap.error(f'Missing data directory: {root}')
    splits=['train','val']+(['test'] if args.include_test else [])
    rows=[]; manifest=[]; issues=[]
    for split in splits:
        folder=root/'BSR'/'BSDS500'/'data'/'images'/split
        if not folder.is_dir(): issues.append(f'Missing canonical split {folder}'); continue
        images=sorted(folder.glob('*.jpg'))
        if args.max_images: images=images[:args.max_images]
        for path in images:
            try:
                with Image.open(path) as im:
                    rgb=im.convert('RGB'); payload=rgb.tobytes(); gray=im.convert('L'); binary=bytes(1 if x<128 else 0 for x in gray.tobytes()); w,h=im.size
                manifest.append({'split':split,'image':path.name,'width':w,'height':h,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
                for r in range(args.repeats):
                    (shares,enc)=timed(lambda:xor_split(payload)); (rec,dec)=timed(lambda:xor_join(*shares))
                    rows.append(dict(split=split,image=path.name,repeat=r,scheme='XOR_2of2',input_bytes=len(payload),transmitted_bytes=sum(map(len,shares)),encode_ms=enc,decode_ms=dec,exact=int(rec==payload),reconstruction_type='exact_RGB',status='ok'))
                    (shares,enc)=timed(lambda:or_split(binary)); (rec,dec)=timed(lambda:or_join(*shares))
                    rows.append(dict(split=split,image=path.name,repeat=r,scheme='OR_2of2_NaorShamir',input_bytes=len(binary),transmitted_bytes=sum(map(len,shares)),encode_ms=enc,decode_ms=dec,exact=int(rec==binary),reconstruction_type='thresholded_binary_ideal_decoding',status='ok'))
                    if AESGCM:
                        key=AESGCM.generate_key(bit_length=128); nonce=secrets.token_bytes(12); aes=AESGCM(key)
                        (ct,enc)=timed(lambda:aes.encrypt(nonce,payload,None)); (rec,dec)=timed(lambda:aes.decrypt(nonce,ct,None))
                        rows.append(dict(split=split,image=path.name,repeat=r,scheme='AES128_GCM_PSK',input_bytes=len(payload),transmitted_bytes=len(nonce)+len(ct),encode_ms=enc,decode_ms=dec,exact=int(rec==payload),reconstruction_type='exact_RGB',status='ok'))
            except Exception as exc: issues.append(f'{split}/{path.name}: {type(exc).__name__}: {exc}')
    def save_csv(name,data,fields):
        with (out/name).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(data)
    fields=['split','image','repeat','scheme','input_bytes','transmitted_bytes','encode_ms','decode_ms','exact','reconstruction_type','status']
    save_csv('32_01_benchmark_runs.csv',rows,fields)
    save_csv('32_02_manifest.csv',manifest,['split','image','width','height','sha256'])
    groups={}
    for x in rows: groups.setdefault((x['split'],x['scheme']),[]).append(x)
    summary=[]
    for (split,scheme),v in sorted(groups.items()):
        summary.append({'split':split,'scheme':scheme,'runs':len(v),'encode_median_ms':round(statistics.median(x['encode_ms'] for x in v),6),'decode_median_ms':round(statistics.median(x['decode_ms'] for x in v),6),'expansion_ratio':round(statistics.mean(x['transmitted_bytes']/x['input_bytes'] for x in v),6),'exact_fraction':sum(x['exact'] for x in v)/len(v)})
    save_csv('32_03_summary.csv',summary,['split','scheme','runs','encode_median_ms','decode_median_ms','expansion_ratio','exact_fraction'])
    (out/'32_04_issues.txt').write_text('\n'.join(issues) or 'No issues reported.\n',encoding='utf-8')
    meta={'dataset':str(root),'splits':splits,'images':len(manifest),'runs':len(rows),'AES_GCM_available':AESGCM is not None,'network_simulated':False,'limitations':['Local CPU timing only; no UDP/Mininet or packet-loss tests','OR uses binary thresholded input and idealized decoding, not visual contrast','No random-grid or threshold sharing competitor implemented','AES-GCM pre-shared key excludes key distribution','Python XOR and OR are not optimized; cross-scheme CPU timing is implementation-dependent','No security claims from entropy or visual appearance']}
    (out/'32_05_metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(out),'images':len(manifest),'runs':len(rows),'issues':len(issues),'aes_available':AESGCM is not None},indent=2))
if __name__=='__main__':main()
