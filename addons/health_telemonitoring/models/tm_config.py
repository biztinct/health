# -*- coding: utf-8 -*-
"""Config-parameter helpers for the telemonitoring engine.

All keys are namespaced ``health_telemonitoring.<key>``; the seed defaults
live in ``data/telemonitoring_config_params.xml`` (noupdate=1). These
helpers fall back to the passed default when the param is unset so the
engine still runs on a database whose params were never seeded.
"""

_PREFIX = 'health_telemonitoring.'


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
