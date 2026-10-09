import base64,json,unittest
from cryptography.hazmat.primitives.asymmetric import rsa,padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from foundation.staging.encrypted_backup import encrypt
class EncryptionTests(unittest.TestCase):
    def test_envelope_roundtrip_and_tamper_rejection_with_ephemeral_test_key(self):
        private=rsa.generate_private_key(public_exponent=65537,key_size=3072);pub=private.public_key().public_numbers()
        encode=lambda n:base64.urlsafe_b64encode(n.to_bytes((n.bit_length()+7)//8,'big')).decode().rstrip('=')
        raw=b'{"isolated_test":true}';out=encrypt(raw,{'kty':'RSA','n':encode(pub.n),'e':encode(pub.e)})
        b=lambda k:base64.b64decode(out[k]);key=private.decrypt(b('wrapped_key'),padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
        self.assertEqual(AESGCM(key).decrypt(b('nonce'),b('ciphertext'),b('aad')),raw)
        with self.assertRaises(Exception):AESGCM(key).decrypt(b('nonce'),b('ciphertext')[:-1]+b'X',b('aad'))
        with self.assertRaises(ValueError):encrypt(raw,{'kty':'RSA','d':'do not accept private keys'})
if __name__=='__main__':unittest.main()
