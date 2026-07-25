# -*- coding: utf-8 -*-
"""T70–T72 — the channel secret layer.

Written and run BEFORE any model exists in the design order of the handover:
if this layer is wrong, every credential in the system is wrong.
"""
import base64

from odoo.tests import TransactionCase, tagged

from odoo.addons.health_care_command_channels.services import channel_crypto


@tagged('post_install', '-at_install')
class TestChannelCrypto(TransactionCase):

    # ------------------------------------------------------------------
    # T70 — roundtrip, idempotence, passthrough
    # ------------------------------------------------------------------
    def test_70_roundtrip(self):
        plaintext = 'zalo-oa-access-token-ĐĂNG-NHẬP-9f3a'
        token = channel_crypto.encrypt(self.env, plaintext)

        self.assertTrue(token.startswith(channel_crypto.TOKEN_PREFIX))
        self.assertTrue(channel_crypto.is_encrypted(token))
        self.assertNotIn(plaintext, token)
        self.assertEqual(channel_crypto.decrypt(self.env, token), plaintext)

        # Idempotent: encrypting a token again returns it untouched.
        self.assertEqual(channel_crypto.encrypt(self.env, token), token)

        # Falsy / non-str values pass straight through.
        for value in (False, '', None, 0, 17):
            self.assertEqual(channel_crypto.encrypt(self.env, value), value)

        # Two encryptions of the same plaintext differ (fresh nonce each time).
        self.assertNotEqual(channel_crypto.encrypt(self.env, plaintext),
                            channel_crypto.encrypt(self.env, plaintext))

    # ------------------------------------------------------------------
    # T71 — tamper detection is LOUD (the phi_crypto divergence)
    # ------------------------------------------------------------------
    def test_71_tamper_raises(self):
        token = channel_crypto.encrypt(self.env, 'bot-token-4242')
        raw = bytearray(base64.b64decode(token[len(channel_crypto.TOKEN_PREFIX):]))
        raw[-1] ^= 0x01          # flip one bit of the GCM tag
        tampered = channel_crypto.TOKEN_PREFIX + base64.b64encode(bytes(raw)).decode()

        with self.assertRaises(ValueError):
            channel_crypto.decrypt(self.env, tampered)

        # Base64 garbage behind a valid prefix is equally fatal.
        with self.assertRaises(ValueError):
            channel_crypto.decrypt(self.env, channel_crypto.TOKEN_PREFIX + '!!!not-b64')

        # A value that was never encrypted passes through unchanged — this is
        # the migration tolerance for plaintext copied in from zalo.config.
        self.assertEqual(channel_crypto.decrypt(self.env, 'legacy-plaintext'),
                         'legacy-plaintext')
        self.assertEqual(channel_crypto.decrypt(self.env, False), False)

    # ------------------------------------------------------------------
    # T72 — the channel subkey is NOT the PHI subkey
    # ------------------------------------------------------------------
    def test_72_key_isolation_from_phi(self):
        try:
            from odoo.addons.health_phi_encryption.models import phi_crypto
        except ImportError:
            self.skipTest('health_phi_encryption is not installed')

        secret = 'shared-root-different-subkey'

        # A channel token, re-labelled as a PHI token, must NOT decrypt: same
        # root key material, different HKDF info ⇒ different AES key.
        chs = channel_crypto.encrypt(self.env, secret)
        as_phi = phi_crypto.PREFIX + chs[len(channel_crypto.TOKEN_PREFIX):]
        self.assertEqual(phi_crypto.decrypt(self.env, as_phi),
                         phi_crypto.DECRYPT_ERROR_MARKER)

        # ...and the other way round, where OUR layer raises instead of
        # returning a marker.
        phi = phi_crypto.encrypt(self.env, secret)
        as_chs = channel_crypto.TOKEN_PREFIX + phi[len(phi_crypto.PREFIX):]
        with self.assertRaises(ValueError):
            channel_crypto.decrypt(self.env, as_chs)
