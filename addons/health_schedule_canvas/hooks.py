# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def post_init_cleanup_templates(env):
    """Retire the template-assignment side channel (§2.4): unlink every leftover
    ``state='template'`` health.staff.assignment. Nothing creates them any more
    (the create dialog now receives the action context natively), so any surviving
    row is an orphan that would keep pre-filling stale bookings. Runs after upgrade
    because this module depends on health_fieldservice.
    """
    # active_test=False: many legacy template rows are ARCHIVED (active=False);
    # a plain search would silently skip them and leave orphans behind.
    Asg = env['health.staff.assignment'].sudo().with_context(active_test=False)
    templates = Asg.search([('state', '=', 'template')])
    count = len(templates)
    if not count:
        _logger.info('health_schedule_canvas: no orphan template assignments to remove.')
        return
    try:
        templates.unlink()
        _logger.info('health_schedule_canvas: removed %s orphan template assignment(s).', count)
    except Exception as exc:  # noqa: BLE001 — never block install on cleanup
        _logger.warning('health_schedule_canvas: could not bulk-remove %s template '
                        'assignment(s) (%s); trying one by one.', count, exc)
        removed = 0
        for t in templates:
            try:
                t.unlink()
                removed += 1
            except Exception as exc2:  # noqa: BLE001
                _logger.warning('  template %s not removed: %s', t.id, exc2)
        _logger.info('health_schedule_canvas: removed %s/%s orphan template '
                     'assignment(s).', removed, count)
