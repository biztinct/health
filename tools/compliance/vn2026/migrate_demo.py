"""Run under carejiox-deploy -D DB -x; never emit clinical values or keys."""
import json
from odoo.addons.health_phi_encryption.hooks import _existing_columns, _migrate_column
from odoo.addons.health_phi_encryption.models import phi_crypto
ICP=env['ir.config_parameter'].sudo()
note_columns=_existing_columns(env.cr,'health_clinical_note')
if 'correction_reason' in note_columns:
    _migrate_column(env,'health_clinical_note','correction_reason','correction_reason_enc',None)
columns=_existing_columns(env.cr,'health_scribe_job')
if 'transcript' in columns:
    _migrate_column(env,'health_scribe_job','transcript','transcript_enc',None)
ai_columns=_existing_columns(env.cr,'health_ai_coding_log')
for field in ('request_json','response_json'):
    if field in ai_columns:
        env.cr.execute('SELECT id, "'+field+'" FROM health_ai_coding_log WHERE "'+field+'" IS NOT NULL')
        for identifier,payload in env.cr.fetchall():
            token=phi_crypto.encrypt(env,json.dumps(payload,ensure_ascii=False))
            env.cr.execute('UPDATE health_ai_coding_log SET "'+field+'_enc"=%s WHERE id=%s',(token,identifier))
        env.cr.execute('ALTER TABLE health_ai_coding_log DROP COLUMN "'+field+'"')
count=0
while True:
    moved=env['ir.attachment']._migrate_health_attachment_encryption(limit=200)
    count+=moved
    if moved<200:break
# Also protect legacy evidence linked by M2M with a generic attachment model.
notes=env['health.clinical.note'].sudo().search([])
(notes.image_ids | notes.audio_ids | env['health.consent'].sudo().search([]).evidence_attachment_ids)._health_encrypt_existing()
verified=failed=0
for note in notes.filtered(lambda n:n.emr_state=='final'):
    if note.verify_integrity():verified+=1
    else:failed+=1
if failed:
    raise RuntimeError('Historical integrity failures detected; investigate without resealing')
ICP.set_param('health_consent.require_notice_evidence','True')
ICP.set_param('health_consent.enforce','True')
ICP.set_param('health_fhir_core.consent_enforced','True')
ICP.set_param('health_emr.auto_finalize_enabled','False')
ICP.set_param('health_scribe.allow_cloud','False')
if env.cr.dbname=='carejiox_template':env['ir.cron'].sudo().search([('active','=',True)]).write({'active':False})
# Retain existing key derivation: no random replacement and no legacy timestamp invention.
env.cr.commit()
print('VN2026_MIGRATION '+json.dumps({'database':env.cr.dbname,'attachment_count_migrated':count,
    'historical_final_seals_verified':verified,'historical_final_seals_failed':failed,
    'notice_enforced':True,'consent_enforced':True,'ca_signing':'not_configured',
    'national_transport':'disabled','bhxh_transport':'disabled'}))
