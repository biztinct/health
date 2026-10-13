import io
import os
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from .. import backup_crypto as crypto


class TestBackupCrypto(unittest.TestCase):
    def test_roundtrip_large_empty_and_authentication(self):
        with tempfile.TemporaryDirectory() as directory:
            for payload in (b'', b'Synthetic private clinical backup' * 70000):
                source, sealed, restored = [os.path.join(directory, n) for n in ('src','sealed','restored')]
                with open(source,'wb') as f: f.write(payload)
                key = os.urandom(32)
                proof = crypto.seal_file(source,sealed,key)
                self.assertEqual(proof['sha256'],crypto.sha256_file(sealed))
                self.assertEqual(os.stat(sealed).st_mode & 0o077,0)
                crypto.unseal_file(sealed,restored,key)
                with open(restored,'rb') as f:self.assertEqual(f.read(),payload)
                os.unlink(restored)
                with self.assertRaises(Exception):crypto.unseal_file(sealed,restored,os.urandom(32))
                self.assertFalse(os.path.exists(restored))
                with open(sealed,'r+b') as f:
                    f.seek(-1,2); last=f.read(1);f.seek(-1,2);f.write(bytes([last[0]^1]))
                with self.assertRaises(Exception):crypto.unseal_file(sealed,restored,key)
                self.assertFalse(os.path.exists(restored))
                self.assertFalse(any(n.startswith('.backup-') for n in os.listdir(directory)))

    def test_key_permissions_length_and_missing(self):
        with tempfile.TemporaryDirectory() as d:
            p=os.path.join(d,'key')
            with self.assertRaises(FileNotFoundError):crypto.load_key(p)
            with open(p,'wb') as f:f.write(os.urandom(32))
            os.chmod(p,0o600);self.assertEqual(len(crypto.load_key(p)),32)
            os.chmod(p,0o644)
            with self.assertRaises(ValueError):crypto.load_key(p)
            os.chmod(p,0o600)
            with open(p,'ab') as f:f.write(b'x')
            with self.assertRaises(ValueError):crypto.load_key(p)

    def test_pair_cleanup_and_digest(self):
        with tempfile.TemporaryDirectory() as d:
            key=os.urandom(32);paths=[]
            for name in ('database','filestore'):
                p=os.path.join(d,name);s=p+'.aesgcm'
                with open(p,'wb') as f:f.write(b'fixture '+name.encode())
                crypto.seal_file(p,s,key);paths.append(s)
            with patch.object(crypto,'load_key',return_value=key):
                with crypto.restore_inputs(*paths) as restored:
                    captured=list(restored)
                    self.assertTrue(all(os.path.exists(p) for p in captured))
                self.assertFalse(any(os.path.exists(p) for p in captured))
                with self.assertRaises(ValueError):
                    with crypto.restore_inputs(*paths,expected_hashes={paths[0]:'bad'}):pass

    def test_archive_traversal_links_rejected(self):
        for name,kind in (('../escape',tarfile.REGTYPE),('filestore/link',tarfile.SYMTYPE)):
            data=io.BytesIO()
            with tarfile.open(fileobj=data,mode='w') as t:
                member=tarfile.TarInfo(name);member.type=kind;member.linkname='/etc/passwd';t.addfile(member)
            data.seek(0)
            with tarfile.open(fileobj=data,mode='r') as t,tempfile.TemporaryDirectory() as d:
                with self.assertRaises(ValueError):crypto.extract_filestore(t,d)

    def test_restore_neutralises_outbound_copy_before_commit(self):
        with tempfile.TemporaryDirectory() as d:
            src,dst=os.path.join(d,'src'),os.path.join(d,'dst')
            with open(src,'w') as f:f.write('COPY public.ir_cron (id, active, name) FROM stdin;\n1\tt\tfixture\n\\.\nCOPY public.mail_mail (id, state) FROM stdin;\n2\toutgoing\n\\.\n')
            crypto.sanitise_restore_sql(src,dst)
            with open(dst) as f:sql=f.read()
            self.assertTrue(sql.startswith('BEGIN;'))
            self.assertIn('1\tf\tfixture',sql);self.assertIn('2\tcancel',sql)
            self.assertTrue(sql.endswith('COMMIT;\n'))
