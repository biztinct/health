# -*- coding: utf-8 -*-
"""EMR-readiness checklist (Circular 54 areas) — handover §4.

FIXED checklist rows/statuses (no invented compliance claims) plus a LIVE,
computed coding-density figure and per-facility MOH-code presence."""

from datetime import timedelta

from odoo import api, fields, models
from odoo.tools import html_escape

# (criterion, health19 evidence, status). VERBATIM from the handover table —
# do not edit the compliance claims.
CHECKLIST = [
    ('User authentication & role-based access',
     'Odoo auth + healthcare group ladder + record rules', 'met'),
    ('Audit trail of clinical data access',
     'api.audit.log (append-only) + mail tracking', 'met'),
    ('Structured EMR content (vitals, meds, care plans, forms)',
     'clinical spine 7/7 modules', 'met'),
    ('ICD-10 coded diagnoses',
     'health_fhir_terminology sidecar',
     'met (coding density depends on usage)'),
    ('Interoperability / HIS interface readiness',
     'FHIR R4 facade, 20 resources + terminology ops', 'met'),
    ('EMR export (hồ sơ bệnh án điện tử)',
     "this module's patient bundle export", 'met'),
    ('PHI protection at rest',
     'health_phi_encryption (AES-GCM field level)', 'met'),
    ('Patient identity (CCCD/VNeID linkage)',
     'national_id/cccd + vneid_verified capture',
     'partial (VNeID OIDC not integrated)'),
    ('Digital signature on clinical documents',
     'consent digital signature only',
     'gap (VNPT-CA/Viettel-CA integration planned)'),
    ('BHYT claims interface (Decision 4210 XML)',
     '—', 'gap (planned adapter phase)'),
    ('Backup & retention procedures',
     'server ops (outside application scope)',
     'operational — evidence per deployment'),
]

_STATUS_COLOR = {'met': '#1B6E20', 'partial': '#B26A00',
                 'gap': '#B3261E', 'operational': '#5A5A5A'}


class VnEmrReadiness(models.TransientModel):
    _name = 'vn.emr.readiness'
    _description = 'VN EMR Readiness Report'

    facility_id = fields.Many2one(
        'health.facility', string='Facility',
        help='Scope the coding-density figure to one facility '
             '(empty = all facilities).')
    notes_total = fields.Integer(
        string='Clinical Notes (90d)', compute='_compute_report')
    notes_coded = fields.Integer(
        string='Notes with ICD-10 Code (90d)', compute='_compute_report')
    coding_density = fields.Float(
        string='Coding Density (%)', compute='_compute_report')
    report_html = fields.Html(
        string='Readiness Report', compute='_compute_report', sanitize=False)

    @api.depends('facility_id')
    def _compute_report(self):
        cutoff = fields.Datetime.now() - timedelta(days=90)
        for wizard in self:
            domain = [('create_date', '>=', cutoff)]
            if wizard.facility_id:
                domain.append(
                    ('order_id.facility_id', '=', wizard.facility_id.id))
            notes = self.env['health.clinical.note'].search(domain)
            total = len(notes)
            coded = len(notes.filtered(lambda note: note.condition_code_ids))
            wizard.notes_total = total
            wizard.notes_coded = coded
            wizard.coding_density = (
                round(100.0 * coded / total, 1) if total else 0.0)
            wizard.report_html = wizard._build_html()

    def _build_html(self):
        self.ensure_one()
        rows = []
        for criterion, evidence, status in CHECKLIST:
            head = status.split(' ', 1)[0].split('(', 1)[0].strip()
            color = _STATUS_COLOR.get(head, '#5A5A5A')
            rows.append(
                '<tr>'
                '<td style="padding:6px 10px;border-bottom:1px solid #E0E0E0;">%s</td>'
                '<td style="padding:6px 10px;border-bottom:1px solid #E0E0E0;color:#5A5A5A;">%s</td>'
                '<td style="padding:6px 10px;border-bottom:1px solid #E0E0E0;'
                'color:%s;font-weight:600;">%s</td>'
                '</tr>' % (html_escape(criterion), html_escape(evidence),
                           color, html_escape(status)))
        scope = (self.facility_id.name if self.facility_id
                 else 'All facilities')
        facilities = self._facility_moh_lines()
        return (
            '<div>'
            '<h3 style="margin-bottom:4px;">EMR Readiness — Circular 54</h3>'
            '<p style="color:#5A5A5A;margin-top:0;">Scope: %s</p>'
            '<table style="border-collapse:collapse;width:100%%;">'
            '<thead><tr>'
            '<th style="text-align:left;padding:6px 10px;border-bottom:2px solid #333;">Criterion</th>'
            '<th style="text-align:left;padding:6px 10px;border-bottom:2px solid #333;">health19 evidence</th>'
            '<th style="text-align:left;padding:6px 10px;border-bottom:2px solid #333;">Status</th>'
            '</tr></thead><tbody>%s</tbody></table>'
            '<h4 style="margin-bottom:4px;">Live indicators</h4>'
            '<ul>'
            '<li>ICD-10 coding density (last 90 days): '
            '<strong>%s%%</strong> (%s of %s notes coded)</li>'
            '</ul>'
            '<h4 style="margin-bottom:4px;">Facility MOH codes</h4>%s'
            '</div>'
        ) % (html_escape(scope), ''.join(rows), self.coding_density,
             self.notes_coded, self.notes_total, facilities)

    def _facility_moh_lines(self):
        facilities = (self.facility_id if self.facility_id
                      else self.env['health.facility'].search([]))
        items = []
        for facility in facilities:
            present = bool(facility.moh_facility_code)
            color = '#1B6E20' if present else '#B3261E'
            label = (facility.moh_facility_code if present
                     else 'missing MOH facility code')
            items.append(
                '<li>%s: <span style="color:%s;">%s</span></li>' % (
                    html_escape(facility.name or ''), color,
                    html_escape(label)))
        return '<ul>%s</ul>' % ''.join(items) if items else '<p>—</p>'
