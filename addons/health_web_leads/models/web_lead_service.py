# -*- coding: utf-8 -*-
"""``web.lead.service`` — the website-submission handler (design §9.1).

All of the business logic lives here rather than in the controller, so the
whole algorithm is exercisable from a ``TransactionCase`` with no HTTP: the
controller is a thin auth → parse → call → envelope shell.

Every payload value is UNTRUSTED. Phones go through ``_safe_phone`` (ledger
§5.15: ``normalize_vn_phone`` RAISES on invalid input), emails through
``_safe_email``, UTM strings through ``_sanitize_utm`` before they may become
``utm.source``/``utm.medium`` records, and nothing in the payload may ever
link a lead to a ``res.partner`` (design §9.2 — an anonymous visitor typing a
patient's number must not merge onto that patient).
"""
import json
import logging
import re
import unicodedata
from datetime import datetime, timedelta, timezone

import psycopg2
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.health_api_gateway.controllers.gateway import ApiError
from odoo.addons.health_base.models.phone_utils import normalize_vn_phone

_logger = logging.getLogger(__name__)

# Leads the pipeline may merge onto: an enquiry is only "the same enquiry"
# while it is still open. `lost_booking` and `spam` are terminal — a new
# approach from that number is a NEW lead a human can merge, never a silent
# revival of a closed one.
OPEN_STATUSES = ('active', 'lead', 'booking')
MERGE_WINDOW_DAYS = 60

RAW_PAYLOAD_CAP = 8192          # design §4.2
_CHAR_CAP = 255                 # click ids, utm raws, form ids
_URL_CAP = 512
_UTM_NAME_CAP = 64              # design §9.3 — governed m2o names

_CONTROL_CHARS_RE = re.compile(r'[\x00-\x1f\x7f]')

# Diacritic-insensitive city matching. NFD decomposition handles the tone and
# vowel marks; `đ/Đ` carries no combining mark and must be mapped explicitly.
_D_STROKE = {ord('đ'): 'd', ord('Đ'): 'd'}

_HN_LOCATION_TOKENS = ('ha noi', 'hanoi', 'hn')
_HCM_LOCATION_TOKENS = ('ho chi minh', 'hcm', 'sai gon', 'saigon', 'tphcm',
                        'tp hcm')

# Logical city keys. They are resolved to live `health.catchment.province`
# rows at runtime — never stored as ids in configuration, because vietuat's
# rows carry codes `01`/`02` while the seed XML says `HN`/`HCM` (design §2.3).
CITY_HN = 'HN'
CITY_HCM = 'HCM'
_CATCHMENT_REFS = {
    CITY_HN: ('health_base.catchment_province_hanoi', ('HN', '01')),
    CITY_HCM: ('health_base.catchment_province_hcm', ('HCM', '02')),
}

PARAM_FORM_CITY_MAP = 'web_leads.form_city_map'
PARAM_URL_CITY_MAP = 'web_leads.url_city_map'


# ---------------------------------------------------------------------------
# Pure helpers (no ORM) — unit-testable, and reused by the touchpoint vals
# ---------------------------------------------------------------------------
def _strip_diacritics(value):
    """'Hà Nội' -> 'ha noi' (casefolded, whitespace-collapsed)."""
    if not value:
        return ''
    value = str(value).translate(_D_STROKE)
    decomposed = unicodedata.normalize('NFD', value)
    stripped = ''.join(c for c in decomposed
                       if not unicodedata.combining(c))
    return ' '.join(stripped.casefold().split())


def _safe_phone(value):
    """Falsy-on-invalid wrapper (ledger §5.15 / rail R1).

    ``normalize_vn_phone`` RAISES ``ValidationError`` on non-empty garbage,
    and inbound website data is routinely garbage — a raised exception here
    would 500 the endpoint and make the relay retry forever.
    """
    if not value:
        return False
    try:
        return normalize_vn_phone(str(value).strip()) or False
    except ValidationError:
        return False
    except Exception:  # noqa: BLE001 — never let identity parsing break capture
        _logger.warning('web_leads: phone normalization failed', exc_info=True)
        return False


def _safe_email(value):
    """Lower/strip; an address with no ``@`` is not an address."""
    if not value:
        return False
    value = str(value).strip().lower()
    if '@' not in value or len(value) > 254:
        return False
    return value


def _clean(value, cap=_CHAR_CAP):
    """Untrusted Char value → stripped, control-char-free, length-capped."""
    if value in (None, False, ''):
        return False
    value = _CONTROL_CHARS_RE.sub('', str(value)).strip()
    if not value:
        return False
    return value[:cap]


def _clean_multiline(value, cap):
    """Like :func:`_clean` but keeps line breaks — the visitor's message is
    the one payload field where paragraphing is content, not noise."""
    if value in (None, False, ''):
        return False
    value = str(value).replace('\r\n', '\n').replace('\r', '\n')
    value = ''.join(c for c in value
                    if c == '\n' or not _CONTROL_CHARS_RE.match(c))
    value = value.strip()
    return value[:cap] if value else False


def _sanitize_utm(value):
    """Design §9.3 — a value only becomes a governed `utm.*` record when it
    is short, printable and not a URL. Anything else stays a raw string on
    the lead and the touchpoint, where it can do no harm."""
    value = _clean(value, _UTM_NAME_CAP)
    if not value or '://' in value:
        return False
    return value


def _names_match(left, right):
    """Diacritic- and case-insensitive equality of two human names.

    Deliberately strict (no fuzzy distance): design §9.2 prefers an occasional
    extra lead a human can merge over silently gluing two people together,
    which is unrecoverable.
    """
    left, right = _strip_diacritics(left), _strip_diacritics(right)
    return bool(left) and left == right


def _parse_submitted_at(value):
    """ISO-8601 (offset-aware or naive) → naive UTC, per rail R7.

    '2026-07-28T09:30:00+07:00' → datetime(2026, 7, 28, 2, 30) — Odoo stores
    naive UTC. Returns ``None`` when the value is absent or unparsable, and
    the caller falls back to now.
    """
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if text.endswith('Z') or text.endswith('z'):
            text = text[:-1] + '+00:00'
        try:
            parsed = datetime.fromisoformat(text)
        except (ValueError, TypeError):
            return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed.replace(microsecond=0)


def _sub(payload, key):
    """A nested payload object, defensively (the sender may send null)."""
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


class WebLeadService(models.AbstractModel):
    _name = 'web.lead.service'
    _description = 'Website Lead Capture Service'

    # ------------------------------------------------------------------
    # Configuration — city maps
    # ------------------------------------------------------------------
    @api.model
    def _json_param(self, key):
        """A JSON `ir.config_parameter`, or {} when unset/broken.

        Reading the parameter needs sudo (`get_param` runs `check_access`)
        and a malformed value must degrade to "no map", never 500 the
        capture path.
        """
        raw = self.env['ir.config_parameter'].sudo().get_param(key)
        if not raw:
            return {}
        try:
            value = json.loads(raw)
        except (ValueError, TypeError):
            _logger.warning('web_leads: %s is not valid JSON — ignored', key)
            return {}
        return value if isinstance(value, dict) else {}

    @api.model
    def _resolve_catchment(self, city_key):
        """Logical 'HN'/'HCM' → a live `health.catchment.province` record.

        xmlid first, then a code search — vietuat's rows carry `01`/`02`
        because the database predates the current (noupdate=1) seed file
        (handover fact #9). Returns an empty recordset when neither resolves,
        which the caller reports as `city_source='unknown'`.
        """
        Province = self.env['health.catchment.province'].sudo()
        entry = _CATCHMENT_REFS.get(city_key)
        if not entry:
            return Province.browse()
        xmlid, codes = entry
        record = self.env.ref(xmlid, raise_if_not_found=False)
        if record:
            return record.sudo()
        return Province.search([('code', 'in', list(codes))], limit=1)

    # ------------------------------------------------------------------
    # City derivation (design §8) — precedence, first hit wins
    # ------------------------------------------------------------------
    @api.model
    def _derive_city(self, payload):
        """Returns ``(city_key or False, city_source)``.

        IP geolocation is deliberately absent: a Hanoi resident booking care
        for a parent in HCMC is a normal case, not an anomaly.
        """
        # 1. What the visitor chose in the Địa điểm field.
        location = _strip_diacritics(payload.get('location'))
        if location:
            if any(token in location for token in _HCM_LOCATION_TOKENS):
                return CITY_HCM, 'form_location'
            # 'hn' is checked as a whole token so 'hn' inside another word
            # cannot claim the lead.
            words = location.split()
            if any(token in location for token in _HN_LOCATION_TOKENS[:2]) \
                    or 'hn' in words:
                return CITY_HN, 'form_location'

        # 2. Which form. Config-mapped, so a form renumbering is an edit.
        form_id = _clean(payload.get('form_id'))
        if form_id:
            mapped = self._json_param(PARAM_FORM_CITY_MAP).get(str(form_id))
            if mapped in _CATCHMENT_REFS:
                return mapped, 'form_id'

        # 3. Which page — submit page first, then the landing page.
        url_map = self._json_param(PARAM_URL_CITY_MAP)
        if url_map:
            for url_key in ('page_url', 'landing_url'):
                url = (payload.get(url_key) or '')
                if not isinstance(url, str) or not url:
                    continue
                url_lower = url.lower()
                for prefix, mapped in url_map.items():
                    if (prefix or '').lower() in url_lower \
                            and mapped in _CATCHMENT_REFS:
                        return mapped, 'page_url'

        # 4. The campaign-name convention ({city}_{service}_{objective}_{yyyymm}).
        campaign = (_sub(payload, 'utm').get('campaign') or '')
        campaign = _strip_diacritics(campaign).replace(' ', '')
        if campaign.startswith('hcm_'):
            return CITY_HCM, 'campaign_prefix'
        if campaign.startswith('hn_'):
            return CITY_HN, 'campaign_prefix'

        return False, 'unknown'

    # ------------------------------------------------------------------
    # UTM records (design §9.3)
    # ------------------------------------------------------------------
    @api.model
    def _utm_ids(self, utm):
        """source/medium are find-or-create; campaign is FIND-ONLY.

        Campaign values are attacker-controllable URL input, so blanket
        auto-create is a record-explosion vector; unmatched strings stay raw
        and surface in the W3 review view for marketing to seed.
        """
        vals = {}
        for field_name, model_name in (('source_id', 'utm.source'),
                                       ('medium_id', 'utm.medium')):
            name = _sanitize_utm(utm.get(field_name.split('_')[0]))
            if not name:
                continue
            Model = self.env[model_name].sudo()
            record = Model.search([('name', '=ilike', name)], limit=1)
            if not record:
                record = Model.create({'name': name})
            vals[field_name] = record.id

        campaign_name = _sanitize_utm(utm.get('campaign'))
        if campaign_name:
            campaign = self.env['utm.campaign'].sudo().search(
                [('name', '=ilike', campaign_name)], limit=1)
            if campaign:
                vals['campaign_id'] = campaign.id
        return vals

    # ------------------------------------------------------------------
    # care.conversation (handover fact #7 / rail R5)
    # ------------------------------------------------------------------
    @api.model
    def _upsert_care_conversation(self, lead, phone, email, occurred_at):
        """Make a MERGED enquiry visible to triage.

        The lead-create hook already ingests every new lead, so only the merge
        path needs this. Defensive on three axes: the model may not be
        installed, the body runs inside its own savepoint (ledger §5.55 — a
        caught IntegrityError still poisons the host transaction without one),
        and any failure is logged, never raised: triage visibility must not be
        able to fail a capture.
        """
        if 'care.conversation' not in self.env:
            return
        try:
            with self.env.cr.savepoint():
                self.env['care.conversation'].sudo()._find_or_create_for(
                    {'lead_id': lead.id,
                     'phone_normalized': phone,
                     'email_normalized': email},
                    {'inbound': True,
                     'event_at': occurred_at,
                     'set_status': 'needs_reply',
                     'unread': 1},
                )
        except Exception:  # noqa: BLE001 — never break capture for triage
            _logger.exception(
                'web_leads: care.conversation upsert failed for lead %s',
                lead.id)

    # ------------------------------------------------------------------
    # Possible-existing-client note (design §9.2 / rail R4)
    # ------------------------------------------------------------------
    @api.model
    def _match_existing_client(self, phone, email):
        """A client whose phone/email matches — for a CHATTER NOTE only.

        Never returns anything the caller may write into `partner_id`: a typed
        number is a claim, not an identity (anti-pattern:
        care_channel_message.py:175-185). sudo because the service user has no
        business reading the patient book — it only needs to know that a human
        should look.
        """
        Partner = self.env['res.partner'].sudo()
        domain = []
        if phone:
            domain.append(('phone', 'ilike', phone[-9:]))
        if email:
            domain = (['|'] + domain + [('email', '=ilike', email)]
                      if domain else [('email', '=ilike', email)])
        if not domain:
            return Partner.browse()
        return Partner.search(domain + [('is_patient', '=', True)], limit=1)

    # ==================================================================
    # THE handler (design §9.1)
    # ==================================================================
    @api.model
    def process_submission(self, payload):
        """One website submission → created | merged | duplicate |
        rejected_spam. Raises :class:`ApiError` for the 4xx cases the
        controller must surface."""
        if not isinstance(payload, dict):
            raise ApiError(_('Request body must be a JSON object'), 422)

        submission_id = _clean(payload.get('submission_id'))
        form_id = _clean(payload.get('form_id'))
        if not submission_id:
            raise ApiError(_('Missing required field(s): submission_id'), 422)
        if not form_id:
            raise ApiError(_('Missing required field(s): form_id'), 422)

        Lead = self.env['crm.lead']
        Touchpoint = self.env['health.lead.touchpoint']

        # -- A. Idempotency: search-first ------------------------------
        existing = Lead.search(
            [('external_submission_id', '=', submission_id)], limit=1)
        if existing:
            return self._result('duplicate', existing, submission_id)
        touch = Touchpoint.search(
            [('touchpoint_type', '=', 'form_submit'),
             ('external_event_id', '=', submission_id)], limit=1)
        if touch:
            return self._result('duplicate', touch.lead_id, submission_id)

        # -- B. Identity (untrusted) -----------------------------------
        raw_phone = payload.get('phone')
        phone = _safe_phone(raw_phone)
        email = _safe_email(payload.get('email'))
        invalid_phone = bool(raw_phone) and not phone
        if not phone and not email:
            raise ApiError(
                _('At least one of phone or email is required'), 422)

        # -- C. Spam gate ----------------------------------------------
        anti_spam = _sub(payload, 'anti_spam')
        if anti_spam.get('honeypot_filled') or anti_spam.get('token_ok') is False:
            # Rail R3: 200, never 4xx. A 4xx makes the relay retry forever and
            # tells a bot which of its submissions were detected. The attempt
            # lives in the gateway audit log; no lead row is created.
            _logger.info('web_leads: submission %s rejected as spam',
                         submission_id)
            return {'status': 'rejected_spam',
                    'submission_id': submission_id}

        spam_hit = bool(phone) and bool(Lead.search_count(
            [('phone', '=', phone), ('contact_status', '=', 'spam')], limit=1))

        # -- D. City — BEFORE create (rail R2 / handover fact #5) ------
        city_key, city_source = self._derive_city(payload)
        catchment = self._resolve_catchment(city_key) if city_key \
            else self.env['health.catchment.province'].browse()
        if not catchment:
            city_source = 'unknown'

        occurred_at = _parse_submitted_at(payload.get('submitted_at')) \
            or fields.Datetime.now()

        # -- E. Dedup — LEAD-TO-LEAD ONLY ------------------------------
        open_domain = [('type', '=', 'opportunity'),
                       ('contact_status', 'in', list(OPEN_STATUSES))]
        candidate = Lead.browse()
        phone_candidate = Lead.browse()
        if phone:
            phone_candidate = Lead.search(
                open_domain + [('phone', '=', phone)],
                order='write_date desc', limit=1)
            candidate = phone_candidate
        if not candidate and email:
            candidate = Lead.search(
                open_domain + [('email_from', '=ilike', email)],
                order='write_date desc', limit=1)

        merge = False
        if candidate:
            fresh = (candidate.contact_status == 'booking'
                     or (candidate.write_date
                         and candidate.write_date >= fields.Datetime.now()
                         - timedelta(days=MERGE_WINDOW_DAYS)))
            identified = _names_match(
                payload.get('name'),
                candidate.contact_name or candidate.name)
            if not identified and email and candidate.email_from:
                identified = email == _safe_email(candidate.email_from)
            merge = bool(fresh and identified)

        # A known open lead on the same number that is NOT this person: a
        # shared family phone. Both leads get a cross-reference, and the new
        # one is flagged — the representative flow is a human decision.
        shared_phone_hit = bool(phone_candidate) and not merge

        if merge:
            return self._merge(candidate, payload, submission_id, phone, email,
                               catchment, city_source, occurred_at)

        try:
            with self.env.cr.savepoint():
                lead = self._create_lead(
                    payload, submission_id, form_id, phone, raw_phone,
                    invalid_phone, email, catchment, city_source, spam_hit,
                    shared_phone_hit)
                Touchpoint.create(self._touchpoint_vals(
                    lead, payload, submission_id, catchment, city_source,
                    occurred_at))
        except psycopg2.IntegrityError:
            # Ledger §5.55: the savepoint (not the try) is what keeps the
            # transaction usable here. Two relay deliveries raced past the
            # search-first check and the unique index arbitrated — re-read the
            # winner and answer as a replay.
            _logger.info(
                'web_leads: submission %s lost the create race — '
                'reporting the existing lead', submission_id)
            winner = Lead.search(
                [('external_submission_id', '=', submission_id)], limit=1)
            return self._result('duplicate', winner, submission_id)

        if shared_phone_hit:
            self._cross_reference(lead, phone_candidate)
        client = self._match_existing_client(phone, email)
        if client:
            lead.message_post(body=Markup('<p>%s</p>') % _(
                'Possible existing client: %(name)s (%(code)s). Verify before '
                'converting — the pipeline never links a lead to a client '
                'from a typed phone or email.',
                name=client.name or '',
                code=client.patient_code or _('no code')))
            if not lead.web_needs_review:
                lead.web_needs_review = True

        return self._result('created', lead, submission_id)

    # ------------------------------------------------------------------
    # Branches
    # ------------------------------------------------------------------
    def _merge(self, lead, payload, submission_id, phone, email, catchment,
               city_source, occurred_at):
        """Append this touch to an existing open lead (design §9.1 step 6a)."""
        with self.env.cr.savepoint():
            self.env['health.lead.touchpoint'].create(self._touchpoint_vals(
                lead, payload, submission_id, catchment, city_source,
                occurred_at))
            if catchment and lead.catchment_province_id \
                    and catchment != lead.catchment_province_id:
                # Design §8: the stored city is NEVER auto-changed. Flag it.
                lead.write({'city_conflict': True, 'web_needs_review': True})
            lead.message_post(body=Markup('<p>%s</p>') % _(
                'Repeat web enquiry received (form %(form)s, submission '
                '%(submission)s). Appended as a touchpoint — no second lead '
                'was created.',
                form=_clean(payload.get('form_id')) or '-',
                submission=submission_id))
        self._upsert_care_conversation(lead, phone, email, occurred_at)
        return self._result('merged', lead, submission_id)

    def _create_lead(self, payload, submission_id, form_id, phone, raw_phone,
                     invalid_phone, email, catchment, city_source, spam_hit,
                     shared_phone_hit):
        utm = _sub(payload, 'utm')
        clicks = _sub(payload, 'click_ids')
        consent = _sub(payload, 'consent')

        display_name = _clean(payload.get('name'), 120)
        vals = {
            # `type='opportunity'` is what makes health_crm generate the
            # city-prefixed unique_contact_code — which reads
            # catchment_province_id straight out of these vals (fact #5).
            'type': 'opportunity',
            'name': _('Web: %s', display_name or phone or email),
            'contact_name': display_name or False,
            'phone': phone or False,      # rail R1 — never the raw garbage
            'email_from': email or False,
            'description': self._description_html(payload, raw_phone,
                                                  invalid_phone),
            'catchment_province_id': catchment.id if catchment else False,

            # Reused healthcare fields — this is a website form, said once.
            'mode_of_contact': 'website',
            'contact_source': 'website_form',
            'healthcare_lead_source': 'website_form',
            'vietnamese_channel': 'website',
            'contact_status': 'spam' if spam_hit else 'active',
            'is_spam_caller': spam_hit,

            # Attribution — first touch, frozen at creation.
            'external_submission_id': submission_id,
            'web_form_id': form_id,
            'city_source': city_source,
            'city_conflict': False,
            'web_needs_review': bool(invalid_phone) or not catchment
                                or shared_phone_hit,
            'utm_content': _clean(utm.get('content')),
            'utm_term': _clean(utm.get('term')),
            'gclid': _clean(clicks.get('gclid')),
            'fbclid': _clean(clicks.get('fbclid')),
            'fbc': _clean(clicks.get('fbc')),
            'fbp': _clean(clicks.get('fbp')),
            'ga_client_id': _clean(payload.get('ga_client_id')),
            'web_landing_url': _clean(payload.get('landing_url'), _URL_CAP),
            'web_submit_page_url': _clean(payload.get('page_url'), _URL_CAP),
            'web_referrer_url': _clean(payload.get('referrer_url'), _URL_CAP),
            'web_consent_marketing': bool(consent.get('marketing')),
            'web_consent_text_version': _clean(consent.get('text_version')),
        }
        vals.update(self._utm_ids(utm))
        return self.env['crm.lead'].create(vals)

    def _cross_reference(self, new_lead, other_lead):
        """Reciprocal notes on a shared phone number (design §9.2)."""
        new_lead.message_post(body=Markup('<p>%s</p>') % _(
            'Same phone number as lead %(ref)s (%(name)s), under a different '
            'name — kept as a separate lead. Flagged for review.',
            ref=other_lead.unique_contact_code or other_lead.id,
            name=other_lead.contact_name or other_lead.name or ''))
        other_lead.message_post(body=Markup('<p>%s</p>') % _(
            'A new website enquiry (%(ref)s — %(name)s) arrived on this phone '
            'number under a different name.',
            ref=new_lead.unique_contact_code or new_lead.id,
            name=new_lead.contact_name or new_lead.name or ''))

    # ------------------------------------------------------------------
    # Value builders
    # ------------------------------------------------------------------
    def _description_html(self, payload, raw_phone, invalid_phone):
        """The visitor's message, plus the raw phone when we could not use it.

        Ledger §5.20: `description` is an Html field, so the fragment is built
        as ``Markup(...) % value`` — a plain ``str`` right-hand side would be
        escaped and the markup would render as literal text.
        """
        message = _clean_multiline(payload.get('message'), 4000) or ''
        html = Markup('')
        for paragraph in [p for p in message.split('\n') if p.strip()]:
            html += Markup('<p>%s</p>') % paragraph
        if invalid_phone:
            html += Markup('<p>%s</p>') % _(
                'Phone (unverified, not a valid Vietnamese number): %s',
                _clean(raw_phone, 64) or '')
        return html or False

    def _touchpoint_vals(self, lead, payload, submission_id, catchment,
                         city_source, occurred_at):
        utm = _sub(payload, 'utm')
        clicks = _sub(payload, 'click_ids')
        return {
            'lead_id': lead.id,
            'occurred_at': occurred_at,          # rail R7 — the visitor's time
            'received_at': fields.Datetime.now(),
            'touchpoint_type': 'form_submit',
            'source_system': 'wordpress',
            'catchment_province_id': catchment.id if catchment else False,
            'city_source': city_source,
            'utm_source': _clean(utm.get('source')),
            'utm_medium': _clean(utm.get('medium')),
            'utm_campaign': _clean(utm.get('campaign')),
            'utm_content': _clean(utm.get('content')),
            'utm_term': _clean(utm.get('term')),
            'gclid': _clean(clicks.get('gclid')),
            'fbclid': _clean(clicks.get('fbclid')),
            'page_url': _clean(payload.get('page_url'), _URL_CAP),
            'referrer_url': _clean(payload.get('referrer_url'), _URL_CAP),
            'external_event_id': submission_id,
            'raw_payload': self._raw_payload(payload),
        }

    @staticmethod
    def _raw_payload(payload):
        """Rail R8 — traceability, capped at 8 KB, never logged."""
        try:
            return json.dumps(payload, ensure_ascii=False,
                              default=str)[:RAW_PAYLOAD_CAP]
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _result(status, lead, submission_id):
        """The `data` half of the envelope. `lead_ref` is the human contact
        code, never a database id (design §5.1)."""
        return {
            'status': status,
            'lead_ref': (lead.unique_contact_code or False) if lead else False,
            'submission_id': submission_id,
        }
