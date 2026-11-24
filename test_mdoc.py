import json, sqlite3, tempfile, unittest
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ec
from crypto_utils import jwk, b64, unb64
from mdoc import MDocLab, NS, DOCTYPE, enc, dec, tagged, cose_sign, hpke_seal, hpke_open, transcript
class MDocTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=sqlite3.connect(':memory:');self.lab=MDocLab(self.tmp.name,self.db,'https://127.0.0.1:8443');self.key=ec.generate_private_key(ec.SECP256R1());self.card=self.lab.issue({'holder_jwk':jwk(self.key)})
    def tearDown(self):self.db.close();self.tmp.cleanup()
    def response(self,*,wrong_key=False,wrong_origin=False,tamper=False,extra=False):
        req=self.lab.request({'origin':self.lab.origin});ei=dec(unb64(req['data']['encryptionInfo']));st=transcript(req['data']['encryptionInfo'],'https://evil.invalid' if wrong_origin else self.lab.origin)
        signed=dec(unb64(self.card['issuer_signed']));selected=[]
        for item in signed['nameSpaces'][NS]:
            v=dec(item.value)
            if v['elementIdentifier']=='name' and not extra:continue
            if tamper and v['elementIdentifier']=='role':v['elementValue']='administrator';item=tagged(v)
            selected.append(item)
        signed['nameSpaces'][NS]=selected;empty=tagged({});auth=enc(tagged(['DeviceAuthentication',st,DOCTYPE,empty]))
        signature=cose_sign(ec.generate_private_key(ec.SECP256R1()) if wrong_key else self.key,auth,detached=True)
        plain=enc(dict(version='1.0',documents=[dict(docType=DOCTYPE,issuerSigned=signed,deviceSigned=dict(nameSpaces=empty,deviceAuth=dict(deviceSignature=signature)))],status=0))
        from mdoc import cose_public
        e,c=hpke_seal(cose_public(ei[1]['recipientPublicKey']),plain,enc(st));return dict(id=req['id'],response=b64(enc(['dcapi',dict(enc=e,cipherText=c)])))
    def test_success_selective_disclosure_and_replay(self):
        r=self.response();result=self.lab.verify(r);self.assertNotIn('name',result['disclosed']);self.assertTrue(result['ok'])
        self.assertEqual(self.db.execute('SELECT recipient FROM mdoc_requests WHERE id=?',(r['id'],)).fetchone()[0], b'')
        with self.assertRaisesRegex(ValueError,'REPLAY'):self.lab.verify(r)
    def test_wrong_device_key(self):
        with self.assertRaises(Exception):self.lab.verify(self.response(wrong_key=True))
    def test_wrong_origin(self):
        with self.assertRaises(Exception):self.lab.verify(self.response(wrong_origin=True))
    def test_tampered_attribute(self):
        with self.assertRaisesRegex(ValueError,'摘要'):self.lab.verify(self.response(tamper=True))
    def test_excess_disclosure(self):
        with self.assertRaisesRegex(ValueError,'额外'):self.lab.verify(self.response(extra=True))
    def test_revoked(self):
        self.lab.revoke({'id':self.card['document_id'],'revoke_token':self.card['revoke_token']})
        with self.assertRaisesRegex(ValueError,'REVOKED'):self.lab.verify(self.response())
    def test_expired_request(self):
        r=self.response();self.db.execute('UPDATE mdoc_requests SET expires=0 WHERE id=?',(r['id'],));self.db.commit()
        with self.assertRaisesRegex(ValueError,'过期'):self.lab.verify(r)
    def test_wrong_request_origin(self):
        with self.assertRaisesRegex(ValueError,'origin'):self.lab.request({'origin':'https://evil.invalid'})
    def test_rfc9180_p256_vector(self):
        v=json.loads((Path(__file__).parent/'tests/fixtures/rfc9180-p256.json').read_text());e=v['encryptions'][0]
        key=ec.derive_private_key(int(v['skRm'],16),ec.SECP256R1())
        self.assertEqual(hpke_open(key,bytes.fromhex(v['enc']),bytes.fromhex(e['ct']),bytes.fromhex(v['info']),bytes.fromhex(e['aad'])),bytes.fromhex(e['pt']))
if __name__=='__main__':unittest.main(verbosity=2)
