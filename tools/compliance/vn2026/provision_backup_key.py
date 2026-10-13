"""Run as root on the deployment host. Never overwrite or print a key."""
import grp
import hashlib
import os
import stat
path='/etc/biz-tenants-backup.key'
try:
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o640)
except FileExistsError:
    created=False
else:
    with os.fdopen(fd,'wb') as output:
        output.write(os.urandom(32));output.flush();os.fsync(output.fileno())
    os.chown(path,0,grp.getgrnam('odoo').gr_gid)
    created=True
info=os.stat(path,follow_symlinks=False)
if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o027 or info.st_uid != 0:
    raise RuntimeError('Existing backup key has unsuitable custody or permissions; no replacement was attempted')
with open(path,'rb') as source:key=source.read(33)
if len(key)!=32:raise RuntimeError('Existing backup key has invalid length; no replacement was attempted')
print('Backup key verified; path=%s created=%s key_id=%s; independent escrow remains an operator task' %
      (path,created,hashlib.sha256(key).hexdigest()[:16]))
