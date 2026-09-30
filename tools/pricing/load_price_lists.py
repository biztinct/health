# -*- coding: utf-8 -*-
"""Load the regional price list workbooks through the SAME upload wizard
staff use (Pricing Rules > Import Price List), as an owner so the rules are
approved on import. `odoo shell` script (carejiox-deploy -x).

    PRICE_FILES="/tmp/pricelists/Hanoi.xlsx:/tmp/pricelists/HCMC.xlsx"
    PRICE_CHECK_ONLY=1   # optional: check-only, nothing saved
"""
import base64
import os

files = [f for f in os.environ.get('PRICE_FILES', '').split(':') if f]
check_only = os.environ.get('PRICE_CHECK_ONLY') == '1'
assert files, 'set PRICE_FILES'

owner_group = env.ref('health_base.group_healthcare_owner')  # noqa: F821
owner = env['res.users'].search(  # noqa: F821
    [('group_ids', 'in', owner_group.id), ('share', '=', False), ('active', '=', True)],
    order='id', limit=1)
assert owner, 'no active owner user'
wenv = env(user=owner, context=dict(env.context, lang='en_US'))  # noqa: F821
engine = wenv['advanced.pricing.config'].get_config().default_engine_id
if not engine:
    engine = wenv['advanced.pricing.engine'].search([], limit=1)
assert engine, 'no pricing engine'
print('owner=%s engine=%s check_only=%s' % (owner.login, engine.name, check_only))

for path in files:
    with open(path, 'rb') as fh:
        data = base64.b64encode(fh.read())
    wiz = wenv['advanced.pricing.import.wizard'].create({
        'file': data, 'filename': os.path.basename(path), 'engine_id': engine.id,
        'import_type': 'both', 'replace_existing': True, 'approve_rules': True,
    })
    (wiz.action_check if check_only else wiz.import_rules)()
    print(wiz.import_log)
    print('=' * 70)

if not check_only:
    env.cr.commit()  # noqa: F821
