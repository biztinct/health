# -*- coding: utf-8 -*-
"""Pure Google Ads attribution helpers — no ORM, unit-testable.

Every input is UNTRUSTED (it came from a URL). Values are bounded strings;
provider ids are digits kept as STRINGS (they exceed 2**53 — never int()).
"""
import re

GOOGLE_SOURCES = ('google', 'google ads', 'googleads', 'adwords')
PAID_MEDIUMS = ('cpc', 'ppc', 'paidsearch', 'paid_search', 'paid-search', 'paid')
_DIGITS_RE = re.compile(r'^\d{1,32}$')
_ID_CAP = 32


def norm_customer_id(value):
    """'123-456-7890' -> '1234567890'; anything not exactly 10 digits -> False."""
    if value in (None, False, ''):
        return False
    digits = re.sub(r'\D', '', str(value))
    return digits if len(digits) == 10 else False


def norm_provider_id(value):
    """A campaign / ad-group / creative id: 1-32 digits, as a STRING, else False."""
    if value in (None, False, ''):
        return False
    text = str(value).strip()
    return text if _DIGITS_RE.match(text) else False


def _lower(value):
    return ' '.join(str(value or '').strip().lower().split())


def classify(utm, clicks):
    """Return (is_google_ads, match_hint) for one submission.

    is_google_ads: a Google click id is present, OR the declared source is a
    Google alias AND the medium is a paid alias.
    match_hint: 'click_id' | 'utm' | 'conflict' | ''.
      'conflict' = a Google click id is present but the declared source names
      something else — the touch is still Google Ads (the click id is the
      stronger evidence) and the lead is flagged for review; the declared UTM
      strings are NEVER rewritten.
    """
    utm = utm if isinstance(utm, dict) else {}
    clicks = clicks if isinstance(clicks, dict) else {}
    has_click = any(str(clicks.get(k) or '').strip()
                    for k in ('gclid', 'wbraid', 'gbraid'))
    source = _lower(utm.get('source'))
    medium = _lower(utm.get('medium'))
    utm_says_google = source in GOOGLE_SOURCES and medium in PAID_MEDIUMS
    if has_click:
        if source and source not in GOOGLE_SOURCES:
            return True, 'conflict'
        return True, 'click_id'
    if utm_says_google:
        return True, 'utm'
    return False, ''


def extract_ids(payload):
    """The optional `google_ads` block plus the h19_gads_* query keys some relays
    flatten into the top level. Bounded, digit-only, strings."""
    block = payload.get('google_ads') if isinstance(payload, dict) else None
    block = block if isinstance(block, dict) else {}
    def pick(key):
        return (block.get(key)
                if block.get(key) not in (None, '', False)
                else payload.get('h19_gads_%s' % key))
    return {
        'customer_id': norm_customer_id(pick('customer_id')),
        'campaign_id': norm_provider_id(pick('campaign_id')),
        'adgroup_id': norm_provider_id(pick('adgroup_id')),
        'creative_id': norm_provider_id(pick('creative_id')),
        'asset_group_id': norm_provider_id(pick('asset_group_id')),
    }
