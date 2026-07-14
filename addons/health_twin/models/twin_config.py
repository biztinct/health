# -*- coding: utf-8 -*-
"""Config-parameter helpers for the digital-twin risk engine.

All keys are namespaced ``health_twin.<key>``; the seed defaults live in
``data/twin_config_params.xml`` (noupdate=1). These helpers fall back to the
passed default when the param is unset so the engine still runs on a database
whose params were never seeded. Cloned verbatim from
``health_telemonitoring/models/tm_config.py`` (handover §1).
"""

_PREFIX = 'health_twin.'


def get_param(env, key, default=None):
    val = env['ir.config_parameter'].sudo().get_param(_PREFIX + key)
    return val if val not in (None, False, '') else default


def get_bool(env, key, default):
    val = get_param(env, key, None)
    if val is None:
        return default
    return str(val).strip().lower() in ('1', 'true', 'yes')


def get_int(env, key, default):
    val = get_param(env, key, None)
    try:
        return int(val) if val not in (None, False, '') else default
    except (TypeError, ValueError):
        return default


def get_float(env, key, default):
    val = get_param(env, key, None)
    try:
        return float(val) if val not in (None, False, '') else default
    except (TypeError, ValueError):
        return default
