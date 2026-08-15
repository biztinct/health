# -*- coding: utf-8 -*-
"""Seeding and back-fill for the Selection -> Many2one conversion.

Two jobs, both idempotent so they are safe to re-run and safe on a database
that is only half-way through the rollout:

  `seed_lookup_values`   — creates the vocabularies and their values from
                           lookup_registry.CATEGORIES. Runs in health_base, for
                           EVERY category, whether or not the module that uses
                           it is installed: the rows are inert data until
                           something points at them.

  `snapshot_legacy_columns` — copies the old varchar values into an audit
                           table BEFORE the schema changes. See below.

  `backfill_lookup_field` — fills a newly added Many2one from the varchar the
                           old Selection left behind, matching on code. Values
                           with no matching code are left NULL and logged, never
                           guessed at.

WHY A SNAPSHOT, AND NOT "THE OLD COLUMN STAYS"
----------------------------------------------
An earlier version of this file claimed the old varchar survives the upgrade.
IT DOES NOT. When a field is removed from a model, Odoo deletes its
`ir.model.fields` row at the end of the upgrade and DROPS THE COLUMN with it.
On the first UAT run that cost us the `service_interest` of the crm.lead rows
whose value ("home_visit"/"clinic_visit") was not in the old Selection list —
the back-fill correctly refused to guess, but the evidence was then dropped
before anyone could act on the warning.

So `snapshot_legacy_columns` copies every old value into
`health_lookup_conversion_audit` BEFORE the schema changes (it runs from a
PRE-migrate, while the columns still exist). Anything the back-fill cannot map
is then still recoverable by hand from that table. The snapshot is cheap, it
is written once, and it is the only durable record of the pre-conversion
state.
"""
import logging

from .lookup_registry import CATEGORIES

_logger = logging.getLogger(__name__)


def seed_lookup_values(env):
    """Create/refresh the vocabularies. Never overwrites client edits."""
    Category = env['health.lookup.category'].with_context(active_test=False)
    Value = env['health.lookup.value'].with_context(active_test=False)

    for code, spec in CATEGORIES.items():
        category = Category.search([('code', '=', code)], limit=1)
        if not category:
            category = Category.create({
                'code': code,
                'name': spec['name'],
                'used_by': ', '.join(spec['used_by']),
            })
        elif category.used_by != ', '.join(spec['used_by']):
            # Keep the "where is this used" hint current without touching the
            # name, which the client may well have rewritten.
            category.used_by = ', '.join(spec['used_by'])

        existing = {v.code: v for v in Value.search([('category_id', '=', category.id)])}
        for index, (value_code, label_en, label_vi) in enumerate(spec['values']):
            value = existing.get(value_code)
            if not value:
                value = Value.create({
                    'category_id': category.id,
                    'code': value_code,
                    'name': label_en,
                    'sequence': (index + 1) * 10,
                })
            if label_vi:
                # Only fill a Vietnamese label that is not there yet — an empty
                # translation reads back as the English fallback.
                current = value.with_context(lang='vi_VN').name
                if current == value.with_context(lang='en_US').name:
                    value.with_context(lang='vi_VN').name = label_vi

    _logger.info('lookup seed: %s vocabularies, %s values',
                 len(CATEGORIES), sum(len(s['values']) for s in CATEGORIES.values()))


def backfill_lookup_field(env, model_name, old_field, new_field, category_code):
    """Point `new_field` at the lookup row matching the old varchar value.

    Returns (filled, unmapped_values). Rows whose old value has no matching
    code are LEFT NULL and reported — never guessed at.
    """
    if model_name not in env:
        _logger.info('lookup back-fill: %s not installed, skipped', model_name)
        return 0, []

    table = env[model_name]._table
    env.cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s
    """, (table, old_field))
    if not env.cr.fetchone():
        _logger.info('lookup back-fill: %s.%s column absent, skipped',
                     table, old_field)
        return 0, []

    values = env['health.lookup.value'].with_context(active_test=False).search(
        [('category_code', '=', category_code)])
    by_code = {v.code: v.id for v in values}
    if not by_code:
        _logger.warning('lookup back-fill: vocabulary %s is empty, skipped',
                        category_code)
        return 0, []

    env.cr.execute(
        'SELECT DISTINCT %s FROM %s WHERE %s IS NOT NULL' % (
            old_field, table, old_field))
    present = [r[0] for r in env.cr.fetchall() if r[0]]

    filled, unmapped = 0, []
    for old_value in present:
        target = by_code.get(old_value)
        if not target:
            unmapped.append(old_value)
            continue
        env.cr.execute(
            'UPDATE %s SET %s = %%s WHERE %s = %%s AND %s IS NULL' % (
                table, new_field, old_field, new_field),
            (target, old_value))
        filled += env.cr.rowcount

    if unmapped:
        _logger.error(
            'lookup back-fill: %s.%s has values with no code in vocabulary '
            '%s: %s — those rows were left EMPTY. Recover them from '
            'health_lookup_conversion_audit.', table, old_field,
            category_code, unmapped)
    _logger.info('lookup back-fill: %s.%s -> %s, %s rows',
                 table, old_field, new_field, filled)
    return filled, unmapped


def backfill_module(env, module):
    """Back-fill every conversion a module owns. Used by its post-migrate."""
    from .lookup_registry import conversions_for
    results = []
    for model_name, old_field, new_field, category_code, _mod in conversions_for(module):
        results.append((model_name, old_field) + backfill_lookup_field(
            env, model_name, old_field, new_field, category_code))
    return results


def snapshot_legacy_columns(env):
    """Copy every pre-conversion Selection value into an audit table.

    MUST run from a PRE-migrate: Odoo drops the old column when it removes the
    field at the end of the upgrade, so this is the last moment the data
    exists. Idempotent — a (model, field) pair already captured is skipped, so
    re-running never doubles up or overwrites an earlier, truer snapshot.
    """
    from .lookup_registry import CONVERSIONS

    env.cr.execute("""
        CREATE TABLE IF NOT EXISTS health_lookup_conversion_audit (
            id serial PRIMARY KEY,
            model_name varchar NOT NULL,
            field_name varchar NOT NULL,
            res_id integer NOT NULL,
            old_value varchar,
            captured_at timestamp NOT NULL DEFAULT now()
        )
    """)
    env.cr.execute("""
        CREATE INDEX IF NOT EXISTS health_lookup_conversion_audit_key
            ON health_lookup_conversion_audit (model_name, field_name, res_id)
    """)

    captured = 0
    for model_name, old_field, _new, _cat, _mod in CONVERSIONS:
        # Derived, NOT env[model]._table: this runs from a pre-migrate, before
        # the module's own models are in the registry, so looking them up would
        # silently skip almost everything (it did — only hr.employee, which
        # comes from a dependency, got captured on the first run).
        table = model_name.replace('.', '_')
        env.cr.execute("""
            SELECT 1 FROM information_schema.columns
             WHERE table_name = %s AND column_name = %s
        """, (table, old_field))
        if not env.cr.fetchone():
            continue  # already converted on this database
        env.cr.execute("""
            SELECT 1 FROM health_lookup_conversion_audit
             WHERE model_name = %s AND field_name = %s LIMIT 1
        """, (model_name, old_field))
        if env.cr.fetchone():
            continue  # already snapshotted
        env.cr.execute(
            "INSERT INTO health_lookup_conversion_audit "
            "(model_name, field_name, res_id, old_value) "
            "SELECT %%s, %%s, id, %s FROM %s WHERE %s IS NOT NULL" % (
                old_field, table, old_field),
            (model_name, old_field))
        captured += env.cr.rowcount
        _logger.info('lookup snapshot: %s.%s captured %s value(s)',
                     table, old_field, env.cr.rowcount)
    _logger.info('lookup snapshot: %s legacy value(s) preserved', captured)
    return captured


def backfill_symptom_urgency(env):
    """health.symptom.urgency_level -> health.urgency.level (not the generic table).

    Urgency is already its own client-editable model with its own Master Data
    tab, so symptoms point at THAT rather than gaining a parallel vocabulary.
    Its codes differ from the retired Selection values, hence the explicit map
    in lookup_registry.SYMPTOM_URGENCY_MAP.
    """
    from .lookup_registry import SYMPTOM_URGENCY_MAP

    env.cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'health_symptom' AND column_name = 'urgency_level'
    """)
    if not env.cr.fetchone():
        _logger.info('symptom urgency back-fill: column absent, skipped')
        return 0

    levels = {l.code: l.id for l in env['health.urgency.level']
              .with_context(active_test=False).search([])}
    filled = 0
    for old_value, level_code in SYMPTOM_URGENCY_MAP.items():
        target = levels.get(level_code)
        if not target:
            _logger.error('symptom urgency back-fill: no health.urgency.level '
                          'with code %s — rows left empty', level_code)
            continue
        env.cr.execute(
            "UPDATE health_symptom SET urgency_level_id = %s "
            " WHERE urgency_level = %s AND urgency_level_id IS NULL",
            (target, old_value))
        filled += env.cr.rowcount
    _logger.info('symptom urgency back-fill: %s rows', filled)
    return filled


def repoint_bi_fields(env):
    """Point BI dataset columns at the converted Many2one.

    WHY THIS IS NOT OPTIONAL AND WHY NO GREP FINDS IT
    -------------------------------------------------
    biz_bi datasets reference model columns as DATABASE ROWS (`bi.field`),
    not as source code, so the static sweeps that caught every python and
    view reference are blind to them. The first symptom is a matview that
    will not build — "column t23.facility_type does not exist" at registry
    load — because the gold SELECT still names a column Odoo dropped.

    A converted column keeps its meaning, so the BI field is REPOINTED, not
    deleted: it stays a dimension, but stores an id and is LABELLED from the
    lookup record (`relation_model`), which is how biz_bi already renders
    every other many2one. Grouping therefore happens on the id and the label
    follows the reader's language for free.

    MUST RUN IN THE `end` PHASE. A post-migrate on health_base runs while the
    registry is still being built, and the converted fields on hr.employee and
    crm.lead are contributed by health_fieldservice / health_crm, which load
    LATER — so `model._fields.get('employment_type_id')` is legitimately None
    and eleven of thirteen columns are skipped. `end-` scripts run after every
    module is loaded. (biz_bi's own end-backfill-relation-model.py exists for
    the same reason.)

    Idempotent, and a no-op when biz_bi is not installed.
    """
    from .lookup_registry import CONVERSIONS

    if 'bi.field' not in env:
        _logger.info('bi repoint: biz_bi not installed, skipped')
        return 0

    targets = {}
    for model_name, old_field, new_field, _cat, _mod in CONVERSIONS:
        targets.setdefault(model_name, {})[old_field] = new_field
    targets.setdefault('health.symptom', {})['urgency_level'] = 'urgency_level_id'

    repointed, datasets = 0, env['bi.dataset']
    for bi_field in env['bi.field'].sudo().search([]):
        source = bi_field.node_id.source_id
        model_name = getattr(source, 'model_name', False)
        new_field = targets.get(model_name, {}).get(bi_field.technical_name)
        if not new_field:
            continue
        model = env.get(model_name)
        odoo_field = model._fields.get(new_field) if model is not None else None
        if odoo_field is None:
            _logger.error('bi repoint: %s.%s missing, leaving %r alone',
                          model_name, new_field, bi_field.name)
            continue
        old_name = bi_field.technical_name
        bi_field.write({
            'technical_name': new_field,
            # biz_bi stores a many2one as its id and labels it via
            # relation_model — see bi_dataset._classify / _attach_relation_labels.
            'data_type': 'integer',
            'relation_model': odoo_field.comodel_name,
            'selection_labels_json': False,
        })
        datasets |= bi_field.dataset_id
        repointed += 1
        _logger.info('bi repoint: %s.%s -> %s (dataset %r)',
                     model_name, old_name, new_field, bi_field.dataset_id.name)

    # Rebuild any gold dataset whose SELECT named a dropped column.
    for dataset in datasets:
        if getattr(dataset, 'storage_mode', 'live') != 'gold':
            continue
        try:
            dataset._publish_gold()
            _logger.info('bi repoint: republished gold dataset %r', dataset.name)
        except Exception:
            _logger.exception('bi repoint: could not republish %r — the '
                              'dataset stays live-query until someone '
                              'republishes it by hand', dataset.name)

    _logger.info('bi repoint: %s field(s) across %s dataset(s)',
                 repointed, len(datasets))
    return repointed
