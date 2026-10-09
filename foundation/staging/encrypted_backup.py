"""Offline envelope encryption. Requires the OWNER'S browser-generated public key.
No private key generation, upload, secret logging or remote storage access.
"""
import base64,hashlib,json,secrets
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa,padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def decode(s):return base64.urlsafe_b64decode(s+'='*((-len(s))%4))
def encrypt(raw,public_jwk):
    if public_jwk.get('kty')!='RSA' or 'd' in public_jwk:raise ValueError('Provide only a public RSA encryption key')
    key=rsa.RSAPublicNumbers(int.from_bytes(decode(public_jwk['e']),'big'),int.from_bytes(decode(public_jwk['n']),'big')).public_key()
    if key.key_size<3072:raise ValueError('A 3072-bit or stronger public key is required')
    metadata={'format':'wantlist-encrypted-backup-v1','plaintext_sha256':hashlib.sha256(raw).hexdigest(),'key_fingerprint':hashlib.sha256(json.dumps(public_jwk,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
    aad=json.dumps(metadata,sort_keys=True,separators=(',',':')).encode();aes=secrets.token_bytes(32);nonce=secrets.token_bytes(12)
    b64=lambda b:base64.b64encode(b).decode()
    return {'metadata':metadata,'aad':b64(aad),'nonce':b64(nonce),'wrapped_key':b64(key.encrypt(aes,padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))),'ciphertext':b64(AESGCM(aes).encrypt(nonce,raw,aad))}

def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--snapshot',required=True);p.add_argument('--public-key',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    snapshot=Path(a.snapshot);raw=snapshot.read_bytes();data=json.loads(raw)
    from .readiness_audit import restore_snapshot
    restored=restore_snapshot(data);restored.close()
    encrypted=encrypt(raw,json.loads(Path(a.public_key).read_text()));out=Path(a.output)
    with out.open('x',encoding='utf-8') as f:out.chmod(0o600);json.dump(encrypted,f,separators=(',',':'))
    print(json.dumps({'encrypted':True,'plaintext_restore_verified':True,'encrypted_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'upload_performed':False,'durable_storage_verified':False}))
if __name__=='__main__':main()
