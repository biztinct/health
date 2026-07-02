# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Seed the default workspace and the usage-analytics dogfood dashboard."""
    Workspace = env['bi.workspace']
    if not Workspace.search_count([('is_default', '=', True)]):
        Workspace.create({
            'name': 'General Analytics',
            'code': 'general',
            'is_default': True,
            'color': 1,
        })
        _logger.info("biz_bi: created default workspace 'General Analytics'")
    try:
        _seed_usage_analytics(env)
    except Exception:
        _logger.exception("biz_bi: usage analytics seed failed — skipping")


def _seed_usage_analytics(env):
    """BI observing itself: a dataset over the audit log + a dashboard."""
    if env['bi.dataset'].search_count([('name', '=', 'BI Usage')]):
        return
    workspace = env['bi.workspace'].search(
        [('is_default', '=', True)], limit=1)
    source = env['bi.source'].create({
        'name': 'BI Audit Log', 'type': 'odoo_model',
        'model_id': env['ir.model']._get_id('bi.audit.log'),
        'state': 'ready'})
    dataset = env['bi.dataset'].create({
        'name': 'BI Usage', 'workspace_id': workspace.id,
        'description': 'Platform usage from the BI audit trail.'})
    root = env['bi.dataset.node'].create({
        'dataset_id': dataset.id, 'source_id': source.id, 'is_root': True})
    root.action_scan_fields()

    def field(technical_name):
        return dataset.field_ids.filtered(
            lambda f: f.technical_name == technical_name)[:1]

    curation = [
        ('created_at', 'When', {'role': 'date', 'visibility': 'visible'}),
        ('event', 'Event', {'visibility': 'visible'}),
        ('user_id', 'User', {'visibility': 'hidden'}),
    ]
    for technical, label, overrides in curation:
        record = field(technical)
        if record:
            record.write(dict(overrides, name=label))
    dataset.action_publish()

    f_when, f_event = field('created_at'), field('event')
    if not (f_when and f_event):
        return

    def chart(name, chart_type, slots):
        return env['bi.chart'].create({
            'name': name, 'dataset_id': dataset.id, 'chart_type': chart_type,
            'config_json': {'version': 1, 'chart_type': chart_type,
                            'slots': slots, 'filters': [], 'limit': 500}})

    kpi = chart('Activity (30 days)', 'kpi',
                {'values': [{'field_id': f_event.id, 'agg': 'count'}]})
    kpi.config_json = dict(
        kpi.config_json,
        filters=[{'field_id': f_when.id, 'op': 'relative',
                  'value': 'last_30_days'}])
    trend = chart('Daily Activity', 'line',
                  {'x': [{'field_id': f_when.id, 'grain': 'day'}],
                   'values': [{'field_id': f_event.id, 'agg': 'count'}]})
    breakdown = chart('Activity by Event', 'bar_h',
                      {'x': [{'field_id': f_event.id}],
                       'values': [{'field_id': f_event.id, 'agg': 'count'}]})

    dashboard = env['bi.dashboard'].create({
        'name': 'BI Usage Analytics', 'workspace_id': workspace.id})
    Widget = env['bi.dashboard.widget']
    Widget.create({'dashboard_id': dashboard.id, 'chart_id': kpi.id,
                   'grid_x': 0, 'grid_y': 0, 'grid_w': 3, 'grid_h': 2})
    Widget.create({'dashboard_id': dashboard.id, 'chart_id': trend.id,
                   'grid_x': 3, 'grid_y': 0, 'grid_w': 9, 'grid_h': 5})
    Widget.create({'dashboard_id': dashboard.id, 'chart_id': breakdown.id,
                   'grid_x': 0, 'grid_y': 5, 'grid_w': 12, 'grid_h': 5})
    _logger.info("biz_bi: seeded BI Usage Analytics dashboard")
