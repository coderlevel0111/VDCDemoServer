"""Bounded local ISO mdoc / org-iso-mdoc profile. Fictional mDL subset, pinned lab PKI.
Not a production ISO conformance implementation. See docs for supported subset.
"""
import datetime as dt, hashlib, hmac, secrets, time, uuid
from pathlib import Path
import cbor2 as cbor
from cryptography import x509
from cryptography.x509.oid import NameOID, ObjectIdentifier
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand
from crypto_utils import b64, unb64, jwk, public

DOCTYPE='org.iso.18013.5.1.mDL'
NS='org.iso.18013.5.1'
# Restricted fictional test subset, not a complete ISO mDL or a real driving licence.
CLAIMS={'given_name':'DEMO ONLY','family_name':'NOT A REAL LICENCE','age_over_18':True}
def enc(x): return cbor.dumps(x)
def dec(x):
    if len(x)>131072: raise ValueError('CBOR too large')
    import io
    f=io.BytesIO(x); value=cbor.load(f)
    if f.read(): raise ValueError('CBOR trailing bytes')
    return value
def tagged(x): return cbor.CBORTag(24,enc(x))
def pub_cose(key):
    j=jwk(key); return {1:2,-1:1,-2:unb64(j['x']),-3:unb64(j['y'])}
def cose_public(key):
    if key[1]!=2 or key[-1]!=1: raise ValueError('COSE P-256 required')
    return ec.EllipticCurvePublicNumbers(int.from_bytes(key[-2],'big'),int.from_bytes(key[-3],'big'),ec.SECP256R1()).public_key()
def cose_sign(key,payload,cert=None,detached=False):
    protected=enc({1:-7}); sig=key.sign(enc(['Signature1',protected,b'',payload]),ec.ECDSA(hashes.SHA256()))
    r,s=utils.decode_dss_signature(sig)
    return [protected,({33:cert} if cert else {}),None if detached else payload,r.to_bytes(32,'big')+s.to_bytes(32,'big')]
def cose_verify(obj,key,payload=None):
    if isinstance(obj,cbor.CBORTag): obj=obj.value
    protected,unprotected,attached,raw=obj
    if dec(protected)!={1:-7} or len(raw)!=64: raise ValueError('COSE algorithm/signature mismatch')
    if payload is not None and attached is not None: raise ValueError('Detached payload required')
    key.verify(utils.encode_dss_signature(int.from_bytes(raw[:32],'big'),int.from_bytes(raw[32:],'big')),enc(['Signature1',protected,b'',attached if payload is None else payload]),ec.ECDSA(hashes.SHA256()))
    return attached

def certificate(directory,label,parent=None,eku=None):
    directory=Path(directory); keyfile=directory/(label+'.key'); certfile=directory/(label+'.der')
    if keyfile.exists() and certfile.exists():
        return serialization.load_pem_private_key(keyfile.read_bytes(),None),x509.load_der_x509_certificate(certfile.read_bytes())
    key=ec.generate_private_key(ec.SECP256R1()); now=dt.datetime.now(dt.timezone.utc)
    name=x509.Name([x509.NameAttribute(NameOID.COUNTRY_NAME,'CN'),x509.NameAttribute(NameOID.COMMON_NAME,'VDC LOCAL TEST '+label)])
    root=parent is None; signer=key if root else parent[0]
    builder=x509.CertificateBuilder().subject_name(name).issuer_name(name if root else parent[1].subject).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-dt.timedelta(minutes=5)).not_valid_after(now+dt.timedelta(days=365)).add_extension(x509.BasicConstraints(ca=root,path_length=0 if root else None),True).add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),False).add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(signer.public_key()),False).add_extension(x509.KeyUsage(digital_signature=True,content_commitment=False,key_encipherment=False,data_encipherment=False,key_agreement=False,key_cert_sign=root,crl_sign=root,encipher_only=None,decipher_only=None),True)
    if eku: builder=builder.add_extension(x509.ExtendedKeyUsage([ObjectIdentifier(eku)]),True)
    cert=builder.sign(signer,hashes.SHA256()); keyfile.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));keyfile.chmod(0o600);certfile.write_bytes(cert.public_bytes(serialization.Encoding.DER));return key,cert

def extract(salt,ikm): return hmac.new(salt or bytes(32),ikm,hashlib.sha256).digest()
def lextract(salt,suite,label,ikm): return extract(salt,b'HPKE-v1'+suite+label+ikm)
def lexpand(prk,suite,label,info,length): return HKDFExpand(algorithm=hashes.SHA256(),length=length,info=length.to_bytes(2,'big')+b'HPKE-v1'+suite+label+info).derive(prk)
def hpke_keys(dh,kem_context,info):
    kem=b'KEM'+(0x10).to_bytes(2,'big'); suite=b'HPKE'+bytes.fromhex('001000010001')
    eae=lextract(b'',kem,b'eae_prk',dh); shared=lexpand(eae,kem,b'shared_secret',kem_context,32)
    context=b'\x00'+lextract(b'',suite,b'psk_id_hash',b'')+lextract(b'',suite,b'info_hash',info)
    secret=lextract(shared,suite,b'secret',b'')
    return lexpand(secret,suite,b'key',context,16),lexpand(secret,suite,b'base_nonce',context,12)
def public_bytes(key): return key.public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
def hpke_open(key,encap,cipher,info,aad=b''):
    sender=ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(),encap)
    k,n=hpke_keys(key.exchange(ec.ECDH(),sender),encap+public_bytes(key.public_key()),info)
    return AESGCM(k).decrypt(n,cipher,aad)
def hpke_seal(key,plain,info):
    ephemeral=ec.generate_private_key(ec.SECP256R1()); e=public_bytes(ephemeral.public_key())
    k,n=hpke_keys(ephemeral.exchange(ec.ECDH(),key),e+public_bytes(key),info)
    return e,AESGCM(k).encrypt(n,plain,b'')
def transcript(encryption_info,origin): return [None,None,['dcapi',hashlib.sha256(enc([encryption_info,origin])).digest()]]
def date_tag(stamp): return cbor.CBORTag(0,dt.datetime.fromtimestamp(stamp,dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))

class MDocLab:
    def __init__(self,directory,db,origin):
        self.db=db;self.origin=origin.rstrip('/'); directory=Path(directory)/'mdoc';directory.mkdir(parents=True,exist_ok=True)
        self.iaca=certificate(directory,'IACA'); self.ds=certificate(directory,'DocumentSigner',self.iaca,'1.0.18013.5.1.2')
        self.reader_ca=certificate(directory,'ReaderCA');self.reader=certificate(directory,'Reader',self.reader_ca,'1.0.18013.5.1.6')
        self.db.executescript('CREATE TABLE IF NOT EXISTS mdoc_cards(id TEXT PRIMARY KEY, expires INTEGER, revoked INTEGER, secret TEXT); CREATE TABLE IF NOT EXISTS mdoc_requests(id TEXT PRIMARY KEY, origin TEXT, encryption_info TEXT, recipient BLOB, expires INTEGER, used INTEGER);')
    def config(self):
        der=lambda cert:b64(cert.public_bytes(serialization.Encoding.DER))
        return dict(doc_type=DOCTYPE,namespace=NS,origin=self.origin,issuer_root=der(self.iaca[1]),reader_root=der(self.reader_ca[1]),reader_key_id=b64(self.reader_ca[1].extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value.digest),issuer_fingerprint=b64(self.iaca[1].fingerprint(hashes.SHA256())),reader_fingerprint=b64(self.reader_ca[1].fingerprint(hashes.SHA256())))
    def issue(self,b):
        holder=public(b['holder_jwk']); n=holder.public_numbers();now=int(time.time());ident=str(uuid.uuid4());secret=secrets.token_urlsafe(32)
        items=[];digests={}
        for index,(name,value) in enumerate(dict(CLAIMS,document_number=ident).items()):
            item=tagged(dict(digestID=index,random=secrets.token_bytes(32),elementIdentifier=name,elementValue=value))
            items.append(item);digests[index]=hashlib.sha256(enc(item)).digest()
        mso=dict(version='1.0',digestAlgorithm='SHA-256',valueDigests={NS:digests},deviceKeyInfo=dict(deviceKey={1:2,-1:1,-2:n.x.to_bytes(32,'big'),-3:n.y.to_bytes(32,'big')}),docType=DOCTYPE,validityInfo=dict(signed=date_tag(now),validFrom=date_tag(now-2),validUntil=date_tag(now+3600)))
        auth=cose_sign(self.ds[0],enc(tagged(mso)),self.ds[1].public_bytes(serialization.Encoding.DER))
        issuer_signed=dict(nameSpaces={NS:items},issuerAuth=auth)
        self.db.execute('INSERT INTO mdoc_cards VALUES(?,?,0,?)',(ident,now+3600,secret));self.db.commit()
        return dict(issuer_signed=b64(enc(issuer_signed)),document_id=ident,expires_at=now+3600,revoke_token=secret)
    def request(self,b):
        if b.get('origin')!=self.origin: raise ValueError('网页 origin 与 --origin 配置不一致')
        self.db.execute('DELETE FROM mdoc_requests WHERE expires <= ?', (int(time.time()),))
        key=ec.generate_private_key(ec.SECP256R1());ei=b64(enc(['dcapi',dict(nonce=secrets.token_bytes(32),recipientPublicKey=pub_cose(key))]));st=transcript(ei,self.origin)
        items=tagged(dict(docType=DOCTYPE,nameSpaces={NS:dict(age_over_18=False,document_number=False)}))
        reader_auth=enc(tagged(['ReaderAuthentication',st,items]))
        auth=cose_sign(self.reader[0],reader_auth,self.reader[1].public_bytes(serialization.Encoding.DER),True)
        auth[1][33]=[self.reader[1].public_bytes(serialization.Encoding.DER),self.reader_ca[1].public_bytes(serialization.Encoding.DER)]
        device_request=dict(version='1.0',docRequests=[dict(itemsRequest=items,readerAuth=auth)])
        ident=secrets.token_urlsafe(24); private=key.private_numbers().private_value.to_bytes(32,'big')
        self.db.execute('INSERT INTO mdoc_requests VALUES(?,?,?,?,?,0)',(ident,self.origin,ei,private,int(time.time())+120));self.db.commit()
        return dict(id=ident,protocol='org-iso-mdoc',data=dict(deviceRequest=b64(enc(device_request)),encryptionInfo=ei),expires_in=120)
    def verify(self,b):
        row=self.db.execute('SELECT origin,encryption_info,recipient,expires,used FROM mdoc_requests WHERE id=?',(b['id'],)).fetchone()
        if not row: raise ValueError('未知请求')
        origin,ei,raw,expiry,used=row
        if used: raise ValueError('REPLAY：系统出示请求已消费')
        if time.time()>=expiry: raise ValueError('系统出示请求过期')
        envelope=dec(unb64(b['response']))
        if envelope[0]!='dcapi': raise ValueError('不是 dcapi 响应')
        st=transcript(ei,origin); recipient=ec.derive_private_key(int.from_bytes(raw,'big'),ec.SECP256R1())
        response=dec(hpke_open(recipient,envelope[1]['enc'],envelope[1]['cipherText'],enc(st)))
        if response.get('status')!=0 or len(response.get('documents',[]))!=1: raise ValueError('文档响应状态或数量错误')
        doc=response['documents'][0]
        if doc['docType']!=DOCTYPE: raise ValueError('文档类型不匹配')
        signed=doc['issuerSigned'];auth=signed['issuerAuth'];cert=auth[1][33]
        # This teaching trust domain accepts exactly the configured signer certificate.
        if cert!=self.ds[1].public_bytes(serialization.Encoding.DER): raise ValueError('不可信文档签名证书')
        mso_tag=dec(cose_verify(auth,self.ds[1].public_key()));mso=dec(mso_tag.value)
        if mso['docType']!=DOCTYPE or mso['digestAlgorithm']!='SHA-256': raise ValueError('MSO 格式不匹配')
        def timestamp(value):
            if isinstance(value,dt.datetime):return value.timestamp()
            return dt.datetime.fromisoformat(value.value.replace('Z','+00:00')).timestamp()
        if not timestamp(mso['validityInfo']['validFrom'])<=time.time()<timestamp(mso['validityInfo']['validUntil']): raise ValueError('mdoc 已过期')
        fields={};seen=set()
        if set(signed['nameSpaces'])!={NS}:raise ValueError('未知 namespace')
        for item in signed['nameSpaces'][NS]:
            v=dec(item.value);index=v['digestID'];name=v['elementIdentifier']
            if index in seen or name in fields:raise ValueError('重复属性')
            if hashlib.sha256(enc(item)).digest()!=mso['valueDigests'][NS][index]:raise ValueError('属性摘要错误')
            seen.add(index);fields[name]=v['elementValue']
        if set(fields)!={'age_over_18','document_number'}:raise ValueError('缺少请求属性或披露额外字段')
        if fields['age_over_18'] is not True:raise ValueError('不满足已满 18 岁的演示政策')
        card=self.db.execute('SELECT expires,revoked FROM mdoc_cards WHERE id=?',(fields['document_number'],)).fetchone()
        if not card or card[1] or card[0]<=time.time(): raise ValueError('REVOKED：mdoc 已撤销或未知')
        device=doc['deviceSigned'];namespaces=device['nameSpaces']
        if namespaces!=tagged({}):raise ValueError('不支持额外设备声明')
        device_auth=enc(tagged(['DeviceAuthentication',st,DOCTYPE,namespaces]))
        cose_verify(device['deviceAuth']['deviceSignature'],cose_public(mso['deviceKeyInfo']['deviceKey']),device_auth)
        self.db.execute('UPDATE mdoc_requests SET used=1, recipient=? WHERE id=?',(b'', b['id']));self.db.commit()
        return dict(ok=True,message='mDL 测试凭证验证通过',disclosed=fields,checks=['HPKE 解密 / origin 与 nonce 绑定','受信任发行签名','MSO 属性摘要','文档有效期','设备签名持钥证明','撤销与年龄演示政策','一次性请求'],profile='org-iso-mdoc / fictional mDL subset')
    def revoke(self,b):
        row=self.db.execute('SELECT secret FROM mdoc_cards WHERE id=?',(b['id'],)).fetchone()
        if not row or not hmac.compare_digest(row[0],b['revoke_token']):raise ValueError('撤销授权错误')
        self.db.execute('UPDATE mdoc_cards SET revoked=1 WHERE id=?',(b['id'],));self.db.commit();return dict(ok=True)
