"""Explicit master-only maintenance after installing the backup fix.

Commit metadata before removing originals. Unregistered/orphan copies are not
silently removed. No tenant names, clinical data or key bytes are printed.
"""
import json
import os
from odoo.addons.biz_tenants import backup_crypto
if env.cr.dbname!='carejiox':raise RuntimeError('Legacy backup registry is on the master only')
key=backup_crypto.load_key()
rows=env['biz.tenant.backup'].sudo().search([('state','=','done'),('encryption_format','=',False)])
migrated=missing=0
for row in rows:
    originals=[row.path,row.filestore_path]
    if any(not p or not os.path.isfile(p) for p in originals):missing+=1;continue
    targets=[p+'.aesgcm' for p in originals]
    if any(os.path.exists(p) for p in targets):raise RuntimeError('Existing target needs an operator recovery review; no files overwritten')
    proofs=[backup_crypto.seal_file(p,t,key) for p,t in zip(originals,targets)]
    row.write({'path':targets[0],'filestore_path':targets[1],
        'encryption_format':proofs[0]['format'],'encryption_key_id':proofs[0]['key_id'],
        'database_sha256':proofs[0]['sha256'],'filestore_sha256':proofs[1]['sha256']})
    env.cr.commit()
    for path in originals:os.unlink(path)
    migrated+=1
print('VN2026_LEGACY_BACKUPS '+json.dumps({'encrypted_registered_pairs':migrated,'missing_pairs_require_review':missing}))
