import base64
import hashlib
import io
import json
import os
import zipfile
from datetime import date, timedelta
from unittest.mock import patch
from types import SimpleNamespace
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged
from odoo.addons.health_emr.tests.test_emr import EmrBase
from odoo.addons.ai_egress.egress import EgressRefused
from odoo.addons.health_phi_encryption.models.ir_attachment import MAGIC
from ..models.rights import working_due


@tagged('post_install', '-at_install')
class TestCompliance(EmrBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.write({'group_ids': [(4, cls.env.ref('health_base.group_healthcare_admin').id)]})
    def _consent(self, purpose='ai_processing'):
        row = self.env['health.consent'].create({'client_id': self.patient.id,
            'consent_type_id': self.env['health.lookup.value']._default_for('consent_type',purpose),
            'method':'verbal', 'notice_version':'SYNTHETIC-TEST-v1',
            'notice_text':'Synthetic test only: purpose, recipients, risks and withdrawal instructions.'})
        row.action_grant()
        return row

    def test_notice_and_event_cannot_be_forged(self):
        self.env['ir.config_parameter'].sudo().set_param('health_consent.require_notice_evidence','True')
        Consent=self.env['health.consent']
        vals={'client_id':self.patient.id,'consent_type_id':self.env['health.lookup.value']._default_for('consent_type','ai_processing')}
        row=Consent.create(vals)
        with self.assertRaises(UserError):row.action_grant()
        with self.assertRaises(UserError):Consent.with_context(default_state='active').create(vals)
        row.write({'notice_version':'TEST','notice_text':'Synthetic notice'})
        row.action_grant();self.assertTrue(row.granted_datetime);self.assertEqual(row.granted_by_id,self.env.user)
        with self.assertRaises(UserError):row.write({'notice_text':'replacement'})
        with self.assertRaises(UserError):row.with_context(consent_transition=True).write({'state':'withdrawn'})
        row.write({'withdrawal_reason':'Synthetic withdrawal'})
        row.action_withdraw();self.assertTrue(row.withdrawn_datetime)
        with self.assertRaises(UserError):row.write({'withdrawal_reason':'replacement'})

    def test_finalization_identity_fields_and_defaults_protected(self):
        with self.assertRaises(UserError):self.env['health.clinical.note'].with_context(default_emr_state='final').create({'order_id':self.order.id})
        note=self._note(care_datetime=fields.Datetime.now()-timedelta(hours=1))
        with self.assertRaises(UserError):note.with_context(emr_finalize=True).write({'emr_state':'final'})
        note.action_finalize()
        for field,value in [('author_id',self.env.user.id),('order_id',self.order.id),('care_datetime',fields.Datetime.now()),('correction_reason','replacement'),('correction_reason_enc','replacement')]:
            with self.assertRaises(UserError):note.sudo().write({field:value})
        self.assertTrue(note.verify_integrity())
        self.env.flush_all();self.env.cr.execute("UPDATE health_clinical_note SET care_datetime=care_datetime+INTERVAL '1 minute' WHERE id=%s",(note.id,))
        note.invalidate_recordset();self.assertFalse(note.verify_integrity())

    def test_addendum_requires_reason_and_original_survives(self):
        original=self._note();original.action_finalize();seal=original.content_hash
        amendment=self._note(amends_note_id=original.id,correction_reason=False)
        with self.assertRaises(UserError):amendment.action_finalize()
        amendment.write({'correction_reason':'Correct synthetic observation'})
        amendment.action_finalize()
        self.assertEqual(original.content_hash,seal);self.assertTrue(original.verify_integrity())

    def test_v1_history_still_verifies_without_resealing(self):
        note=self._note();note.action_finalize();self.env.flush_all()
        self.env.cr.execute("UPDATE health_clinical_note SET hash_version='v1' WHERE id=%s",(note.id,))
        note.invalidate_recordset();legacy=note._compute_content_hash()
        self.env.cr.execute('UPDATE health_clinical_note SET content_hash=%s WHERE id=%s',(legacy,note.id))
        note.invalidate_recordset();self.assertTrue(note.verify_integrity())

    def test_attachment_encrypted_download_and_sealed_replacement_denied(self):
        note=self._note()
        payload=b'Synthetic sensitive image bytes'
        attachment=self.env['ir.attachment'].create({'name':'test-clinical.bin','raw':payload,
            'res_model':'health.clinical.note','res_id':note.id})
        self.assertTrue(attachment.store_fname.startswith('hphi/'))
        with open(attachment._full_path(attachment.store_fname),'rb') as f:
            ciphertext=f.read()
        self.assertTrue(ciphertext.startswith(MAGIC));self.assertNotIn(payload,ciphertext)
        self.assertEqual(attachment.raw,payload)
        with patch('odoo.addons.base.models.ir_attachment.request',SimpleNamespace(db=self.env.cr.dbname)):
            stream=attachment._to_http_stream();self.assertEqual(stream.type,'data');self.assertEqual(stream.data,payload)
        note.write({'image_ids':[(4,attachment.id)]});note.action_finalize()
        with self.assertRaises(UserError):attachment.sudo().write({'raw':b'replacement'})
        with self.assertRaises(UserError):attachment.sudo().unlink()
        self.assertTrue(note.verify_integrity())
        with self.assertRaises(UserError):attachment.write({'public':True})

    def test_plain_product_asset_keeps_normal_delivery(self):
        attachment=self.env['ir.attachment'].create({'name':'test-style.css','raw':b'body { color: red; }','public':True,'mimetype':'text/css'})
        self.assertFalse(attachment.store_fname.startswith('hphi/'))
        self.assertEqual(attachment.raw,b'body { color: red; }')
        with patch('odoo.addons.base.models.ir_attachment.request',SimpleNamespace(db=self.env.cr.dbname)):
            self.assertEqual(attachment._to_http_stream().type,'path')

    def test_consent_attachment_immutable_after_grant(self):
        attachment=self.env['ir.attachment'].create({'name':'synthetic-consent.txt','raw':b'Synthetic paper only'})
        consent=self.env['health.consent'].create({'client_id':self.patient.id,
            'consent_type_id':self.env['health.lookup.value']._default_for('consent_type','photography'),
            'method':'written','evidence_attachment_ids':[(4,attachment.id)],'notice_version':'TEST','notice_text':'Synthetic notice'})
        consent.action_grant()
        self.assertTrue(attachment.store_fname.startswith('hphi/'))
        with self.assertRaises(UserError):attachment.sudo().unlink()
        with self.assertRaises(UserError):attachment.sudo().write({'raw':b'replacement'})

    def test_evidence_independent_review_digest_and_immutability(self):
        req=self.env['health.compliance.requirement'].create({'name':'Synthetic requirement','code':'TEST','package':'A02'})
        with self.assertRaises(UserError):req.write({'technical_status':'verified'})
        evidence=self.env['health.compliance.evidence'].create({'name':'Synthetic fixture','requirement_id':req.id,
            'file':base64.b64encode(b'Synthetic result'), 'filename':'test.txt','release_commit':'test-only',
            'environment_scope':'isolated-test','result_summary':'Synthetic result','limitations':'Not real compliance evidence'})
        self.assertEqual(evidence.sha256,hashlib.sha256(b'Synthetic result').hexdigest())
        with self.assertRaises(UserError):evidence.action_review()
        reviewer=new_test_user(self.env,login='compliance_reviewer_test',groups='base.group_user,health_base.group_healthcare_admin')
        evidence.with_user(reviewer).action_review()
        req.write({'technical_status':'verified'})
        with self.assertRaises(UserError):evidence.write({'result_summary':'replacement'})
        att=self.env['ir.attachment'].sudo().search([('res_model','=',evidence._name),('res_id','=',evidence.id),('res_field','=','file')])
        with self.assertRaises(UserError):att.write({'raw':b'replacement'})
        with self.assertRaises(UserError):req.write({'authority_status':'approved'})

    def test_rights_calendar_and_workflow_proof(self):
        self.assertEqual(working_due(date(2026,10,2),{date(2026,10,5)}),date(2026,10,7))
        row=self.env['health.compliance.rights'].create({'name':'Synthetic access request','patient_id':self.patient.id,
            'kind':'access','received_at':'2026-10-02 03:00:00'})
        self.assertEqual(row.completion_due,date(2026,10,12))
        with self.assertRaises(UserError):row.action_acknowledge()
        with self.assertRaises(UserError):row.write({'completed_at':fields.Datetime.now()})
        with self.assertRaises(UserError):row.action_extend()
        with self.assertRaises(UserError):row.unlink()

    def test_retention_hold_prevents_patient_and_attachment_deletion(self):
        hold=self.env['health.compliance.hold'].create({'name':'Synthetic hold','patient_id':self.patient.id,
            'record_class':'Custodian synthetic class','legal_basis':'Synthetic test litigation hold'})
        attachment=self.env['ir.attachment'].create({'name':'test.txt','raw':b'test','res_model':'res.partner','res_id':self.patient.id})
        with self.assertRaises(UserError):self.patient.unlink()
        with self.assertRaises(UserError):attachment.unlink()
        with self.assertRaises(UserError):hold.write({'active':False})
        with self.assertRaises(UserError):hold.action_release()

    def test_archive_manifest_and_clinical_content(self):
        self.patient.write({'birth_date':'1980-01-01'})
        note=self._note(diagnosis='Synthetic archive observation');note.action_finalize()
        self.env['health.ai.coding.log'].create({'note_id':note.id,
            'request_json':{'user':'Synthetic structured archival payload'}, 'response_json':{'raw':'Synthetic response'}})
        action=self.patient.action_compliance_archive();identifier=int(action['url'].split('/')[3].split('?')[0])
        artifact=self.env['ir.attachment'].browse(identifier)
        with zipfile.ZipFile(io.BytesIO(artifact.raw)) as z:
            manifest=json.loads(z.read('manifest.json'))
            for path,metadata in manifest['files'].items():
                self.assertEqual(hashlib.sha256(z.read(path)).hexdigest(),metadata['sha256'])
            content=json.loads(z.read('patient-records.json'))
            self.assertIn('Synthetic archive observation',z.read('patient-records.html').decode())
            self.assertTrue(content['records']['health.clinical.note'][0]['integrity_verified'])
            self.assertIn('unsupported_models',manifest)
            self.assertIn('omitted_fields',manifest)
            self.assertEqual(content['patient']['birth_date'],'1980-01-01')
            self.assertEqual(content['records']['health.ai.coding.log'][0]['request_json']['user'], 'Synthetic structured archival payload')

    def test_ai_missing_purpose_destination_and_cloud_refused_before_network(self):
        provider=self.env['bi.ai.provider'].create({'name':'Synthetic local AI','provider':'ollama',
            'endpoint':'http://127.0.0.1:11434/api/chat','model_name':'test'})
        with patch('odoo.addons.biz_bi.models.bi_ai.requests.post') as post:
            with self.assertRaises(EgressRefused):provider._complete('test','test',patient=self.patient)
            self._consent('data_sharing')
            with self.assertRaises(EgressRefused):provider._complete('test','test',patient=self.patient)
            self._consent('ai_processing')
            with self.assertRaises(EgressRefused):provider._complete('test','test',patient=self.patient)
            self.assertFalse(post.called)
            provider.write({'provider':'openai','endpoint':'https://api.openai.com/v1/chat/completions'})
            with self.assertRaises(EgressRefused):provider._complete('test','test',patient=self.patient)
            self.assertFalse(post.called)

    def test_national_ack_cannot_be_manufactured(self):
        with self.assertRaises(UserError):self.env['fhir.adapter.vn'].reconcile({'state':'acked'})

    def test_scribe_transcript_not_plaintext(self):
        note=self._note();attachment=self.env['ir.attachment'].create({'name':'test.webm','raw':b'audio',
            'res_model':'health.clinical.note','res_id':note.id,'mimetype':'audio/webm'})
        job=self.env['health.scribe.job'].create({'note_id':note.id,'attachment_id':attachment.id,
            'audio_sha256':hashlib.sha256(b'audio').hexdigest(),'transcript':'Synthetic transcript secret'})
        self.assertEqual(job.transcript,'Synthetic transcript secret')
        self.env.flush_all();self.env.cr.execute('SELECT transcript_enc FROM health_scribe_job WHERE id=%s',(job.id,))
        stored=self.env.cr.fetchone()[0];self.assertTrue(stored.startswith('enc$1$'));self.assertNotIn('Synthetic transcript secret',stored)

    def test_ai_payload_audit_encrypted_and_append_only(self):
        log=self.env['health.ai.coding.log'].create({'note_id':self._note().id,
            'request_json':{'user':'Synthetic sensitive prompt'},'response_json':{'raw':'Synthetic response'}})
        self.assertEqual(log.request_json['user'],'Synthetic sensitive prompt')
        self.assertEqual(log.response_json['raw'],'Synthetic response')
        self.env.flush_all();self.env.cr.execute('SELECT request_json_enc,response_json_enc FROM health_ai_coding_log WHERE id=%s',(log.id,))
        for value in self.env.cr.fetchone():
            self.assertTrue(value.startswith('enc$1$'));self.assertNotIn('Synthetic',value)
        with self.assertRaises(UserError):log.write({'request_json_enc':'replacement'})

    def test_approved_recipient_required_and_withdrawal_blocks_calls(self):
        provider=self.env['bi.ai.provider'].create({'name':'Synthetic provider','provider':'ollama',
            'endpoint':'http://127.0.0.1:11434/api/chat','model_name':'test'})
        terms=self.env['ir.attachment'].create({'name':'synthetic-test-terms.txt','raw':b'Synthetic test terms'})
        destination=self.env['health.compliance.destination'].create({'name':'Synthetic loopback',
            'endpoint':provider.endpoint,'country':'Synthetic test only','purpose':'ai_processing',
            'legal_basis':'Synthetic test only','processor_terms_id':terms.id,'valid_until':fields.Date.today()+timedelta(days=1)})
        destination.action_approve()
        consent=self.env['health.consent'].create({'client_id':self.patient.id,
            'consent_type_id':self.env['health.lookup.value']._default_for('consent_type','ai_processing'),
            'method':'verbal','notice_version':'TEST','notice_text':'Synthetic exact recipient notice',
            'destination_ids':[(4,destination.id)]})
        consent.action_grant()
        with patch('odoo.addons.biz_bi.models.bi_ai.requests.post') as post:
            post.return_value.json.return_value={'message':{'content':'synthetic result'}}
            self.assertEqual(provider._complete('test','test',patient=self.patient),'synthetic result')
            self.assertFalse(post.call_args.kwargs['allow_redirects'])
            with self.assertRaises(UserError):consent.write({'destination_ids':[(5,0,0)]})
            consent.with_context(withdrawal_reason='Synthetic withdrawal').action_withdraw()
            post.reset_mock()
            with self.assertRaises(EgressRefused):provider._complete('test','test',patient=self.patient)
            self.assertFalse(post.called)

    def test_free_text_name_does_not_escape_pattern_scanner(self):
        guard=self.env['ai.egress.log']
        with self.assertRaises(EgressRefused):
            guard.guard('What happened to Synthetic Person?', 'schema', 'openai',
                'https://api.openai.com/v1/chat/completions',surface='biz_bi.nlq')
        with self.assertRaises(EgressRefused):
            guard.guard('Synthetic free question', 'schema', 'ollama',
                'http://127.0.0.1:11434/api/chat',surface='learn.coach.composer')

    def test_audio_capture_requires_distinct_purpose_before_storage(self):
        self.env['ir.config_parameter'].sudo().set_param('health_consent.enforce','True')
        note=self._note();Job=self.env['health.scribe.job']
        before=self.env['ir.attachment'].search_count([])
        from odoo.exceptions import AccessError
        with self.assertRaises(AccessError):Job.register_upload(self.order,note,b'fixture audio','audio/webm')
        self.assertEqual(before,self.env['ir.attachment'].search_count([]))
        self._consent('photography')
        with self.assertRaises(AccessError):Job.register_upload(self.order,note,b'fixture audio','audio/webm')
        self._consent('audio_recording')
        job=Job.register_upload(self.order,note,b'fixture audio','audio/webm')
        self.assertEqual(job.state,'pending')
        self.assertTrue(job.attachment_id.store_fname.startswith('hphi/'))

    def test_export_register_uses_real_object_button_rpc_contract(self):
        from odoo.service.model import call_kw
        requirement=self.env.ref('health_compliance.requirement_05_1')
        action=call_kw(self.env[requirement._name],'export_register',[[requirement.id]],{})
        attachment=self.env['ir.attachment'].browse(int(action['url'].split('/')[3].split('?')[0]))
        exported=json.loads(attachment.raw)
        self.assertEqual(len(exported['requirements']),48)
        self.assertIn('No blanket compliance',exported['notice'])
        self.assertTrue(attachment.store_fname.startswith('hphi/'))
