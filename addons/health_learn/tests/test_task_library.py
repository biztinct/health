"""Role-scoped learning must never become a second route to private data."""
import json
from unittest.mock import patch
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase, tagged
from ..models.learn_task import catalog


@tagged('post_install', '-at_install')
class TestTaskLibrary(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.people = {}
        for role, group in [('finance', 'health_base.group_healthcare_finance'),
                            ('clinical', 'health_base.group_healthcare_nurse'),
                            ('operations', 'health_base.group_healthcare_operations_manager'),
                            ('owner', 'health_base.group_healthcare_owner'),
                            ('portal', 'base.group_portal')]:
            groups = [cls.env.ref(group).id]
            if role != 'portal':
                groups.append(cls.env.ref('base.group_user').id)
            cls.people[role] = users.create({'name': 'Learning ' + role,
                'login': 'learn_library_' + role, 'group_ids': [(6, 0, groups)]})
        cls.fin_key = 'finance.receive-part-payment'
        cls.admin_key = 'administration.add-or-disable-a-user'

    def task(self, role):
        return self.env['learn.task'].with_user(self.people[role])

    def test_catalog_is_role_scoped(self):
        for role in ('finance', 'clinical', 'operations'):
            data = self.task(role).get_catalog()
            self.assertTrue(data['tasks'])
            self.assertFalse(any(t['key'] == self.admin_key for t in data['tasks']))
            self.assertFalse(any('media' in t for t in data['tasks']))
            self.assertFalse(any('correct' in q for q in data['quizzes'].values()))
        self.assertTrue(self.task('owner')._task(self.admin_key))

    def test_direct_topic_and_media_require_role(self):
        with self.assertRaises(AccessError):
            self.task('clinical')._task(self.admin_key)
        with self.assertRaises(AccessError):
            self.task('finance')._media_path(self.admin_key)
        with self.assertRaises(AccessError):
            self.task('portal').get_catalog()
        with self.assertRaises(AccessError):
            self.task('owner')._media_path('../../etc/passwd')
        self.assertIsNone(self.task('owner')._media_path(self.fin_key, '../../etc/passwd'))

    def test_progress_is_private_and_persists(self):
        self.task('finance').record(self.fin_key, 'reviewed')
        self.task('finance').record(self.fin_key, 'position', 42)
        data = self.task('finance').get_catalog()
        self.assertTrue(data['progress'][self.fin_key]['reviewed'])
        self.assertEqual(data['progress'][self.fin_key]['position'], 42)
        self.env.cr.execute("SELECT conname FROM pg_constraint WHERE conrelid='learn_task_progress'::regclass AND contype='u'")
        self.assertTrue(self.env.cr.fetchone(), 'Progress requires a database uniqueness constraint')
        self.assertNotIn(self.fin_key, self.task('owner').get_catalog()['progress'])
        progress = self.env['learn.task.progress'].with_user(self.people['owner'])
        self.assertFalse(progress.search([('user_id', '=', self.people['finance'].id)]))
        mine = self.env['learn.task.progress'].with_user(self.people['finance']).search([])
        with self.assertRaises(AccessError):
            mine.write({'quiz_passed': True})
        with self.assertRaises(AccessError):
            mine.create({'user_id': self.people['owner'].id, 'company_id': self.env.company.id,
                         'task_key': self.fin_key})

    def test_reject_invalid_progress(self):
        for value in (-1, float('inf'), float('nan'), 'not-a-time', 10000):
            with self.assertRaises(ValidationError):
                self.task('finance').record(self.fin_key, 'position', value)
        with self.assertRaises(ValidationError):
            self.task('finance').record(self.fin_key, 'quiz_passed')
        with self.assertRaises(AccessError):
            self.task('finance').record(self.admin_key, 'reviewed')

    def test_quiz_is_graded_on_server(self):
        q = catalog()['quizzes']['finance']
        wrong = (q['correct'] + 1) % len(q['options'])
        self.assertFalse(self.task('finance').check_quiz('finance', wrong)['correct'])
        self.assertTrue(self.task('finance').check_quiz('finance', q['correct'])['correct'])
        self.assertTrue(self.task('finance').get_catalog()['progress']['quiz:finance']['quiz_passed'])
        with self.assertRaises(AccessError):
            self.task('clinical').check_quiz('finance', q['correct'])
        with self.assertRaises(ValidationError):
            self.task('finance').check_quiz('finance', True)

    def test_coach_english_and_vietnamese_cite_authored_task(self):
        for question in ('How do I receive part payment?', 'thanh toán một phần'):
            answer = self.task('finance').answer(question, 'fin_invoices')
            self.assertTrue(answer['matched'], question)
            self.assertEqual(answer['key'], self.fin_key)
            self.assertEqual(answer['steps'], self.task('finance')._task(self.fin_key)['steps'])

    def test_coach_refuses_clinical_and_current_patient_amounts(self):
        for question in ('What antibiotic dose should I give?', 'lieu khang sinh la bao nhieu',
                         'What is this patient balance?', 'How much does wound care cost?'):
            self.assertFalse(self.task('owner').answer(question)['matched'], question)

    def test_unknown_and_wrong_role_questions_do_not_invent_answers(self):
        with patch.object(type(self.env['learn.intent']), '_provider', return_value=(None, '', '')):
            self.assertFalse(self.task('finance').answer('teleport the helicopter')['matched'])
            self.assertFalse(self.task('clinical').answer('add or disable a user')['matched'])

    def test_provider_key_is_validated_and_failure_is_safe(self):
        class Provider:
            def generate_text(self, *args, **kwargs):
                return 'administration.add-or-disable-a-user'
        with patch.object(type(self.env['learn.intent']), '_provider', return_value=(Provider(), 'llama', 'http://localhost')):
            with patch.object(type(self.env['ai.egress.log']), 'guard', return_value=True):
                self.assertFalse(self.task('clinical').answer('unusual request xyzzy')['matched'])
        class Broken:
            def generate_text(self, *args, **kwargs):
                raise RuntimeError('provider unavailable')
        with patch.object(type(self.env['learn.intent']), '_provider', return_value=(Broken(), 'llama', 'http://localhost')):
            with patch.object(type(self.env['ai.egress.log']), 'guard', return_value=True):
                self.assertFalse(self.task('finance').answer('unusual request xyzzy')['matched'])

    def test_content_is_complete_and_uses_learning_language(self):
        data = catalog()
        keys = {t['key'] for t in data['tasks']}
        self.assertEqual(len(keys), len(data['tasks']))
        for task in data['tasks']:
            for field in ('title', 'title_vi', 'goal', 'before', 'steps', 'success', 'trouble', 'roles'):
                self.assertTrue(task[field], (task['key'], field))
            self.assertTrue(set(task['related']) <= keys)
            visible = json.dumps({k: task[k] for k in ('title','goal','before','steps','success','trouble','warning')}).lower()
            for phrase in ('acceptance result', 'test data', 'test cases', 'uat-', '.xlsx', '.docx', 'review edition'):
                self.assertNotIn(phrase, visible)
        for path in data['paths'].values():
            self.assertTrue(set(path) <= keys)
