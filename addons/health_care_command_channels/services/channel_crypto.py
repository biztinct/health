# -*- coding: utf-8 -*-
"""AES-256-GCM encryption for channel credentials at rest (architecture §7.1).

Token format (stored in ``*_enc`` columns)::

    chs$1$<base64(nonce || ciphertext || tag)>

Deliberately **self-contained**: this module clones the *recipe* of
``health_phi_encryption/models/phi_crypto.py`` (same root-key sources, same
HKDF/AES-GCM construction) but shares no code and derives a DIFFERENT subkey
(``info=b'health19-channel-secret-v1'``). A channel token therefore cannot be
decrypted with the PHI key and vice versa, and this module carries no
dependency on health_phi_encryption.

Two deliberate divergences from phi_crypto:

* ``decrypt()`` **RAISES** ``ValueError`` on a corrupt/foreign token instead of
  returning a visible marker string. phi_crypto's marker keeps a patient form
  rendering; here the value is a provider credential — a silently mangled
  secret sent to WhatsApp/Zalo is far worse than a loud failure.
* Values *without* the prefix pass through ``decrypt()`` unchanged (migration
  tolerance for legacy plaintext copied in from ``zalo.config``/``voip.config``
  in CC-D/CC-F).

Key material, in order of precedence:

1. ``HEALTH_PHI_KEY`` environment variable — base64, ≥32 bytes decoded. Shared
   *root*, separate subkey (platform-operator checklist §12.9).
2. HKDF from the ``database.secret`` system parameter.
"""
import base64
import logging
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

_logger = logging.getLogger(__name__)

TOKEN_PREFIX = 'chs$1$'
_HKDF_INFO = b'health19-channel-secret-v1'
_HKDF_SALT = b'health19-phi'          # same salt family as phi_crypto, distinct info

# Per-database key cache: {dbname: aes_key}
_KEY_CACHE = {}


def _derive(root: bytes, info: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=_HKDF_SALT,
                info=info).derive(root)


def _get_key(env):
    dbname = env.cr.dbname
    key = _KEY_CACHE.get(dbname)
    if key:
        return key
    env_key = os.environ.get('HEALTH_PHI_KEY')
    if env_key:
        root = base64.b64decode(env_key)
        if len(root) < 32:
            raise ValueError('HEALTH_PHI_KEY must decode to at least 32 bytes')
    else:
        secret = env['ir.config_parameter'].sudo().get_param('database.secret')
        if not secret:
            raise ValueError(
                'database.secret is not set; cannot derive the channel key')
        root = secret.encode()
    key = _derive(root, _HKDF_INFO)
    _KEY_CACHE[dbname] = key
    return key


def clear_key_cache(dbname=None):
    if dbname:
        _KEY_CACHE.pop(dbname, None)
    else:
        _KEY_CACHE.clear()


def is_encrypted(value) -> bool:
    return isinstance(value, str) and value.startswith(TOKEN_PREFIX)


def encrypt(env, plaintext):
    """Encrypt ``plaintext`` (str) → token. Falsy / non-str values pass through
    unchanged; already-encrypted tokens are returned as-is (idempotent)."""
    if not plaintext or not isinstance(plaintext, str) or is_encrypted(plaintext):
        return plaintext
    nonce = os.urandom(12)
    ct = AESGCM(_get_key(env)).encrypt(nonce, plaintext.encode('utf-8'), None)
    return TOKEN_PREFIX + base64.b64encode(nonce + ct).decode('ascii')


def decrypt(env, token):
    """Decrypt a ``chs$1$`` token → plaintext.

    Values without the prefix pass through unchanged (migration tolerance).
    A prefixed value that fails to decrypt RAISES ``ValueError`` — never a
    marker, never a silent empty string.
    """
    if not is_encrypted(token):
        return token
    try:
        raw = base64.b64decode(token[len(TOKEN_PREFIX):])
        return AESGCM(_get_key(env)).decrypt(raw[:12], raw[12:], None).decode('utf-8')
    except Exception as exc:
        # No secret material in the log line — only the failure fact.
        _logger.error('Channel secret decryption failed (db=%s): %s',
                      env.cr.dbname, type(exc).__name__)
        raise ValueError('Channel secret could not be decrypted') from exc
