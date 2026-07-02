# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged

from ..models.bi_expression import (
    ExpressionError, validate_expression)

KNOWN = {'Revenue': True, 'Cost': True, 'order_date': True, 'State': True}


@tagged('biz_bi', 'post_install', '-at_install')
class TestExpression(TransactionCase):

    def ok(self, text, aggregates=False):
        return validate_expression(text, KNOWN, allow_aggregates=aggregates)

    def bad(self, text, aggregates=False):
        with self.assertRaises(ExpressionError):
            validate_expression(text, KNOWN, allow_aggregates=aggregates)

    def test_accepts_arithmetic(self):
        used = self.ok('([Revenue] - [Cost]) / [Revenue]')
        self.assertEqual(used, {'Revenue', 'Cost'})

    def test_accepts_functions(self):
        self.ok('iff([Revenue] > 0, [Revenue], 0)')
        self.ok('round([Revenue] * 1.08, 0)')
        self.ok('coalesce([Cost], 0)')
        self.ok('year([order_date])')
        self.ok('date_diff("day", [order_date], today())')
        self.ok('concat(upper([State]), "-", "X")')
        self.ok('[Revenue] if [Cost] > 100 else 0')

    def test_accepts_aggregates_in_measure_context(self):
        self.ok('ratio([Revenue], [Cost])', aggregates=True)
        self.ok('sum([Revenue]) - sum([Cost])', aggregates=True)

    def test_rejects_aggregates_in_row_context(self):
        self.bad('sum([Revenue])', aggregates=False)

    def test_rejects_unknown_field(self):
        self.bad('[Nope] + 1')

    def test_rejects_unknown_function(self):
        self.bad('exec("x")')
        self.bad('pg_sleep(10)')

    def test_rejects_python_constructs(self):
        self.bad('__import__("os")')
        self.bad('[Revenue].__class__')
        self.bad('(lambda: 1)()')
        self.bad('[x for x in [1]]')
        self.bad('a.b')

    def test_rejects_sql_injection_attempts(self):
        self.bad("'; DROP TABLE res_users; --")
        self.bad('[Revenue]; DELETE FROM res_users')
        self.bad('"" or 1=1')  # bare string expr with or → string is fine,
        # but identifier-less comparison chain must still parse strictly

    def test_rejects_bad_date_unit(self):
        self.bad('date_diff("fortnight", [order_date], today())')
        self.bad('date_diff([State], [order_date], today())')

    def test_rejects_empty_and_unclosed(self):
        self.bad('')
        self.bad('[Revenue')
        self.bad('[]')
