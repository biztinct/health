# -*- coding: utf-8 -*-
"""SH-1 §3 (F1) — the anonymous public user must not read PHI.

Four `base.group_public` / `base.group_portal` rows in this module's
``ir.model.access.csv`` granted read on `health.clinical.note` (57 live rows),
`health.fieldservice.order` (1269) and `health.appointment` (0), and **no
`ir.rule` narrowed any of them**: global rules AND together, group rules OR
together, and when no group rule matches the acting user nothing narrows the
ACL at all. The nine FSO rules are all group-bound to healthcare roles, so
none of them constrains the public user.

These tests assert the EXPLOIT, not the ACL table — the row is the cause, the
oracle is the defect. The reachable primitive is a public thread-store route
that takes a caller-supplied `thread_model` and answers with
``hasReadAccess``; it gates on ``thread.sudo(False).has_access(mode)``
(`mail/models/mail_thread.py:5090`), which returned **True** for the anonymous
public user.

Route note (deviation, see the SH-1 report): the handover named
``/mail/thread/data``. That route exists only in the repo's stale Odoo-18
snapshot of ``addons/mail`` (v1.18) — the SAME stale copy §6.0(a) warns
about. On the live Odoo 19 mail (v1.19) it 404s; the equivalent live
primitive is ``/mail/data`` (`mail/controllers/webclient.py:20`,
``auth="public"``), whose ``mail.thread`` fetch param reaches the identical
gate. Both are probed below so the test survives either build.
"""
import json
import uuid

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, new_test_user, tagged

THREAD_ROUTES = ('/mail/data', '/mail/thread/data')


@tagged('post_install', '-at_install')
class TestSh1PublicAcl(HttpCase):
    """F1 — deleting the public grants, and the ladder they were masking."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        tag = uuid.uuid4().hex[:5]
        cls.province = cls.env['health.catchment.province'].create({
            'name': 'SH1 P %s' % tag, 'code': 'S%s' % tag[:3]})
        cls.facility = cls.env['health.facility'].create({
            'name': 'SH1 Facility %s' % tag, 'code': 'SF%s' % tag[:3],
            'street': '1 St', 'city': 'City',
            'catchment_province_id': cls.province.id})
        cls.patient = cls.env['res.partner'].create({
            'name': 'SH1 Patient %s' % tag, 'is_patient': True,
            'catchment_province_id': cls.province.id,
            'primary_facility_id': cls.facility.id,
            'mobile': '09%08d' % (uuid.uuid4().int % 10 ** 8)})
        cls.order = cls.env['health.fieldservice.order'].create({
            'patient_id': cls.patient.id, 'facility_id': cls.facility.id,
            'scheduled_datetime': fields.Datetime.now(),
            'scheduled_duration': 60, 'service_type': 'home_visit'})
        cls.note = cls.env['health.clinical.note'].create({
            'order_id': cls.order.id,
            'clinical_notes': '<p>SH1 fixture note</p>',
            'diagnosis': 'SH1 fixture diagnosis'})
        cls.public_user = cls.env.ref('base.public_user')

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _probe_thread(self, route, model, res_id):
        """Unauthenticated thread-store probe.

        Returns the route's ``hasReadAccess`` verdict, or None when the route
        does not exist on this build (so the assertion can say so honestly
        rather than passing by accident).
        """
        if route == '/mail/data':
            params = {'fetch_params': [[
                'mail.thread',
                {'thread_model': model, 'thread_id': res_id,
                 'request_list': []},
            ]]}
        else:
            params = {'thread_model': model, 'thread_id': res_id,
                      'request_list': []}
        resp = self.url_open(
            route,
            data=json.dumps({'jsonrpc': '2.0', 'method': 'call',
                             'params': params}),
            headers={'Content-Type': 'application/json'})
        if resp.status_code == 404:
            return None
        self.assertEqual(resp.status_code, 200, '%s: %s' % (route, resp.text[:300]))
        payload = resp.json()
        # An error envelope means the route refused outright — also "no read".
        if 'error' in payload:
            return False
        threads = (payload.get('result') or {}).get('mail.thread') or []
        entry = next((t for t in threads if t.get('id') == res_id), None)
        self.assertIsNotNone(
            entry, 'no mail.thread entry for %s/%s in %s' % (model, res_id, payload))
        return bool(entry.get('hasReadAccess'))

    def _assert_no_public_read(self, model, res_id):
        probed = []
        for route in THREAD_ROUTES:
            verdict = self._probe_thread(route, model, res_id)
            if verdict is None:
                continue
            probed.append(route)
            self.assertFalse(
                verdict,
                'UNAUTHENTICATED %s reports hasReadAccess=True for %s id %s — '
                'the public ACL row is still live' % (route, model, res_id))
        self.assertTrue(
            probed,
            'neither %s exists on this build — the exploit probe proved '
            'nothing; investigate rather than trusting this test'
            % (' nor '.join(THREAD_ROUTES),))

    # ------------------------------------------------------------------
    # T3.1 / T3.2 — the oracle
    # ------------------------------------------------------------------
    def test_31_public_cannot_read_clinical_note_thread(self):
        self.assertIn(
            'message_ids', self.env['health.clinical.note']._fields,
            'health.clinical.note is not a mail.thread here (health_emr '
            'absent) — the oracle cannot be probed')
        # the gate the route consults, asserted directly
        self.assertFalse(
            self.note.with_user(self.public_user).sudo(False).has_access('read'),
            'the anonymous public user still has_access(read) on a clinical note')
        self._assert_no_public_read('health.clinical.note', self.note.id)

    def test_32_public_cannot_read_fso_thread(self):
        # T3.2's open question, answered: health.fieldservice.order DOES
        # inherit mail.thread (health_fieldservice_order.py:84), so the
        # assertion is meaningful rather than vacuous.
        self.assertIn('message_ids', self.env['health.fieldservice.order']._fields)
        self.assertFalse(
            self.order.with_user(self.public_user).sudo(False).has_access('read'),
            'the anonymous public user still has_access(read) on an FSO')
        self._assert_no_public_read('health.fieldservice.order', self.order.id)

    # ------------------------------------------------------------------
    # T3.3 — the clinical ladder the public row was masking
    # ------------------------------------------------------------------
    def test_33_doctor_can_read_and_create_clinical_notes(self):
        doctor = new_test_user(
            self.env, login='sh1_doctor', password='sh1_doctor_pw',
            groups='base.group_user,health_base.group_healthcare_doctor',
            catchment_province_id=self.province.id)
        note = self.note.with_user(doctor)
        note.check_access('read')          # raises if the grant is missing
        self.assertTrue(note.display_name)
        created = self.env['health.clinical.note'].with_user(doctor).create({
            'order_id': self.order.id,
            'clinical_notes': '<p>doctor sign-off</p>'})
        self.assertTrue(created.id)
        self.assertEqual(created.author_id, doctor)

    # ------------------------------------------------------------------
    # T3.4 — the direct negative for the deleted rows
    # ------------------------------------------------------------------
    def test_34_public_user_is_denied_on_all_three_models(self):
        for model in ('health.clinical.note', 'health.fieldservice.order',
                      'health.appointment'):
            with self.subTest(model=model):
                with self.assertRaises(AccessError):
                    self.env[model].with_user(self.public_user).search([])

    def test_33b_receptionist_has_no_clinical_note_read(self):
        """SH-1 REVIEW FIX — the receptionist grant was removed again.

        §3.2 specified cloning `health_condition`'s ladder, which includes a
        receptionist read row, and the implementer did exactly that. The
        review measured the consequence: `health.clinical.note` has ZERO
        `ir.rule` rows, so that row was UNNARROWED read of every clinical
        note in the database for ten front-desk users — and it bought
        nothing, because a receptionist has no `health.fieldservice.order`
        ACL and so cannot open the only form that embeds notes, while the
        standalone "Unsigned Clinical Notes" menu (id 960, no group
        restriction) is hidden by Odoo precisely when the model ACL is
        absent. The phase's purpose was the DOCTOR sign-off worklist; the
        receptionist row was collateral widening, so it is gone.

        If a front-desk surface ever genuinely needs note data, the answer is
        a record rule first (see T-009), not a blanket ACL row.
        """
        recep = new_test_user(
            self.env, login='sh1_recep', password='sh1_recep_pw',
            groups='base.group_user,health_base.group_healthcare_receptionist',
            catchment_province_id=self.province.id)
        with self.assertRaises(AccessError):
            self.env['health.clinical.note'].with_user(recep).search([])

    def test_34b_portal_user_is_denied_on_appointments(self):
        portal = new_test_user(
            self.env, login='sh1_portal', password='sh1_portal_pw',
            groups='base.group_portal')
        with self.assertRaises(AccessError):
            self.env['health.appointment'].with_user(portal).search([])

    # ------------------------------------------------------------------
    # T3.5 — the tokenized portal path is sudo'd and therefore unaffected
    # ------------------------------------------------------------------
    def test_35_tokenized_portal_records_page_still_renders(self):
        if 'health.portal.access' not in self.env:
            self.skipTest('health_portal is not installed on this database')
        access = self.env['health.portal.access'].get_or_create_for(self.patient)
        self.assertTrue(access.token)
        resp = self.url_open('/my/care/%s/records' % access.token)
        self.assertEqual(resp.status_code, 200, resp.text[:400])
        # emr_state='final' count is 0 on vietuat, so the list is legitimately
        # empty — assert the page rendered, not its contents.
        self.assertIn('my/care/%s' % access.token, resp.text)
