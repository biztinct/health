# -*- coding: utf-8 -*-
"""Weekly conformance self-check — control C5 (register item G4).

The CI gate (C1) asks "does the repo still conform?" and the deploy smoke
(C3) asks "did this release come up conformant?". Neither notices a drift
that appears *between* releases: a downstream module registering a serializer,
an ACL change that empties a compartment, a data shape that only occurs in
production. This cron asks the same two questions on a schedule, against the
DEPLOYED code and the LIVE data:

1. does the CapabilityStatement this server would serve still equal the
   baseline committed in the module (control C2, re-run in production)?
2. does one real record of every interaction-bearing resource type still
   serialize into something ``fhir.resources`` accepts?

Nothing leaves the process. The sample records are read as superuser purely
to construct and validate a resource in memory — no HTTP response, no bundle,
no audit row, no consent decision, and deliberately no record rules: a
narrowed sample would hide exactly the drift this exists to find.

On any failure the run logs at ERROR **and** hangs a ``mail.activity`` on a
named owner (``health_fhir_core.conformance_owner_login``, admin fallback),
because a conformance alarm with no assignee is a log line nobody reads —
which is the whole of gap G4.
"""

import json
import logging

from markupsafe import Markup, escape

from odoo import SUPERUSER_ID, _, api, models
from odoo.tools.misc import file_open

from ..capability import build_capability, clear_capability_cache
from ..serializers import REGISTRY
from ..serializers.base import validate_resource

_logger = logging.getLogger(__name__)

#: read through ``file_open`` — one copy of the baseline, shared with
#: tests/test_fhir_conformance.py (control C2).
BASELINE_PATH = 'health_fhir_core/conformance/capability_baseline.json'

OWNER_LOGIN_PARAM = 'health_fhir_core.conformance_owner_login'

#: stable across runs on purpose — the dedupe key for the open activity
#: (ledger §5.89: the dedupe key is whatever you search on).
ALARM_SUMMARY = 'FHIR conformance check failed'


def normalized_capability(statement):
    """The comparable form of a CapabilityStatement: everything except the
    generation timestamp, key-sorted so the comparison is byte-exact.

    Byte-identical to the normalization in
    ``tests/test_fhir_conformance.py`` on purpose — the CI control and the
    production control must not be able to disagree about what "unchanged"
    means."""
    comparable = {k: v for k, v in statement.items() if k != 'date'}
    return json.dumps(comparable, sort_keys=True, indent=2, ensure_ascii=False)


class FhirConformance(models.AbstractModel):
    """Abstract: this model holds no data of its own, it only runs checks.
    The cron record targets it directly (``model.run_weekly_check()``)."""
    _name = 'fhir.conformance'
    _description = 'FHIR Conformance Self-Check'

    # ------------------------------------------------------------------
    # Check 1 — the capability has not drifted from the committed baseline
    # ------------------------------------------------------------------

    @api.model
    def _read_baseline(self):
        """Seam: the corrupt-baseline test patches this, so the check can be
        exercised without writing a bad file into the module."""
        with file_open(BASELINE_PATH) as handle:
            return json.load(handle)

    @api.model
    def _check_capability(self):
        clear_capability_cache()
        try:
            current = normalized_capability(build_capability(self.env))
            baseline = normalized_capability(self._read_baseline())
        except Exception as error:  # noqa: BLE001 — a check that cannot run
            # is itself a finding; it must never take the cron down.
            return ['capability: could not be built or read (%s)' % error]
        finally:
            # The statement is cached at module level and the request workers
            # share this process — never leave a cron-built statement behind.
            clear_capability_cache()
        if current != baseline:
            return ['capability: the live CapabilityStatement no longer '
                    'matches %s — a capability change is only sanctioned by '
                    'regenerating the baseline in the same commit as the '
                    'code that changed it' % BASELINE_PATH]
        return []

    # ------------------------------------------------------------------
    # Check 2 — one live record per type still serializes and validates
    # ------------------------------------------------------------------

    @api.model
    def _check_resources(self):
        """Returns ``(failures, checked)``. A type with no records yet is
        skipped and NOT counted — an empty table is not a conformance
        failure, and pretending it was checked would be the "no silent
        truncation" defect in reverse."""
        failures = []
        checked = 0
        for rtype in sorted(REGISTRY):
            serializer = REGISTRY[rtype]
            try:
                record = self.env[serializer.odoo_model].sudo().search(
                    serializer.base_domain(self.env), limit=1)
            except Exception as error:  # noqa: BLE001
                failures.append('%s: sample read failed (%s)' % (rtype, error))
                continue
            if not record:
                continue
            checked += 1
            try:
                resource = serializer.serialize_batch(record)[0]
                validate_resource(resource)
            except ImportError:
                failures.append(
                    'fhir.resources is not installed — no resource could be '
                    'validated (stopped at %s)' % rtype)
                break
            except Exception as error:  # noqa: BLE001
                failures.append('%s/%s: %s' % (rtype, record.id, error))
        return failures, checked

    # ------------------------------------------------------------------
    # The alarm
    # ------------------------------------------------------------------

    @api.model
    def _owner_user(self):
        """The named conformance owner, or the admin user. Naming the owner
        is an OPS action (§10.11) — until it happens the alarm still lands
        somewhere a human looks, rather than nowhere."""
        Users = self.env['res.users'].sudo()
        login = (self.env['ir.config_parameter'].sudo().get_param(
            OWNER_LOGIN_PARAM) or '').strip()
        if login:
            user = Users.search([('login', '=', login)], limit=1)
            if user:
                return user
            _logger.warning(
                'FHIR conformance owner %r (%s) does not exist — falling '
                'back to the admin user', login, OWNER_LOGIN_PARAM)
        return (self.env.ref('base.user_admin', raise_if_not_found=False)
                or Users.browse(SUPERUSER_ID))

    @api.model
    def _raise_alarm(self, failures):
        """One open activity at a time per owner: a weekly cron that stacks a
        new to-do every run turns a real finding into noise. Returns the
        activity (existing or new), or False when none could be raised."""
        try:
            user = self._owner_user()
            partner = user.sudo().partner_id
            activity_type = self.env.ref(
                'mail.mail_activity_data_todo', raise_if_not_found=False)
            if not partner or not activity_type:
                _logger.warning(
                    'FHIR conformance alarm: no owner partner or activity '
                    'type — the ERROR log line is the only alert')
                return False
            Activity = self.env['mail.activity'].sudo()
            existing = Activity.search([
                ('res_model', '=', 'res.partner'),
                ('res_id', '=', partner.id),
                ('user_id', '=', user.id),
                ('summary', '=', ALARM_SUMMARY),
            ], limit=1)
            note = Markup('<p>%s</p><ul>%s</ul>') % (
                escape(_('The weekly FHIR conformance check found '
                         '%s issue(s):', len(failures))),
                Markup('').join(
                    Markup('<li>%s</li>') % escape(f) for f in failures),
            )
            if existing:
                _logger.info(
                    'FHIR-CONFORMANCE-ACTIVITY id=%s (already open) user=%s',
                    existing.id, user.login)
                return existing
            activity = partner.sudo().activity_schedule(
                activity_type_id=activity_type.id,
                summary=ALARM_SUMMARY,
                note=note,
                user_id=user.id)
            _logger.error('FHIR-CONFORMANCE-ACTIVITY id=%s user=%s',
                          activity.id, user.login)
            return activity
        except Exception:  # noqa: BLE001 — alerting must never break the cron
            _logger.exception('FHIR conformance alarm could not be raised')
            return False

    # ------------------------------------------------------------------
    # Entry point (the cron calls exactly this)
    # ------------------------------------------------------------------

    @api.model
    def run_weekly_check(self):
        """Returns the list of failure strings (empty = conformant)."""
        failures = list(self._check_capability())
        resource_failures, checked = self._check_resources()
        failures += resource_failures
        if failures:
            _logger.error('FHIR-CONFORMANCE-FAIL %s issue(s) over %s type(s): '
                          '%s', len(failures), checked, ' | '.join(failures))
            self._raise_alarm(failures)
        else:
            _logger.info('FHIR-CONFORMANCE-OK %s types', checked)
        return failures
