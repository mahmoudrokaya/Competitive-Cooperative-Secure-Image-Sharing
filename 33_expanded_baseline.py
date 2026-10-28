#!/usr/bin/env python3
"""Step 33: experimental, read-only dataset baseline screening.
Research prototype, NOT a production cryptographic implementation.
Does not alter GIS/HHO source, use network transport, or touch test split by default.
"""
import argparse, csv, hashlib, json, math, platform, secrets, statistics, sys, time
from pathlib import Path

try:
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    X25519PrivateKey = None

DEFAULT_DATA = r'D:\48\481\New Papers\Progressive HHO-Based and Hybrid Multi-Objective Optimization for Color Visual Cryptography\Data'
FIELDS = ['split','image','repeat','scheme','payload_type','input_bytes','transmitted_bytes','expansion_ratio','encode_ms','decode_ms','exact','reconstruction_type','security_class','notes']

# GF(2^8), AES irreducible polynomial x^8+x^4+x^3+x+1 (0x11b).
def gf_mul(a,b):
    r=0
    while b:
        if b&1:r^=a
        a=(a<<1) ^ (0x11b if a&0x80 else 0)
        a &=255
        b>>=1
    return r

def gf_inv(a):
    if not a: raise ValueError('zero has no inverse')
    for b in range(1,256):
        if gf_mul(a,b)==1:return b
    raise AssertionError('GF inverse unavailable')

# Use precomputed translation tables to avoid a Python loop per payload byte.
MUL = [bytes(gf_mul(a,b) for b in range(256)) for a in range(256)]
def mix(a,b,coef):
    return bytes(x^y for x,y in zip(a,b.translate(MUL[coef])))

def xor_split(data):
    a=secrets.token_bytes(len(data)); return (a,bytes(x^y for x,y in zip(data,a)))
def xor_join(shares):return bytes(x^y for x,y in zip(*shares))

def shamir_2of3_split(data):
    slope=secrets.token_bytes(len(data))
    return {x:mix(data,slope,x) for x in (1,2,3)}
def shamir_2of3_join(shares):
    if len(shares)!=2:raise ValueError('Exactly two distinct shares required')
    (x1,y1),(x2,y2)=list(shares.items())
    if x1==x2 or len(y1)!=len(y2):raise ValueError('Invalid shares')
    slope=bytes((a^b) for a,b in zip(y1,y2)).translate(MUL[gf_inv(x1^x2)])
    return mix(y1,slope,x1)

def or_split(bits):
    a=bytearray();b=bytearray()
    for bit in bits:
        p=secrets.randbits(1);a.extend((p,1-p));b.extend((1-p,p) if bit else (p,1-p))
    return bytes(a),bytes(b)
def or_join(shares):
    a,b=shares
    return bytes(int((a[i]|b[i])+(a[i+1]|b[i+1])==2) for i in range(0,len(a),2))

def random_grid_split(bits):
    # Two shares, no pixel expansion. A single-share pixel is unbiased.
    # For white pixel, shares equal; for black, shares are complementary.
    a=bytes(secrets.randbits(1) for _ in bits)
    b=bytes(v if bit==0 else (1-v) for v,bit in zip(a,bits))
    return a,b

def random_grid_visual_overlay(shares):
    a,b=shares
    return bytes(x|y for x,y in zip(a,b))

def aes_encrypt(data):
    key=AESGCM.generate_key(bit_length=128);nonce=secrets.token_bytes(12)
    ct=AESGCM(key).encrypt(nonce,data,None)
    return (key,nonce,ct),len(nonce)+len(ct)
def aes_decrypt(obj):
    key,nonce,ct=obj;return AESGCM(key).decrypt(nonce,ct,None)

def hpke_like_encrypt(data):
    # X25519 + HKDF + AES-GCM, custom educational envelope, NOT RFC 9180 HPKE.
    if X25519PrivateKey is None:raise RuntimeError('cryptography is not installed')
    recipient=X25519PrivateKey.generate(); sender=X25519PrivateKey.generate()
    pub=sender.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    salt=secrets.token_bytes(16)
    shared=sender.exchange(recipient.public_key())
    key=HKDF(algorithm=hashes.SHA256(),length=16,salt=salt,info=b'Step33 X25519+AESGCM v1').derive(shared)
    nonce=secrets.token_bytes(12);ct=AESGCM(key).encrypt(nonce,data,None)
    return (recipient,pub,salt,nonce,ct),len(pub)+len(salt)+len(nonce)+len(ct)
def hpke_like_decrypt(obj):
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
    recipient,pub,salt,nonce,ct=obj
    shared=recipient.exchange(X25519PublicKey.from_public_bytes(pub))
    key=HKDF(algorithm=hashes.SHA256(),length=16,salt=salt,info=b'Step33 X25519+AESGCM v1').derive(shared)
    return AESGCM(key).decrypt(nonce,ct,None)

def encrypted_erasure_split(data):
    # AES-GCM ciphertext divided into two halves, third XOR parity; any 2 reconstruct.
    # IMPORTANT: fragments are NOT individually confidential. Key is external/pre-shared.
    key=AESGCM.generate_key(bit_length=128);nonce=secrets.token_bytes(12)
    ct=AESGCM(key).encrypt(nonce,data,None)
    n=len(ct); half=(n+1)//2
    a=ct[:half].ljust(half,b'\x00');b=ct[half:].ljust(half,b'\x00')
    p=bytes(x^y for x,y in zip(a,b))
    # 12-byte nonce and 4-byte original ciphertext length counted once, not per fragment.
    return (key,nonce,n,{0:a,1:b,2:p}),3*half+16

def encrypted_erasure_join(obj,ids):
    key,nonce,n,fragments=obj
    if len(ids)!=2 or len(set(ids))!=2:raise ValueError('two distinct fragments required')
    chosen={i:fragments[i] for i in ids}
    if 0 in chosen and 1 in chosen:a,b=chosen[0],chosen[1]
    elif 0 in chosen:a=chosen[0];b=bytes(x^y for x,y in zip(a,chosen[2]))
    else:b=chosen[1];a=bytes(x^y for x,y in zip(b,chosen[2]))
    return AESGCM(key).decrypt(nonce,(a+b)[:n],None)

def now_ms(fn):
    t=time.perf_counter_ns();v=fn();return v,(time.perf_counter_ns()-t)/1e6

def write_csv(path,rows,fields):
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def selftest():
    for length in (0,1,2,3,17,1001):
        data=secrets.token_bytes(length)
        assert xor_join(xor_split(data))==data
        s=shamir_2of3_split(data)
        for pair in ((1,2),(1,3),(2,3)):
            assert shamir_2of3_join({i:s[i] for i in pair})==data
        e=encrypted_erasure_split(data)
        for pair in ((0,1),(0,2),(1,2)):
            assert encrypted_erasure_join(e[0],pair)==data
        a=aes_encrypt(data);assert aes_decrypt(a[0])==data
        if X25519PrivateKey is not None:
            h=hpke_like_encrypt(data);assert hpke_like_decrypt(h[0])==data
    bits=bytes([0,1,1,0,1,0])
    assert or_join(or_split(bits))==bits
    a,b=random_grid_split(bits)
    assert all((x|y)==1 for x,y,bit in zip(a,b,bits) if bit)
    assert all(x==y for x,y,bit in zip(a,b,bits) if not bit)
    print('PASS: local correctness tests, threshold recovery, and authenticated decryption')

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data',default=DEFAULT_DATA)
    ap.add_argument('--out',default='Step33_Expanded_Baselines')
    ap.add_argument('--max-images',type=int,default=2,help='Images per split; 0 means all (slow)')
    ap.add_argument('--repeats',type=int,default=2)
    ap.add_argument('--self-test',action='store_true')
    ap.add_argument('--include-test',action='store_true',help='Explicit opt-in; do not use during method selection')
    args=ap.parse_args()
    if args.self_test:selftest();return
    if args.repeats<1 or args.max_images<0:ap.error('Invalid repeats or max-images')
    try:from PIL import Image
    except ImportError:ap.error('Install pillow: python -m pip install pillow')
    if X25519PrivateKey is None:ap.error('Install cryptography: python -m pip install cryptography')
    root=Path(args.data);out=Path(args.out)
    if not root.is_dir():ap.error(f'Dataset not found: {root}')
    out.mkdir(parents=True,exist_ok=True)
    selftest()
    rows=[];manifest=[];issues=[]
    splits=['train','val']+(['test'] if args.include_test else [])
    for split in splits:
        folder=root/'BSR'/'BSDS500'/'data'/'images'/split
        if not folder.is_dir():issues.append(f'Missing split: {folder}');continue
        files=sorted(folder.glob('*.jpg'))
        if args.max_images:files=files[:args.max_images]
        for path in files:
            try:
                with Image.open(path) as im:
                    rgb=im.convert('RGB');data=rgb.tobytes()
                    gray=im.convert('L');bits=bytes(int(v<128) for v in gray.tobytes());width,height=im.size
                manifest.append(dict(split=split,image=path.name,width=width,height=height,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
                def record(scheme,payload,typ,encode,decode,expansion,kind,security,notes):
                    obj,enc=now_ms(lambda:encode(payload))
                    recovered,dec=now_ms(lambda:decode(obj))
                    rows.append(dict(split=split,image=path.name,repeat=r,scheme=scheme,payload_type=typ,input_bytes=len(payload),transmitted_bytes=expansion(obj),expansion_ratio=round(expansion(obj)/len(payload),6) if payload else None,encode_ms=round(enc,6),decode_ms=round(dec,6),exact=int(recovered==payload),reconstruction_type=kind,security_class=security,notes=notes))
                for r in range(args.repeats):
                    record('XOR_2of2',data,'RGB',xor_split,xor_join,lambda x:sum(map(len,x)),'exact_RGB','single_share_perfect_secrecy','No authentication; secure randomness')
                    record('Shamir_GF256_2of3',data,'RGB',shamir_2of3_split,lambda x:shamir_2of3_join({i:x[i] for i in (1,3)}),lambda x:sum(map(len,x.values())),'exact_RGB','threshold_secret_sharing','Prototype GF256; 2-of-3 recovery; share identifiers overhead excluded')
                    record('OR_2of2',bits,'binary',or_split,or_join,lambda x:sum(map(len,x)),'ideal_binary','visual_secret_sharing','Ideal contrast classification, not literal overlay')
                    # Random-grid overlay is deliberately NOT compared for exact recovery.
                    record('RandomGrid_OR_2of2',bits,'binary',random_grid_split,random_grid_visual_overlay,lambda x:sum(map(len,x)),'visual_overlay_nonexact','visual_secret_sharing','Exact metric is expected to be <1; evaluate contrast separately')
                    record('AES128_GCM_PSK',data,'RGB',aes_encrypt,lambda x:aes_decrypt(x[0]),lambda x:x[1],'exact_RGB_authenticated','authenticated_encryption','Pre-shared key; nonce+tag included; key distribution excluded')
                    record('X25519_HKDF_AES128_GCM',data,'RGB',hpke_like_encrypt,lambda x:hpke_like_decrypt(x[0]),lambda x:x[1],'exact_RGB_authenticated','authenticated_encryption','Custom educational envelope; NOT RFC 9180 HPKE')
                    record('AESGCM_XOR_Erasure_2of3',data,'RGB',encrypted_erasure_split,lambda x:encrypted_erasure_join(x[0],(0,2)),lambda x:x[1],'exact_RGB_authenticated','encrypted_erasure_transport','External PSK; 2-of-3 erasure tolerance; fragments not individually confidential')
            except Exception as exc:issues.append(f'{split}/{path.name}: {type(exc).__name__}: {exc}')
    write_csv(out/'33_01_runs.csv',rows,FIELDS)
    write_csv(out/'33_02_manifest.csv',manifest,['split','image','width','height','sha256'])
    groups={}
    for row in rows:groups.setdefault((row['split'],row['scheme']),[]).append(row)
    summary=[]
    for (split,scheme),items in sorted(groups.items()):
        summary.append(dict(split=split,scheme=scheme,runs=len(items),encode_median_ms=round(statistics.median(x['encode_ms'] for x in items),6),decode_median_ms=round(statistics.median(x['decode_ms'] for x in items),6),expansion_mean=round(statistics.mean(x['expansion_ratio'] for x in items),6),exact_fraction=round(statistics.mean(x['exact'] for x in items),6)))
    write_csv(out/'33_03_summary.csv',summary,['split','scheme','runs','encode_median_ms','decode_median_ms','expansion_mean','exact_fraction'])
    (out/'33_04_issues.txt').write_text('\n'.join(issues) if issues else 'No issues reported.\n',encoding='utf-8')
    metadata=dict(dataset=str(root),splits=splits,images=len(manifest),runs=len(rows),issues=len(issues),python=sys.version,platform=platform.platform(),method_count=7,security_notes=['Research prototype; do not deploy','No network, packet loss, adversarial testing or organizational controller','No GIS/HHO code modified or imported','Shamir prototype uses 2-of-3 GF256 with byte shares and does not authenticate shares','Random grid requires contrast evaluation; exact comparison is not a success criterion','X25519+HKDF+AES-GCM is NOT standardized HPKE','Encrypted erasure fragments are not individually confidential and key is external','All timings include Python overhead; do not infer intrinsic method superiority','Payloads are raw RGB bytes, not compressed JPEG sizes','Original held-out test split excluded unless explicitly opted in'])
    (out/'33_05_metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(out),'images':len(manifest),'runs':len(rows),'schemes':7,'issues':len(issues)},indent=2))

if __name__=='__main__':main()
