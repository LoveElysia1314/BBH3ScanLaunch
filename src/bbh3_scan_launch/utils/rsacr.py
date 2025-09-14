import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding


def rsacreate(message, public_key):
    """使用RSA公钥加密消息（PKCS#1 v1.5填充）"""
    # 加载公钥
    pub_key = serialization.load_pem_public_key(public_key.encode("utf-8"))

    # 使用PKCS1v15填充加密
    cipher_text = pub_key.encrypt(message.encode("utf-8"), padding.PKCS1v15())

    # 返回Base64编码的加密结果
    return base64.b64encode(cipher_text).decode("utf-8")
