"""Geocoding + driving-distance helpers (shared by res.partner, health.facility,
health.fieldservice.order).

- photon_geocode(): address string -> (lat, lon) via Photon/Komoot (free, no key).
- driving_distance(): one-way driving distance/time between two points, trying
  Google Distance Matrix (reusing the configured key) -> OSRM -> haversine.

All functions are defensive: they catch every error and return None / a
straight-line fallback so a save is never blocked by a network failure.
"""
import logging
import math

import requests

_logger = logging.getLogger(__name__)

_HEADERS = {
    'User-Agent': 'VAFHS-Healthcare-System/1.0 (Odoo; contact@vafhs.com)',
    'Accept': 'application/json',
}
_VN_BIAS = {'lat': 16.0, 'lon': 106.0}


def photon_geocode(address, vn_bias=True, timeout=8):
    """Geocode a free-text address with Photon. Returns (lat, lon) or None."""
    if not address or len(address) < 5:
        return None
    try:
        params = {'q': address, 'limit': 1}
        if vn_bias:
            params.update(_VN_BIAS)
        resp = requests.get('https://photon.komoot.io/api/', params=params,
                            headers=_HEADERS, timeout=timeout)
        if resp.status_code != 200:
            _logger.warning("Photon geocode HTTP %s for %r", resp.status_code, address)
            return None
        feats = (resp.json() or {}).get('features') or []
        if not feats:
            return None
        lon, lat = feats[0]['geometry']['coordinates'][:2]
        return (float(lat), float(lon))
    except Exception as e:  # noqa: BLE001 - never break the caller
        _logger.warning("Photon geocode failed for %r: %s", address, e)
        return None


def haversine_km(o_lat, o_lon, d_lat, d_lon):
    """Great-circle distance in km (straight-line fallback)."""
    r = 6371.0
    p1, p2 = math.radians(o_lat), math.radians(d_lat)
    dphi = math.radians(d_lat - o_lat)
    dlmb = math.radians(d_lon - o_lon)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2)
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _google_distance(env, o_lat, o_lon, d_lat, d_lon, timeout=10):
    key = env['ir.config_parameter'].sudo().get_param('health_base.google_maps_api_key')
    if not key:
        return None
    try:
        resp = requests.get(
            'https://maps.googleapis.com/maps/api/distancematrix/json',
            params={
                'origins': '%s,%s' % (o_lat, o_lon),
                'destinations': '%s,%s' % (d_lat, d_lon),
                'mode': 'driving', 'units': 'metric', 'key': key,
            }, headers=_HEADERS, timeout=timeout)
        data = resp.json() if resp.status_code == 200 else {}
        if data.get('status') != 'OK':
            _logger.info("Google DistanceMatrix status=%s", data.get('status'))
            return None
        el = data['rows'][0]['elements'][0]
        if el.get('status') != 'OK':
            return None
        return (round(el['distance']['value'] / 1000.0, 2),
                round(el['duration']['value'] / 60.0, 1), 'google')
    except Exception as e:  # noqa: BLE001
        _logger.info("Google DistanceMatrix failed: %s", e)
        return None


def _osrm_distance(o_lat, o_lon, d_lat, d_lon, timeout=6):
    try:
        url = ('https://router.project-osrm.org/route/v1/driving/'
               '%s,%s;%s,%s' % (o_lon, o_lat, d_lon, d_lat))
        resp = requests.get(url, params={'overview': 'false'},
                            headers=_HEADERS, timeout=timeout)
        data = resp.json() if resp.status_code == 200 else {}
        if data.get('code') != 'Ok' or not data.get('routes'):
            return None
        route = data['routes'][0]
        return (round(route['distance'] / 1000.0, 2),
                round(route['duration'] / 60.0, 1), 'osrm')
    except Exception as e:  # noqa: BLE001
        _logger.info("OSRM routing failed: %s", e)
        return None


def driving_distance(env, o_lat, o_lon, d_lat, d_lon):
    """One-way driving distance/time between two coordinate pairs.

    Returns dict {km, minutes, method} where method is
    'google' | 'osrm' | 'approx'. Returns None if any coordinate is missing.
    """
    if not all(isinstance(v, (int, float)) for v in (o_lat, o_lon, d_lat, d_lon)):
        return None
    if not (o_lat and o_lon and d_lat and d_lon):
        return None
    res = _google_distance(env, o_lat, o_lon, d_lat, d_lon) \
        or _osrm_distance(o_lat, o_lon, d_lat, d_lon)
    if res:
        km, minutes, method = res
        return {'km': km, 'minutes': minutes, 'method': method}
    # straight-line fallback (rough driving estimate ~1.3x crow-flies, 30 km/h)
    crow = haversine_km(o_lat, o_lon, d_lat, d_lon)
    km = round(crow * 1.3, 2)
    return {'km': km, 'minutes': round(km / 30.0 * 60.0, 1), 'method': 'approx'}
