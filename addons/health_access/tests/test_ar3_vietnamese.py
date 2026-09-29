# -*- coding: utf-8 -*-
"""ACCESS AR-3 — the clinic's Access home in Vietnamese.

  * T2  `get_board()` for a Vietnamese reader: the headline, the area labels
        and the hand-over state words are Vietnamese; for an English reader
        they are exactly what they were.
  * T3  the roles and abilities read Vietnamese for that reader after
        `apply_catalogue_vi` (the 19.0.1.7.0 migration's job); the English
        values are untouched; a row somebody has reworded is left alone; a
        second run writes nothing.
  *     this module's catalogue loads (the python half — the area words live
        here, not in `biz_access`).

Nothing changes for an English user: every assertion on the English side is
"the same words as before".
"""
from odoo.tests import TransactionCase, tagged
from odoo.tools.translate import code_translations

from odoo.addons.health_access import hooks
from odoo.addons.health_access.catalogue_vi import VI, apply_catalogue_vi

VI_AREAS = {'Chăm sóc lâm sàng', 'Lễ tân & CRM', 'Vận hành', 'Tài chính',
            'Quản trị'}
EN_AREAS = {'Clinical care', 'Front desk & CRM', 'Operations', 'Finance',
            'Administration'}


@tagged('post_install', '-at_install')
class TestAr3Vietnamese(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not cls.env['res.lang'].search_count(
                [('code', '=', 'vi_VN'), ('active', '=', True)]):
            cls.env['res.lang']._activate_lang('vi_VN')
        apply_catalogue_vi(cls.env)
        owner = cls.env.ref('health_access.role_owner')
        cls.reader_vi = cls.env['res.users'].create({
            'name': 'AR3 Vietnamese owner', 'login': 'ar3.vi@example.test',
            'lang': 'vi_VN',
            'group_ids': [(6, 0, (owner.group_ids
                                  | cls.env.ref('base.group_user')).ids)]})
        cls.reader_en = cls.env['res.users'].create({
            'name': 'AR3 English owner', 'login': 'ar3.en@example.test',
            'lang': 'en_US',
            'group_ids': [(6, 0, (owner.group_ids
                                  | cls.env.ref('base.group_user')).ids)]})

    def _board(self, user):
        return self.env['biz.access'].with_user(user).with_context(
            lang=user.lang).get_board()

    # ------------------------------------------------------------------ T2
    def test_01_the_board_reads_vietnamese_for_a_vietnamese_reader(self):
        vi, en = self._board(self.reader_vi), self._board(self.reader_en)
        self.assertNotEqual(vi['headline'], en['headline'])
        self.assertNotIn('plain English', vi['headline'])
        self.assertIn('plain English', en['headline'])
        vi_labels = {a['label'] for a in vi['areas']}
        en_labels = {a['label'] for a in en['areas']}
        self.assertTrue(vi_labels and vi_labels <= VI_AREAS | {'Tất cả'},
                        'area labels still English: %s' % vi_labels)
        self.assertTrue(en_labels - {'All'} <= EN_AREAS,
                        'the English board changed: %s' % en_labels)
        facade = self.env['biz.access']
        for state in ('active', 'expired', 'revoked'):
            en_word = facade.with_context(lang='en_US')._state_label(state)
            vi_word = facade.with_context(lang='vi_VN')._state_label(state)
            self.assertNotEqual(vi_word, en_word, state)

    def test_02_area_selection_on_a_form_is_translated(self):
        Role = self.env['biz.access.role']
        vi = dict(Role.with_context(lang='vi_VN')._fields['area']
                  ._description_selection(self.env(context={'lang': 'vi_VN'})))
        en = dict(Role._fields['area']._description_selection(
            self.env(context={'lang': 'en_US'})))
        self.assertEqual(vi['clinical'], 'Chăm sóc lâm sàng')
        self.assertEqual(en['clinical'], 'Clinical care')

    # ------------------------------------------------------------------ T3
    def test_03_roles_and_abilities_read_vietnamese(self):
        nurse = self.env.ref('health_access.role_nurse')
        self.assertEqual(nurse.with_context(lang='vi_VN').name, 'Y tá')
        self.assertEqual(nurse.with_context(lang='en_US').name, 'Nurse')
        owner = self.env.ref('health_access.role_owner')
        self.assertEqual(owner.with_context(lang='vi_VN').name, 'Chủ sở hữu')
        Ability = self.env['biz.access.ability'].with_context(
            active_test=False)
        care = Ability.search([('technical_key', '=', 'care-base')], limit=1)
        self.assertEqual(care.with_context(lang='en_US').name,
                         "See the clinic's patients and visits")
        self.assertEqual(care.with_context(lang='vi_VN').name,
                         VI["See the clinic's patients and visits"])
        board = self._board(self.reader_vi)
        names = {p['name'] for p in board.get('profiles') or []}
        self.assertIn('Y tá', names)
        self.assertNotIn('Nurse', names)

    def test_04_a_second_run_writes_nothing_and_own_words_stay(self):
        self.assertEqual(apply_catalogue_vi(self.env), 0)
        doctor = self.env.ref('health_access.role_doctor')
        doctor.with_context(lang='vi_VN').write({'name': 'Bác sĩ điều trị'})
        apply_catalogue_vi(self.env)
        self.assertEqual(doctor.with_context(lang='vi_VN').name,
                         'Bác sĩ điều trị', 'somebody\'s own words were '
                                            'overwritten')
        # A role renamed in English is not ours any more: left alone.
        crm = self.env.ref('health_access.role_crm')
        crm.with_context(lang='en_US').write({'name': 'Front desk team'})
        crm.with_context(lang='vi_VN').write({'name': 'Front desk team'})
        apply_catalogue_vi(self.env)
        self.assertEqual(crm.with_context(lang='vi_VN').name,
                         'Front desk team')

    def test_05_every_seeded_sentence_has_its_vietnamese(self):
        english = set()
        for _key, _area, _seq, name, description, _g in hooks.ABILITIES:
            english |= {name, description}
        for name, notes in hooks.ROLE_NOTES.items():
            english |= {name, notes['description']}
        self.assertEqual(english - set(VI), set(),
                         'a seeded sentence has no Vietnamese')

    def test_06_the_area_words_load_from_this_module(self):
        py = code_translations.get_python_translations('health_access',
                                                       'vi_VN')
        self.assertEqual(py.get('Clinical care'), 'Chăm sóc lâm sàng')
        self.assertEqual(py.get('Administration'), 'Quản trị')
