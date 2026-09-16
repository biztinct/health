# -*- coding: utf-8 -*-
"""AES-256-GCM encryption for telephony credentials at rest.

Deliberately **self-contained**, for the same reason
``health_care_command_channels/services/channel_crypto.py`` is: it clones the
*recipe* (same root-key sources, same HKDF/AES-GCM construction) but shares no
code and derives a DIFFERENT subkey (``info=b'health19-voip-secret-v1'``). A
SIP password therefore cannot be decrypted with the PHI key or the channel key
and vice versa, and this module carries **no dependency on either addon**.

Why core owns a cipher of its own rather than borrowing the Channel Center's:
the handover asks for "narrow overridable secret access methods that fail
closed when a secure store is unavailable", with the Channels implementation in
the bridge. Taken literally that leaves a standalone ``health_voip24h`` with no
credential storage at all, i.e. with every credential-dependent feature dead.
The intent behind the rule is (a) encrypted at rest, (b) never a plaintext
fallback, (c) an acyclic dependency graph (ledger §5.71). A core-owned,
independently-keyed cipher satisfies all three while keeping the module usable
alone, so that is what ships. ``voip.config._voip_secret_backend()`` remains
overridable, and ``health_care_command_voip`` points it at the connection store
where a Channel Center owns the setup.

Token format (stored in ``*_enc`` columns)::

    vps$1$<base64(nonce || ciphertext || tag)>

Key material, in order of precedence:

1. ``HEALTH_PHI_KEY`` environment variable — base64, >= 32 bytes decoded.
   Shared *root*, separate subkey (platform-operator checklist §12.9).
2. HKDF from the ``database.secret`` system parameter.

``decrypt()`` RAISES ``ValueError`` on a corrupt or foreign token. A silently
mangled SIP password would register nothing and look like a provider outage;
a loud failure is the only honest answer. Values *without* the prefix pass
through unchanged, which is the migration tolerance that lets a legacy
plaintext column be read once and re-written encrypted.
"""
import base64
import logging
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

_logger = logging.getLogger(__name__)

TOKEN_PREFIX = 'vps$1$'
_HKDF_INFO = b'health19-voip-secret-v1'
_HKDF_SALT = b'health19-phi'          # same salt family, distinct info

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
                'database.secret is not set; cannot derive the telephony key')
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
    """Encrypt ``plaintext`` (str) -> token.

    Falsy / non-str values pass through unchanged; already-encrypted tokens are
    returned as-is (idempotent, so a re-run of a migration cannot double-wrap).
    """
    if not plaintext or not isinstance(plaintext, str) or is_encrypted(plaintext):
        return plaintext
    nonce = os.urandom(12)
    ct = AESGCM(_get_key(env)).encrypt(nonce, plaintext.encode('utf-8'), None)
    return TOKEN_PREFIX + base64.b64encode(nonce + ct).decode('ascii')


def decrypt(env, token):
    """Decrypt a ``vps$1$`` token -> plaintext.

    Values without the prefix pass through unchanged (migration tolerance).
    A prefixed value that fails to decrypt RAISES ``ValueError`` — never a
    marker, never a silent empty string.
    """
    if not is_encrypted(token):
        return token
    try:
        raw = base64.b64decode(token[len(TOKEN_PREFIX):])
        return AESGCM(_get_key(env)).decrypt(raw[:12], raw[12:], None).decode('utf-8')
    except Exception as exc:  # noqa: BLE001 — re-raised as ValueError below
        # No secret material in the log line — only the failure fact.
        _logger.error('Telephony secret decryption failed (db=%s): %s',
                      env.cr.dbname, type(exc).__name__)
        raise ValueError('Telephony secret could not be decrypted') from exc
