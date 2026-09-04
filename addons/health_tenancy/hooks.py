# -*- coding: utf-8 -*-
"""Two doors, gated to the right people, and one of them switched off where it
would open nothing.

WHY A HOOK AND NOT A `ref=` IN THE DATA FILE. The roles both entries are gated
to are created by ANOTHER module's own install hook, which runs after this
module's data file is read — and a `ref()` can only point at a row that already
exists. So the entries ship ungated and the gate is written here, exactly as
`health_access` does with its own.

WHY "CUSTOMERS" IS DECIDED EVERY TIME RATHER THAN ONCE. Its action lives in a
module a customer's system never receives. On the platform's own system it
resolves and the door works; on a customer's it does not, and an entry that
opens nothing is a dead end — worse than an absence, because somebody clicks it
and gets an error. Deciding it on every run rather than once means the door
comes back on its own the day the cockpit is installed somewhere, and goes away
again if it is ever removed.
"""
import logging

_logger = logging.getLogger(__name__)

#: The entry, the action behind it, and the roles it is open to.
#:
#: OWNER AND ADMIN FOR "ABOUT", because the question it answers — which release
#: are we on, what changed, who do we ring — is one the people who run a clinic
#: ask and nobody else needs.
#:
#: OWNER ALONE FOR "CUSTOMERS", because it creates, copies and removes other
#: people's systems.
DOORS = (
    {
        'xmlid': 'health_tenancy.item_admin_about',
        'action': 'biz_tenancy.action_biz_tenancy_about',
        'roles': ('Owner', 'Admin'),
    },
    {
        'xmlid': 'health_tenancy.item_admin_customers',
        'action': 'biz_tenants.action_biz_tenants',
        'roles': ('Owner',),
    },
)


def _role_ids(env, names):
    """The bundles with these names, archived ones included."""
    Role = env['biz.access.role'].sudo().with_context(active_test=False)
    ids = []
    for name in names:
        role = Role.search([('name', '=', name)], limit=1)
        if role:
            ids.append(role.id)
        else:
            _logger.info("health_tenancy: there is no role called \"%s\" on "
                         "this system, so it was not put on the gate.", name)
    return ids


def wire_doors(env):
    """Gate both entries and switch off any whose action is not here.

    Idempotent, and safe to run again by hand or from a later migration —
    which is the point: an install hook does not fire on an upgrade, and a
    migration does not fire on an install, so anything that must be true on
    BOTH paths has to be reachable from both.
    """
    report = {'gated': [], 'switched_on': [], 'switched_off': [], 'missing': []}
    for door in DOORS:
        item = env.ref(door['xmlid'], raise_if_not_found=False)
        if not item:
            report['missing'].append(door['xmlid'])
            continue
        resolves = bool(env.ref(door['action'], raise_if_not_found=False))
        vals = {}
        if item.active != resolves:
            vals['active'] = resolves
            (report['switched_on'] if resolves
             else report['switched_off']).append(door['xmlid'])
        ids = _role_ids(env, door['roles'])
        if ids and set(item.biz_role_ids.ids) != set(ids):
            vals['biz_role_ids'] = [(6, 0, ids)]
            report['gated'].append(door['xmlid'])
        if vals:
            item.sudo().write(vals)
    _logger.info(
        "health_tenancy: doors wired — %d gated, %d switched on, %d switched "
        "off, %d missing", len(report['gated']), len(report['switched_on']),
        len(report['switched_off']), len(report['missing']))
    return report


# =============================================================================
# WHICH LEFT-MENU ENTRY BELONGS TO WHICH PART OF THE PRODUCT (SAAS H4c §3.4).
#
# ⚠ A HOOK AND NOT A DATA FILE, for a reason worth writing down. These entries
# are shipped by NINE different modules, and this one depends on three of them.
# A data file naming `health_cms_clinical.item_clin_worklist` would take the
# whole upgrade down on any system where that module is not installed — and a
# customer who has not been brought in step is exactly such a system. A hook
# skips what is not there and says how many it skipped.
#
# WHY IT IS RE-DECIDED ON EVERY RUN rather than written once: entries arrive
# with new releases, and a mapping applied once would leave every entry added
# afterwards ungated — which means visible to a clinic that did not buy it.
#
# THE PARENT CARRIES IT WHERE THERE IS ONE. A child with no key of its own
# inherits its parent's (see `cms_sidebar._feature_key_of`), so a block like
# Care Intelligence is named once rather than four times.
# =============================================================================
FEATURE_ENTRIES = {
    'care_command': (
        'health_care_command.item_care_command',
        'health_care_command_channels.item_channel_center',
        'health_care_command_channels.item_contact_capture',
        'health_care_command_channels.item_golive_studio',
        'health_access.item_crm_channel_audit',
        'health_access.item_crm_channel_messages',
        'health_access.item_crm_watch_phrases',
        'health_cms_coverage.item_crm_channels_setup',
        'health_cms_coverage.item_crm_reply_templates',
    ),
    'telehealth': (
        'health_cms_coverage.item_ops_telehealth',
    ),
    'family': (
        'health_cms_coverage.item_ops_family_links',
        'health_cms_coverage.item_ops_family_messages',
        'health_cms_coverage.item_clin_patient_portal',
    ),
    'telemonitoring': (
        'health_cms_clinical.item_clin_care_intel',
        'health_cms_clinical.item_clin_worklist',
        'health_cms_clinical.item_clin_alerts',
        'health_cms_clinical.item_clin_news2',
        'health_cms_clinical.item_clin_devices',
    ),
    'bhyt': (
        'health_cms_coverage.item_fin_bhyt_claims',
    ),
    'redinvoice': (
        'health_cms_coverage.item_fin_red_invoice_log',
    ),
    'analytics': (
        'biz_bi_cms.item_analytics_hub',
        'biz_bi_cms.item_analytics_explore',
        'biz_bi_cms.item_analytics_dashboards',
        'biz_bi_cms.item_analytics_datasets',
        'biz_bi_cms.item_analytics_sources',
        'biz_bi_cms.item_analytics_data',
        'biz_bi_cms.item_analytics_refresh',
        'biz_bi_cms.item_analytics_pipelines',
        'biz_bi_cms.item_analytics_model',
        'biz_bi_cms.item_analytics_glossary',
        'biz_bi_cms.item_analytics_settings',
        'biz_bi_cms.item_analytics_access_rules',
        'biz_bi_cms.item_analytics_ai',
        'biz_bi_cms.item_analytics_import',
    ),
    'ai': (
        'health_cms_coverage.item_clin_coding_review',
        'health_cms_coverage.item_clin_voice_notes',
    ),
    'voice': (
        'health_access.item_ops_voice',
        'health_access.item_ops_voice_calls',
        'health_access.item_ops_voice_missed',
        'health_access.item_ops_voice_recordings',
        'health_access.item_ops_voice_extensions',
        'health_access.item_ops_voice_sync',
        'health_access.item_ops_voice_config',
    ),
    'learn': (
        'health_learn.item_learn_journey',
        'health_access.item_admin_training',
        'health_access.item_admin_training_lessons',
        'health_access.item_admin_training_stations',
        'health_access.item_admin_training_progress',
        'health_access.item_admin_training_events',
        'health_access.item_admin_training_wording',
    ),
}


def wire_features(env):
    """Say which part of the product each left-menu entry belongs to.

    Idempotent and self-repairing: an entry whose module is not on this system
    is skipped and counted, and an entry that has since been given the wrong
    key is put back. Returns a report, so a test and a log line can both read
    what happened.
    """
    if 'feature_key' not in env['cms.sidebar.item']._fields:
        _logger.warning("health_tenancy: this system's left menu has no "
                        "feature column yet; nothing was wired.")
        return {'wired': [], 'missing': [], 'unchanged': 0}
    report = {'wired': [], 'missing': [], 'unchanged': 0}
    for key, xmlids in FEATURE_ENTRIES.items():
        for xmlid in xmlids:
            item = env.ref(xmlid, raise_if_not_found=False)
            if not item:
                report['missing'].append(xmlid)
                continue
            if (item.feature_key or '') == key:
                report['unchanged'] += 1
                continue
            item.sudo().write({'feature_key': key})
            report['wired'].append(xmlid)
    _logger.info("health_tenancy: %d left-menu entries were given a part of "
                 "the product, %d were already right, %d are not on this "
                 "system.", len(report['wired']), report['unchanged'],
                 len(report['missing']))
    return report


def ensure_feature_catalogue(env):
    """Put this product's ten switches in the cockpit's table.

    ⚠ WHY IT IS DONE HERE AS WELL AS FROM THE COCKPIT'S OWN DATA FILE. The
    cockpit's `<function>` runs when the cockpit is installed or upgraded, and
    it reads a registry THIS module fills at import time. Nothing guarantees
    this module has been imported by then — it does not depend on the cockpit,
    on purpose, because it also ships to every customer's system where the
    cockpit is absent. Measured on a real upgrade: the cockpit's data file ran
    first and seeded nothing, and the table stayed empty until somebody opened
    the screen.

    So the product seeds it too, from its own hook and its own migration.
    Idempotent, and skipped on any system without the cockpit.
    """
    if 'biz.feature' not in env:
        return 0
    made = env['biz.feature'].sudo().ensure_seeded()
    _logger.info("health_tenancy: the switches are in the cockpit's table "
                 "(%d new).", len(made))
    return len(made)


def post_init_hook(env):
    wire_doors(env)
    wire_features(env)
    ensure_feature_catalogue(env)
