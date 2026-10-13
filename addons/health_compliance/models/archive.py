import base64
import hashlib
import html
import io
import json
import zipfile
from odoo import _, fields, models
from odoo.exceptions import UserError
from .assurance import require_manager
from .protections import audit_event, _subject_path


class PartnerArchive(models.Model):
    _inherit = 'res.partner'

    def action_compliance_archive(self):
        self.ensure_one()
        require_manager(self.env)
        self.check_access('read')
        files = {}
        sections = {}
        unsupported = []
        omitted_fields = {}
        exported_refs = set()
        for model_name in sorted(self.env.registry.models):
            if not model_name.startswith(('health.', 'bhyt.')) or model_name.startswith('health.compliance.'):
                continue
            Model = self.env[model_name]
            if not Model._auto or Model._transient:
                continue
            relation = _subject_path(self.env, model_name)
            if not relation:
                unsupported.append(model_name)
                continue
            records = Model.sudo().with_context(active_test=False, bin_size=False).search([(relation, '=', self.id)])
            sections[model_name] = []
            for row in records:
                exported_refs.add((model_name, row.id))
                content = {'id': row.id}
                for name, field in row._fields.items():
                    if name.endswith(('_enc', '_bidx')) or name in ('__last_update',):
                        continue
                    if any(part in name.lower() for part in ('password', 'secret', 'api_key', 'credential', 'token')) or name.endswith('_url'):
                        omitted_fields.setdefault(model_name, {})[name] = 'Credential/access-link field excluded; regenerate through an authorised workflow.'
                        continue
                    if field.type in ('char', 'text', 'html', 'selection', 'integer', 'float', 'boolean', 'date', 'datetime', 'monetary', 'json'):
                        value = row[name]
                        content[name] = str(value) if field.type in ('date', 'datetime') and value else value
                    elif field.type == 'many2one':
                        content[name] = {'id': row[name].id, 'label': row[name].display_name} if row[name] else None
                    elif field.type in ('one2many', 'many2many'):
                        related = row[name]
                        content[name] = related.ids
                        content[name + '_details'] = [dict(id=r.id, label=r.display_name,
                            model=r._name, **({'code': r.code} if 'code' in r._fields else {})) for r in related]
                    elif field.type == 'binary':
                        value = row[name]
                        if value:
                            path = 'fields/%s/%s/%s.bin' % (model_name, row.id, name)
                            files[path] = base64.b64decode(value)
                            content[name] = {'archive_path': path}
                    else:
                        omitted_fields.setdefault(model_name, {})[name] = 'Unsupported field type: ' + field.type
                if model_name == 'health.clinical.note' and 'emr_state' in row._fields:
                    content['integrity_verified'] = row.verify_integrity()
                    if not content['integrity_verified']:
                        raise UserError(_('Clinical integrity verification failed; archive not published.'))
                sections[model_name].append(content)
        exported_refs.add(('res.partner', self.id))
        attachments = self.env['ir.attachment'].sudo().with_context(active_test=False).search([
            ('res_model', 'in', list({ref[0] for ref in exported_refs})), ('type', '=', 'binary'),
            '|', ('res_field', '=', False), ('res_field', '!=', False)])
        for attachment in attachments:
            if (attachment.res_model, attachment.res_id) in exported_refs:
                files['attachments/%s.bin' % attachment.id] = attachment.raw or b''
        # Explicit M2M evidence attachments may have a different res_model.
        for model, rows in sections.items():
            for row in rows:
                for field in ('image_ids', 'audio_ids', 'evidence_attachment_ids'):
                    for identifier in row.get(field, []):
                        attachment = self.env['ir.attachment'].sudo().browse(identifier).exists()
                        if attachment:
                            files['attachments/%s.bin' % identifier] = attachment.raw or b''
        # Include the actual healthcare profile field names (birth_date,
        # gender_id etc.), rather than relying on aliases that are absent here.
        metadata = self.env['ir.model.fields'].sudo().search([('model', '=', 'res.partner')])
        healthcare_fields = {f.name for f in metadata if any(m.strip().startswith('health_')
            for m in (f.modules or '').split(','))}
        patient_fields = sorted({f for f in healthcare_fields | {'name', 'phone', 'mobile', 'email', 'lang', 'tz'}
            if f in self._fields and self._fields[f].type in ('char', 'text', 'html', 'selection',
                'integer', 'float', 'boolean', 'date', 'datetime', 'monetary', 'json', 'many2one')
            and not f.endswith(('_enc', '_bidx'))
            and not any(part in f.lower() for part in ('password', 'secret', 'api_key', 'credential', 'token'))
            and not f.endswith('_url')})
        data = {'patient': self.sudo().read(patient_fields)[0], 'records': sections,
                'unsupported_models': unsupported, 'omitted_fields': omitted_fields,
                'scope_notice': 'Export includes supported patient-linked healthcare models and their linked binary files. '
                    'Models without a supported patient link, chatter, financial/platform records and external systems '
                    'require a separate completeness review. This is not a declaration of a complete statutory EMR archive.'}
        files['patient-records.json'] = json.dumps(data, ensure_ascii=False, default=str, indent=2).encode()
        body = ['<!doctype html><html><meta charset="utf-8"><title>Patient archive</title><body>',
                '<h1>Patient archive</h1><p>' + html.escape(data['scope_notice']) + '</p>',
                '<h2>Patient</h2><pre>' + html.escape(json.dumps(data['patient'], ensure_ascii=False, indent=2, default=str)) + '</pre>']
        for model, rows in sections.items():
            body.append('<h2>' + html.escape(model) + '</h2>')
            for row in rows:
                body.append('<article><pre>' + html.escape(json.dumps(row, ensure_ascii=False, default=str, indent=2)) + '</pre></article>')
        body.append('<h2>Attachments</h2>')
        for path in sorted(files):
            if path.startswith('attachments/'):
                body.append('<p><a href="' + path + '">' + path + '</a></p>')
        body.append('</body></html>')
        files['patient-records.html'] = '\n'.join(body).encode()
        manifest = {'database': self.env.cr.dbname, 'exported_at': fields.Datetime.to_string(fields.Datetime.now()),
                    'patient_id': self.id, 'counts': {m: len(r) for m, r in sections.items()},
                    'files': {p: {'bytes': len(v), 'sha256': hashlib.sha256(v).hexdigest()} for p, v in files.items()},
                    'unsupported_models': unsupported, 'omitted_fields': omitted_fields, 'scope_notice': data['scope_notice']}
        files['manifest.json'] = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path, value in files.items():
                archive.writestr(path, value)
        attachment = self.env['ir.attachment'].create({'name': 'patient-%s-archive.zip' % self.id,
            'raw': buffer.getvalue(), 'mimetype': 'application/zip', 'res_model': 'res.partner', 'res_id': self.id})
        audit_event(self.env, 'patient_archive', 'res.partner', self.ids, outcome='exported')
        return {'type': 'ir.actions.act_url', 'url': '/web/content/%s?download=true' % attachment.id,
                'target': 'download'}
