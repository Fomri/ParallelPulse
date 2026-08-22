"""
For this POC, we use a single shared static key via the "cryptography" library's Fernet,
since the POC's purpose is only to prove the bandwidth based allocation logic,
not the key exchange protocol.
"""

from cryptography.fernet import Fernet


# this key is permanent only for the POC, in the real project, a new key will be created for each interaction between peers
_SHARED_KEY = b'ZWJfl754rhfrd33Wpf1t6TbV6saKn3cUtay4ahGmpcI='
_fernet = Fernet(_SHARED_KEY)


def encrypt_chunk(data):
    # returns a base64 encoded encrypted string, safe to send inside JSON
    return _fernet.encrypt(data.encode('utf-8')).decode('utf-8')


def decrypt_chunk(data):
    return _fernet.decrypt(data.encode('utf-8')).decode('utf-8')