# -*- coding: utf-8 -*-
"""Post-migration: split the legacy free-text `city` ("<District>, <City>") into
the structured District (district_id) + City (catchment_province_id) on every
res.partner and crm.lead, then re-derive the denormalized `city` string.

Best-effort + idempotent:
  - The City part is matched (normalized, with common aliases) to a catchment
    province. Only Vietnamese values match; foreign Odoo demo cities (Chicago,
    London, ...) are left untouched and counted as `skipped`.
  - When a record already has catchment_province_id, that is kept; we still try
    to back-fill a District from the old string.
  - District is matched within the resolved province's district master.
  - `city` is only rewritten when we resolved at least a province (so unmatched
    rows keep their original value).
"""
import logging
import re
import unicodedata

_logger = logging.getLogger(__name__)

# city-string aliases -> canonical catchment province name
_ALIASES = {
    'hcm': 'Ho Chi Minh City', 'hcmc': 'Ho Chi Minh City', 'tphcm': 'Ho Chi Minh City',
    'hochiminh': 'Ho Chi Minh City', 'hochiminhcity': 'Ho Chi Minh City',
    'thanhphohochiminh': 'Ho Chi Minh City', 'saigon': 'Ho Chi Minh City',
    'hanoi': 'Hanoi', 'hn': 'Hanoi',
    'danang': 'Da Nang', 'binhduong': 'Binh Duong', 'dongnai': 'Dong Nai',
}


def _norm(s):
    """Fold accents to base letters and keep [a-z0-9] only.

    Digits MUST be kept — otherwise "District 1" and "District 8" both collapse
    to "district" and collide. Accents are folded (Bình Thạnh -> binhthanh) via
    NFKD so Vietnamese names match their unaccented input forms."""
    s = unicodedata.normalize('NFKD', (s or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]', '', s.lower())


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    Province = env['health.catchment.province'].with_context(active_test=False)
    District = env['health.vietnamese.district'].with_context(active_test=False)

    provinces = Province.search([])
    if not provinces:
        _logger.warning("city/district split: no catchment provinces; skipping.")
        return

    prov_by_norm = {}
    for p in provinces:
        prov_by_norm[_norm(p.name)] = p
    for alias, canonical in _ALIASES.items():
        canon = prov_by_norm.get(_norm(canonical))
        if canon:
            prov_by_norm[alias] = canon

    # district master indexed by (province_name, normalized district name)
    districts = District.search([])
    dist_index = {}
    for d in districts:
        dist_index.setdefault(d.province_name, {})[_norm(d.name)] = d

    def resolve_province(city_token):
        n = _norm(city_token)
        if not n:
            return None
        if n in prov_by_norm:
            return prov_by_norm[n]
        # substring fallback (e.g. "hochiminhcity700000")
        for key, prov in prov_by_norm.items():
            if len(key) >= 5 and key in n:
                return prov
        return None

    def resolve_district(province, district_token):
        if not province or not district_token:
            return None
        by_name = dist_index.get(province.name, {})
        n = _norm(district_token)
        if not n:
            return None
        if n in by_name:
            return by_name[n]
        for key, dist in by_name.items():
            if len(key) >= 4 and (key in n or n in key):
                return dist
        return None

    totals = {'res.partner': None, 'crm.lead': None}
    for model in ('res.partner', 'crm.lead'):
        Model = env[model].with_context(active_test=False)
        recs = Model.search(['|', ('city', '!=', False), ('catchment_province_id', '!=', False)])
        done = {'matched_prov': 0, 'matched_dist': 0, 'rederived': 0, 'skipped': 0}
        for rec in recs:
            raw = (rec.city or '').strip()
            province = rec.catchment_province_id or None
            district_token = ''
            city_token = raw
            if ',' in raw:
                left, right = raw.rsplit(',', 1)
                district_token, city_token = left.strip(), right.strip()

            if not province:
                province = resolve_province(city_token) or (resolve_province(raw) if raw else None)
            if not province:
                done['skipped'] += 1
                continue

            vals = {}
            if not rec.catchment_province_id:
                vals['catchment_province_id'] = province.id
                done['matched_prov'] += 1

            if not rec.district_id:
                # try the explicit "District, City" token first, else the whole string
                dist = resolve_district(province, district_token) \
                    or resolve_district(province, raw)
                if dist:
                    vals['district_id'] = dist.id
                    done['matched_dist'] += 1

            # Re-derive the denormalized city string from the resolved parts.
            dname = (env['health.vietnamese.district'].browse(vals['district_id']).name
                     if vals.get('district_id') else (rec.district_id.name if rec.district_id else False))
            composed = env['res.partner']._vn_compose_city(dname, province.name)
            if composed and composed != raw:
                vals['city'] = composed
                done['rederived'] += 1

            if vals:
                rec.write(vals)
        totals[model] = done
        _logger.info("city/district split [%s]: %s", model, done)

    _logger.info("city/district split complete: %s", totals)
