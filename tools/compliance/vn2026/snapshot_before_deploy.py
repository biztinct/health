"""Wrapper shell runs with demo service stopped for DB+filestore consistency."""
import importlib.util
import json
import os
import subprocess
import tarfile
from datetime import datetime, timezone
spec=importlib.util.spec_from_file_location('backup_crypto','/tmp/biz_tenants/backup_crypto.py')
crypto=importlib.util.module_from_spec(spec);spec.loader.exec_module(crypto)
key=crypto.load_key()
root='/odoo/vn2026-recovery'
os.makedirs(root,mode=0o700,exist_ok=True)
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
proofs=[]
for db in ('carejiox','carejiox_template','hhh'):
    dump=os.path.join(root,db+'-'+stamp+'.dump')
    files=os.path.join(root,db+'-'+stamp+'.filestore.tar.gz')
    subprocess.run(['pg_dump','-Fc','-d',db,'-f',dump],check=True,timeout=3600)
    with tarfile.open(files,'w:gz') as archive:
        archive.add('/odoo/.local/share/Odoo/filestore/'+db,arcname='filestore')
    for path in (dump,files):
        proof=crypto.seal_file(path,path+'.aesgcm',key)
        os.unlink(path)
        proofs.append({'database':db,'filename':os.path.basename(path+'.aesgcm'),**proof})
with open(root+'/pre-deployment-manifest-'+stamp+'.json','w') as output:json.dump(proofs,output,indent=2)
print('VN2026_RECOVERY_SNAPSHOT '+json.dumps({'database_count':3,'encrypted_artifact_count':len(proofs),'timestamp':stamp}))
