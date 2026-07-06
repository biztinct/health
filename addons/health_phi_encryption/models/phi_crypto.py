# -*- coding: utf-8 -*-
"""AES-256-GCM helpers for transparent PHI field encryption.

Token format (stored in ``*_enc`` columns)::

    enc$1$<base64(nonce || ciphertext || tag)>

Values without the ``enc$`` prefix are passed through unchanged, so plaintext
written before migration (or by direct SQL) never breaks reads.

Key material, in order of precedence:

1. ``HEALTH_PHI_KEY`` environment variable — base64-encoded 32 bytes.
   Use this in production so the key lives outside the database host backup.
2. Derived (HKDF-SHA256) from the ``database.secret`` system parameter.

The blind-index key is derived separately from the same root so that the
index values cannot be used to decrypt.
"""
import base64
import hashlib
import hmac
import logging
import os
import re

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

_logger = logging.getLogger(__name__)

PREFIX = 'enc$1$'
DECRYPT_ERROR_MARKER = '*** PHI decryption error — check HEALTH_PHI_KEY ***'

# Per-database key cache: {dbname: (aes_key, bidx_key)}
_KEY_CACHE = {}


def _derive(root: bytes, info: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=b'health19-phi',
                info=info).derive(root)


def _get_keys(env):
    dbname = env.cr.dbname
    keys = _KEY_CACHE.get(dbname)
    if keys:
        return keys
    env_key = os.environ.get('HEALTH_PHI_KEY')
    if env_key:
        root = base64.b64decode(env_key)
        if len(root) < 32:
            raise ValueError('HEALTH_PHI_KEY must decode to at least 32 bytes')
    else:
        secret = env['ir.config_parameter'].sudo().get_param('database.secret')
        if not secret:
            raise ValueError('database.secret is not set; cannot derive PHI key')
        root = secret.encode()
    keys = (_derive(root, b'health19-phi-aes-v1'),
            _derive(root, b'health19-phi-bidx-v1'))
    _KEY_CACHE[dbname] = keys
    return keys


def clear_key_cache(dbname=None):
    if dbname:
        _KEY_CACHE.pop(dbname, None)
    else:
        _KEY_CACHE.clear()


def is_encrypted(value) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


def encrypt(env, plaintext):
    """Encrypt ``plaintext`` (str) → token. Falsy values pass through unchanged.
    Already-encrypted tokens are returned as-is (idempotent)."""
    if not plaintext or not isinstance(plaintext, str) or is_encrypted(plaintext):
        return plaintext
    aes_key, _ = _get_keys(env)
    nonce = os.urandom(12)
    ct = AESGCM(aes_key).encrypt(nonce, plaintext.encode('utf-8'), None)
    return PREFIX + base64.b64encode(nonce + ct).decode('ascii')


def decrypt(env, token):
    """Decrypt token → plaintext. Non-token values pass through unchanged.
    On key mismatch/corruption returns a visible marker instead of raising,
    so a wrong key never makes every patient form error out."""
    if not is_encrypted(token):
        return token
    try:
        aes_key, _ = _get_keys(env)
        raw = base64.b64decode(token[len(PREFIX):])
        return AESGCM(aes_key).decrypt(raw[:12], raw[12:], None).decode('utf-8')
    except Exception:
        _logger.exception('PHI decryption failed (db=%s)', env.cr.dbname)
        return DECRYPT_ERROR_MARKER


def normalize_identifier(value: str) -> str:
    """Normalization applied before blind-indexing identity numbers:
    keep alphanumerics only, lowercase (CCCD/CMND are digits; passports may
    carry letters)."""
    return re.sub(r'[^0-9a-z]', '', (value or '').lower())


def blind_index(env, value):
    """HMAC-SHA256 hex digest of the normalized value, for exact-match search."""
    norm = normalize_identifier(value)
    if not norm:
        return False
    _, bidx_key = _get_keys(env)
    return hmac.new(bidx_key, norm.encode('utf-8'), hashlib.sha256).hexdigest()
