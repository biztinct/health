"""Authenticated streaming encryption for database/filestore backup pairs.

Keys are files outside both the database and backup artifacts. Never log keys.
Temporary decrypted files are private and removed on failure or context exit.
"""
import hashlib
import os
import stat
import tempfile
from contextlib import contextmanager

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

MAGIC = b'H19BKP\x01\x00'
CHUNK = 1024 * 1024


def load_key(path=None):
    path = path or os.environ.get('BIZ_BACKUP_KEY_FILE', '/etc/biz-tenants-backup.key')
    info = os.stat(path, follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o027:
        raise ValueError('Backup key must be a regular file without world access')
    with open(path, 'rb') as source:
        key = source.read(33)
    if len(key) != 32:
        raise ValueError('Backup key must contain exactly 32 bytes')
    return key


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as source:
        for block in iter(lambda: source.read(CHUNK), b''):
            digest.update(block)
    return digest.hexdigest()


def is_encrypted_file(path):
    with open(path, 'rb') as source:
        return source.read(len(MAGIC)) == MAGIC


def seal_file(source_path, destination, key):
    nonce = os.urandom(12)
    header = MAGIC + nonce
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(header)
    fd, temporary = tempfile.mkstemp(prefix='.backup-encrypt-', dir=os.path.dirname(destination))
    try:
        with os.fdopen(fd, 'wb') as output, open(source_path, 'rb') as source:
            output.write(header)
            for block in iter(lambda: source.read(CHUNK), b''):
                output.write(encryptor.update(block))
            output.write(encryptor.finalize())
            output.write(encryptor.tag)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
    return {'sha256': sha256_file(destination), 'bytes': os.path.getsize(destination),
            'key_id': hashlib.sha256(key).hexdigest()[:16], 'format': 'H19BKP-AES256GCM-v1'}


def unseal_file(source_path, destination, key):
    size = os.path.getsize(source_path)
    if size < len(MAGIC) + 12 + 16:
        raise ValueError('Encrypted backup is truncated')
    fd, temporary = tempfile.mkstemp(prefix='.backup-decrypt-', dir=os.path.dirname(destination))
    try:
        with open(source_path, 'rb') as source, os.fdopen(fd, 'wb') as output:
            header = source.read(len(MAGIC) + 12)
            if header[:len(MAGIC)] != MAGIC:
                raise ValueError('Unknown backup format')
            source.seek(-16, os.SEEK_END)
            tag = source.read(16)
            source.seek(len(header))
            decryptor = Cipher(algorithms.AES(key), modes.GCM(header[-12:], tag)).decryptor()
            decryptor.authenticate_additional_data(header)
            remaining = size - len(header) - 16
            while remaining:
                block = source.read(min(CHUNK, remaining))
                if not block:
                    raise ValueError('Encrypted backup is truncated')
                remaining -= len(block)
                output.write(decryptor.update(block))
            output.write(decryptor.finalize())  # Authentication precedes publication.
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


@contextmanager
def restore_inputs(database_path, filestore_path=None, expected_hashes=None):
    paths = [database_path, filestore_path]
    expected_hashes = expected_hashes or {}
    for path in filter(None, paths):
        expected = expected_hashes.get(path)
        if expected and sha256_file(path) != expected:
            raise ValueError('Backup artifact checksum verification failed')
    with tempfile.TemporaryDirectory(prefix='health19-restore-') as directory:
        results = []
        key = None
        for index, path in enumerate(paths):
            if not path:
                results.append(None)
            elif is_encrypted_file(path):
                key = key or load_key()
                target = os.path.join(directory, str(index))
                unseal_file(path, target, key)
                results.append(target)
            else:
                results.append(path)  # Explicit backward compatibility for legacy copies.
        yield tuple(results)


def extract_filestore(archive, destination):
    """Reject traversal, symlinks and special files before extraction."""
    root = os.path.realpath(destination)
    for member in archive.getmembers():
        target = os.path.realpath(os.path.join(root, member.name))
        if (not target.startswith(root + os.sep) or member.issym()
                or member.islnk() or not (member.isfile() or member.isdir())):
            raise ValueError('Unsafe filestore archive member')
    archive.extractall(destination)


def sanitise_restore_sql(source, destination):
    """Neutralise outbound jobs in COPY data before schema becomes visible.

    pg_restore defaults to COPY for data. Fail closed if a cron COPY has an
    unexpected schema. No clinical values are changed. SQL runs atomically.
    """
    import re
    table = None
    columns = []
    with open(source, encoding='utf-8') as src, open(destination, 'w', encoding='utf-8') as dst:
        dst.write('BEGIN;\n')
        for line in src:
            match = re.match(r'COPY public\.(ir_cron|ir_mail_server|mail_mail) \(([^)]+)\) FROM stdin;', line)
            if match:
                table = match.group(1)
                columns = [c.strip().strip('"') for c in match.group(2).split(',')]
                if table in ('ir_cron', 'ir_mail_server') and 'active' not in columns:
                    raise ValueError('Restore cannot determine the scheduled-job active field')
            elif table and line.rstrip('\n') == '\\.':
                table = None
            elif table:
                values = line.rstrip('\n').split('\t')
                if len(values) != len(columns):
                    raise ValueError('Unexpected outbound-job COPY row')
                if table in ('ir_cron', 'ir_mail_server'):
                    values[columns.index('active')] = 'f'
                elif 'state' in columns and values[columns.index('state')] == 'outgoing':
                    values[columns.index('state')] = 'cancel'
                line = '\t'.join(values) + '\n'
            dst.write(line)
        dst.write('COMMIT;\n')


def restore_database(dump_path, database):
    import subprocess
    with tempfile.TemporaryDirectory(prefix='health19-restore-sql-') as directory:
        sql = os.path.join(directory, 'source.sql')
        inert = os.path.join(directory, 'inert.sql')
        result = subprocess.run(['pg_restore', '--no-owner', '--exit-on-error',
                                 '--file', sql, dump_path],
                                capture_output=True, text=True, timeout=3600)
        if result.returncode:
            return result
        sanitise_restore_sql(sql, inert)
        return subprocess.run(['psql', '-X', '--set=ON_ERROR_STOP=1',
                               '-d', database, '-f', inert],
                              capture_output=True, text=True, timeout=3600)
