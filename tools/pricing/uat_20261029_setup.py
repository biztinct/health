"""Apply the client-authorized acceptance configuration on carejiox only.

Run with carejiox-deploy -D carejiox -x. No catalogue prices are hardcoded here;
the client-approved 21 October catalogue remains authoritative.
"""
assert env.cr.dbname == 'carejiox', 'Acceptance data belongs only in carejiox'
owner = env['res.users'].search([('login', '=', 'uat20261021.owner')], limit=1)
assert owner
rules = env['advanced.pricing.rule'].with_user(owner).with_context(mail_create_nosubscribe=True)
engine = env['advanced.pricing.engine'].browse(7).exists()
assert engine and engine.name == 'Client UAT 20261013 V01.01'
pricelist = env['product.pricelist'].browse(7)
pricelist.with_user(owner).write({'active': True, 'discount_on_base_only': True})
for rule in rules.search([('engine_id', '=', engine.id), ('action_type', '=', 'add')]):
    rule.write({'action_scope': 'line', 'max_quantity': 0})
    rule.action_approve()

def upsert(name, values):
    domain = [('engine_id', '=', engine.id), ('name', '=', name)]
    rule = rules.search(domain, limit=1)
    vals = dict(values, name=name, engine_id=engine.id, active=True)
    if rule:
        rule.write(vals)
    else:
        rule = rules.create(vals)
    rule.action_approve()
    return rule.id

for product_id, region, sequence in [(589, 'Hanoi', 1), (593, 'Hanoi', 1),
                                      (637, 'HCMC', 3), (632, 'HCMC', 2)]:
    upsert('Client UAT - Subsequent units - %s' % product_id, {
        'applied_on': '0_product_variant', 'product_id': product_id,
        'region': region, 'sequence': sequence, 'level': '1',
        'action_type': 'subsequent_fixed', 'action_value': 50000,
        'min_quantity': 2,
    })
upsert('Client UAT - Additional IV bottles', {
    'applied_on': '0_product_variant', 'product_id': 636,
    'region': 'HCMC', 'sequence': 3, 'level': '1',
    'action_type': 'per_unit', 'action_value': 150000, 'action_scope': 'line',
    'per_unit_field': 'iv_fluid_count', 'iv_fluid_count_min': 2,
})
nursing = env['product.category'].search([('name', '=', 'Nurse Service')], limit=1)
assert nursing
upsert('Client UAT - Hanoi nursing distance once per booking', {
    'applied_on': '2_product_category', 'categ_id': nursing.id,
    'region': 'Hanoi', 'sequence': 5, 'level': '1',
    'action_type': 'add', 'action_value': 50000, 'action_scope': 'booking',
    'distance_min': 5, 'distance_max': 8,
})
bookings = env['health.fieldservice.order'].browse(list(range(9666, 9683))).exists()
assert len(bookings) == 17
bookings.mapped('patient_id').write({'specific_property_product_pricelist': pricelist.id})
orders = bookings.mapped('sale_order_id').with_user(owner)
orders.write({'pricelist_id': pricelist.id})
orders._compute_fso_fields()
orders._compute_time_factors()
orders.action_recalculate_advanced_prices()
env.cr.commit()
print('UAT_CONFIG_APPLIED', len(orders), 'quotes', rules.search_count([('engine_id', '=', engine.id)]), 'rules')
