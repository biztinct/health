# -*- coding: utf-8 -*-
"""One-off clean start before loading the 2026-09-22 price lists (owner
decision 2026-09-30: "Everything: clean start", contacts and leads KEPT).

Deletes every booking, quote, invoice/credit note, payment and visit record,
every old price rule, and every service product that is not framework data
(the old price list plus the service names created by the June data move),
then the product categories left empty.

Runs as an `odoo shell` script (carejiox-deploy -x) so it holds the deploy
lock with the service stopped. DRY RUN unless PURGE_COMMIT=1 is exported:
the dry run prints every table and row count it would touch and rolls back.

Deletion walks the foreign keys itself: for each row set it first deletes
the children that reference it through RESTRICT / NO ACTION / CASCADE keys
(so a restricting child such as an EVV event cannot abort the run half way),
and leaves SET NULL keys to PostgreSQL. A guard refuses to touch the tables
that must survive (contacts, leads, staff, users, companies).
"""
import os
from collections import Counter

COMMIT = os.environ.get('PURGE_COMMIT') == '1'

PROTECTED = {
    'res_partner', 'crm_lead', 'hr_employee', 'res_users', 'res_company',
    'res_groups', 'ir_model', 'ir_model_fields', 'product_category',
    'account_account', 'account_journal', 'account_tax', 'uom_uom',
    'health_facility', 'health_catchment_province', 'advanced_pricing_engine',
}

cr = env.cr  # noqa: F821 (odoo shell)
counts = Counter()


def fks_to(table):
    cr.execute("""
        SELECT cl.relname, att.attname, con.confdeltype
          FROM pg_constraint con
          JOIN pg_class cl ON cl.oid = con.conrelid
          JOIN pg_class rt ON rt.oid = con.confrelid
          JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = con.conkey[1]
         WHERE con.contype = 'f' AND rt.relname = %s AND array_length(con.conkey, 1) = 1
    """, (table,))
    return cr.fetchall()


def has_id(table):
    cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name='id'", (table,))
    return bool(cr.fetchone())


def purge(table, ids, depth=0):
    ids = list(set(ids))
    if not ids:
        return
    if table in PROTECTED:
        raise RuntimeError('refusing to delete from %s (%d rows)' % (table, len(ids)))
    for child, col, deltype in fks_to(table):
        if deltype not in ('a', 'r', 'c') or child == table:
            continue
        if has_id(child):
            cr.execute('SELECT id FROM "%s" WHERE "%s" = ANY(%%s)' % (child, col), (ids,))
            purge(child, [r[0] for r in cr.fetchall()], depth + 1)
        else:  # many2many relation table
            cr.execute('DELETE FROM "%s" WHERE "%s" = ANY(%%s)' % (child, col), (ids,))
            if cr.rowcount:
                counts[child] += cr.rowcount
    cr.execute('DELETE FROM "%s" WHERE id = ANY(%%s)' % table, (ids,))
    counts[table] += cr.rowcount


def ids_of(sql, params=()):
    cr.execute(sql, params)
    return [r[0] for r in cr.fetchall()]


def purge_model_leftovers(models):
    """Chatter, followers, activities and attachments of deleted records."""
    for model in models:
        table = model.replace('.', '_')
        for aux, col in (('mail_message', 'model'), ('mail_followers', 'res_model'),
                         ('mail_activity', 'res_model'), ('ir_attachment', 'res_model')):
            cr.execute(
                'DELETE FROM "%s" WHERE "%s" = %%s AND res_id IS NOT NULL '
                'AND NOT EXISTS (SELECT 1 FROM "%s" t WHERE t.id = "%s".res_id)'
                % (aux, col, table, aux), (model,))
            counts['%s (%s)' % (aux, model)] += cr.rowcount
        cr.execute(
            'DELETE FROM ir_model_data d WHERE d.model = %%s '
            'AND NOT EXISTS (SELECT 1 FROM "%s" t WHERE t.id = d.res_id)' % table, (model,))
        counts['ir_model_data (%s)' % model] += cr.rowcount


cr.execute('SAVEPOINT purge')
before = {}
for t in ('res_partner', 'crm_lead', 'hr_employee', 'res_users'):
    cr.execute('SELECT count(*) FROM "%s"' % t)
    before[t] = cr.fetchone()[0]

# 1. bookings and everything hanging off them
purge('health_fieldservice_order', ids_of('SELECT id FROM health_fieldservice_order'))
# 2. quotes, invoices, payments
purge('sale_order', ids_of('SELECT id FROM sale_order'))
purge('account_payment', ids_of('SELECT id FROM account_payment'))
purge('account_move', ids_of(
    "SELECT id FROM account_move WHERE move_type IN "
    "('out_invoice','out_refund','in_invoice','in_refund','out_receipt','in_receipt') "
    "OR id IN (SELECT move_id FROM account_move_line WHERE account_id IN "
    "(SELECT id FROM account_account WHERE account_type IN ('asset_receivable','liability_payable')))"))
# client packages, receivables log and payment records (test money data;
# the real receivables arrive with the client's next files)
for table in ('account_bank_statement_line', 'health_service_package',
              'health_ar_transaction_log', 'health_payment_transaction'):
    cr.execute("SELECT to_regclass(%s)", (table,))
    if cr.fetchone()[0]:
        purge(table, ids_of('SELECT id FROM "%s"' % table))
# 3. old price rules
purge('advanced_pricing_rule', ids_of('SELECT id FROM advanced_pricing_rule'))
# 4. service products that are not framework data
framework = ids_of(
    "SELECT res_id FROM ir_model_data WHERE model='product.template' "
    "AND module NOT IN ('__export__', '__import__')")
tmpl_ids = ids_of(
    "SELECT id FROM product_template WHERE type='service' AND NOT (id = ANY(%s))",
    (framework or [0],))
purge('product_product', ids_of(
    'SELECT id FROM product_product WHERE product_tmpl_id = ANY(%s)', (tmpl_ids or [0],)))
purge('product_template', tmpl_ids)
# 5. categories left empty (never the framework ones)
PROTECTED.discard('product_category')
for _round in range(3):
    empty = ids_of("""
        SELECT c.id FROM product_category c
         WHERE NOT EXISTS (SELECT 1 FROM product_template t WHERE t.categ_id = c.id)
           AND NOT EXISTS (SELECT 1 FROM product_category k WHERE k.parent_id = c.id)
           AND NOT EXISTS (SELECT 1 FROM ir_model_data d WHERE d.model = 'product.category'
                           AND d.res_id = c.id AND d.module NOT IN ('__export__', '__import__'))
    """)
    if not empty:
        break
    purge('product_category', empty)
PROTECTED.add('product_category')

purge_model_leftovers([
    'health.fieldservice.order', 'sale.order', 'account.move', 'account.payment',
    'advanced.pricing.rule', 'product.template', 'product.product',
    'health.service.package', 'health.payment.transaction',
])

# Settings that pointed at a deleted service
cr.execute("""
    UPDATE ir_config_parameter SET value = ''
     WHERE key IN ('health_self_booking.fallback_service_product_id',
                   'health_workflow_auto.offer_service_product_id')
       AND value ~ '^[0-9]+$'
       AND value::int NOT IN (SELECT id FROM product_product)
""")
counts['ir_config_parameter cleared'] += cr.rowcount

for t, n in before.items():
    cr.execute('SELECT count(*) FROM "%s"' % t)
    after = cr.fetchone()[0]
    assert after == n, '%s changed %s -> %s' % (t, n, after)

print('=== %s ===' % ('COMMITTED' if COMMIT else 'DRY RUN (rolled back)'))
for table, n in sorted(counts.items(), key=lambda kv: -kv[1]):
    if n:
        print('%8d  %s' % (n, table))
print('kept: %s' % before)
if COMMIT:
    cr.execute('RELEASE SAVEPOINT purge')
    cr.commit()
else:
    cr.execute('ROLLBACK TO SAVEPOINT purge')
    cr.rollback()
