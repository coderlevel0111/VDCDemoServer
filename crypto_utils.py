"""Public P-256 key and base64url helpers shared by the mdoc demo."""
import base64
from cryptography.hazmat.primitives.asymmetric import ec


def b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode()


def unb64(value):
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


def jwk(key):
    numbers = key.public_key().public_numbers()
    return dict(kty='EC', crv='P-256', x=b64(numbers.x.to_bytes(32, 'big')), y=b64(numbers.y.to_bytes(32, 'big')))


def public(key):
    if key.get('kty') != 'EC' or key.get('crv') != 'P-256' or set(key) != {'kty', 'crv', 'x', 'y'}:
        raise ValueError('需要仅包含 kty/crv/x/y 的 P-256 公钥')
    x, y = unb64(key['x']), unb64(key['y'])
    if len(x) != 32 or len(y) != 32:
        raise ValueError('P-256 坐标必须为 32 字节')
    return ec.EllipticCurvePublicNumbers(int.from_bytes(x, 'big'), int.from_bytes(y, 'big'), ec.SECP256R1()).public_key()
