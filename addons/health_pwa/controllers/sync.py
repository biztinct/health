# -*- coding: utf-8 -*-

import json
import logging
from datetime import datetime, timedelta

from odoo import http, fields, _
from odoo.http import request

_logger = logging.getLogger(__name__)

# Offline action replay (pwa-offline-actions phase) --------------------------
# The two visit actions that may replay from the offline queue. COMPLETE is
# deliberately absent (money tail + clinical_notes/invoice gates, phase fact 4).
KNOWN_ACTION_TYPES = ('start_service', 'save_clinical_notes')
# Whitelist for the queued clinical-note payload — EXACTLY the online endpoint's
# field set (api.py:1004-1016, duplicated per the A4 convention; api.py stays
# READ-ONLY). Unknown keys are ignored silently.
NOTE_TEXT_FIELDS = ('clinical_notes', 'diagnosis', 'treatment_performed',
                    'medications_prescribed', 'vital_signs',
                    'patient_condition_before', 'patient_condition_after')
NOTE_COUNT_FIELDS = ('injection_count', 'medication_count', 'wound_count',
                     'iv_fluid_count')

# Delta-feed cap literals (pwa-cache-hygiene phase). Extracted into module
# constants so the honest-cap tests can monkeypatch FSO_UPSERT_CAP to force the
# capped path deterministically (methods reference these as module globals, so
# a monkeypatch.setattr on the module takes effect at call time). Values are
# unchanged from the pre-phase inline literals — this phase does NOT change the
# cap magnitudes.
FSO_CANDIDATE_LIMIT = 2000
FSO_UPSERT_CAP = 500


def _selection_labels(record, field_name):
    return dict(record._fields[field_name]._description_selection(record.env))


class HealthPWASyncController(http.Controller):
    """Data synchronization endpoints for offline PWA functionality.

    Scope model (pwa-sync-delta phase): the pull is SCOPED to the caller's
    own visits — orders by explicit grants G1 assignment / G2 team / G3
    catchment (managers) / G4 primary, patients only for orders in a 90-day
    horizon of those grants. All PAYLOAD reads run sudo AFTER the explicit
    grant check (conventions §2.3 pattern / §5.24) so a minimal nurse with no
    catchment and no sale/account ACL still gets their own visits offline,
    while no internal user can cache the full patient table anymore.
    """

    def _check_sync_access(self):
        """Check if user has sync access to health modules"""
        if not request.env.user or request.env.user.id == request.env.ref('base.public_user').id:
            return False

        try:
            request.env['res.partner'].check_access('read')
            return True
        except Exception:
            return False

    def _prepare_sync_response(self, data=None, error=None, status_code=200):
        """Prepare standardized sync response"""
        response_data = {
            'success': error is None,
            'timestamp': fields.Datetime.now().isoformat(),
            'server_time': fields.Datetime.now().isoformat(),
        }

        if error:
            response_data['error'] = error
        else:
            response_data.update(data or {})

        return request.make_response(
            json.dumps(response_data, default=str, ensure_ascii=False),
            headers=[
                ('Content-Type', 'application/json; charset=utf-8'),
                ('Cache-Control', 'no-cache, no-store, must-revalidate'),
                ('Access-Control-Allow-Origin', '*'),
                ('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS'),
                ('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With'),
            ],
            status=status_code
        )

    # ------------------------------------------------------------------
    # Scope helpers (server, computed sudo — the heart of the phase)
    # ------------------------------------------------------------------
    def _employee_assigned_to(self, order):
        """Return the caller's employee IFF assigned to THIS order (any state
        but cancelled), else None. Cloned verbatim from
        health_workflow_auto/controllers/onetap_api.py:_employee_assigned_to
        (fact 6): resolve the employee via sudo user_id search (§5.24 —
        user.employee_id is company-context dependent and reads trip the
        public-profile guard), then sudo the assignment read."""
        employee = request.env['hr.employee'].sudo().search(
            [('user_id', '=', request.env.user.id)], limit=1)
        if not employee:
            return None
        assigned = request.env['health.staff.assignment'].sudo().search_count([
            ('fso_id', '=', order.id),
            ('staff_id', '=', employee.id),
            ('state', '!=', 'cancelled'),
        ])
        return employee if assigned else None

    def _sync_scope(self):
        """Compute the caller's sync scope ONCE per request.

        Returns a dict carrying the grant primitives, a `grant_domain`
        (an OR of G1-G4, `[]` for owner = everything) and `patient_scope_ids`
        (patients of in-grant orders within a 90-day horizon). Every read here
        is sudo AFTER the group/assignment checks."""
        env = request.env
        user = env.user
        Order = env['health.fieldservice.order'].sudo()
        Assignment = env['health.staff.assignment'].sudo()

        # G-primitives ------------------------------------------------------
        employee = env['hr.employee'].sudo().search(
            [('user_id', '=', user.id)], limit=1)
        # member_ids are USERS (fact 2)
        teams = env['health.fieldservice.team'].sudo().search(
            [('member_ids', 'in', [user.id])])
        is_owner = user.has_group('health_base.group_healthcare_owner')
        is_manager = user.has_group('health_base.group_healthcare_operations_manager')
        user_province_id = user.catchment_province_id.id

        # grant_domain = OR of the grants the caller qualifies for. Mirrors the
        # health_fieldservice record rules (fact 3) so no manager/owner loses
        # audience. Owner => [] (everything).
        if is_owner:
            grant_domain = []
        else:
            subs = []
            # G1 assignment
            if employee:
                assigned_ids = Assignment.search([
                    ('staff_id', '=', employee.id),
                    ('state', '!=', 'cancelled'),
                ]).mapped('fso_id').ids
                if assigned_ids:
                    subs.append([('id', 'in', assigned_ids)])
            # G2 team
            if teams:
                subs.append([('team_id', 'in', teams.ids)])
            # G3 catchment (managers only)
            if is_manager and user_province_id:
                subs.append([('catchment_province_id', '=', user_province_id)])
            # G4 primary doctor/nurse == caller
            subs.append([('primary_doctor_id.user_id', '=', user.id)])
            subs.append([('primary_nurse_id.user_id', '=', user.id)])
            # OR-fold the sub-domains (never empty — the two G4 terms are
            # always present, so a minimal nurse gets a valid match-nothing-
            # by-default domain rather than a [0] sentinel, §5.7).
            grant_domain = subs[0]
            for sub in subs[1:]:
                grant_domain = ['|'] + grant_domain + sub

        # patient scope: patients of in-grant orders within a 90-day horizon.
        # Appending AND-terms to a prefix-operator domain list is implicit AND
        # in Odoo: `['|', a, b] + [c]` == `(a OR b) AND c`.
        horizon = fields.Datetime.now() - timedelta(days=90)
        horizon_orders = Order.search(
            grant_domain + [('scheduled_datetime', '>=', horizon)])
        patient_scope_ids = set(horizon_orders.mapped('patient_id').ids)

        return {
            'employee': employee,
            'teams': teams,
            'is_owner': is_owner,
            'is_manager': is_manager,
            'user_province_id': user_province_id,
            'user_id': user.id,
            'grant_domain': grant_domain,
            'patient_scope_ids': patient_scope_ids,
        }

    def _parse_since(self, raw, force_full):
        """Parse the client's JS ISO `since` timestamp. Returns
        (datetime, used_fallback). Falls back to a 30-day window on
        absence / garbage / force_full — never raises, never 500s."""
        fallback = fields.Datetime.now() - timedelta(days=30)
        if force_full or not raw:
            return fallback, True
        try:
            value = raw
            # Handle the JS `Z` suffix, `T` separator, millis and tz offset.
            if value.endswith('Z'):
                value = value[:-1] + '+00:00'
            value = value.replace('T', ' ').split('+')[0].split('.')[0].strip()
            parsed = fields.Datetime.from_string(value)
            if not parsed:
                return fallback, True
            return parsed, False
        except Exception:
            return fallback, True

    # ------------------------------------------------------------------
    # Debug (base.group_system gated)
    # ------------------------------------------------------------------
    @http.route('/health_pwa/sync/debug', type='http', auth='user', methods=['GET'], csrf=False)
    def sync_debug_info(self, **kwargs):
        """Debug endpoint to check what data is available for sync"""
        if not self._check_sync_access():
            return self._prepare_sync_response(error=_('Access denied'), status_code=403)
        # System administrators only — this exposes global row counts.
        if not request.env.user.has_group('base.group_system'):
            return self._prepare_sync_response(error=_('Access denied'), status_code=403)

        try:
            # Check total counts
            total_patients = request.env['res.partner'].search_count([('is_patient', '=', True)])
            total_orders = request.env['health.fieldservice.order'].search_count([])
            total_teams = request.env['health.fieldservice.team'].search_count([])

            # Check user's teams
            user_teams = request.env['health.fieldservice.team'].search([
                ('member_ids', 'in', [request.env.user.id])
            ])

            # Get recent patients (last 30 days)
            since_30_days = fields.Datetime.now() - timedelta(days=30)
            recent_patients = request.env['res.partner'].search_count([
                ('is_patient', '=', True),
                '|',
                ('write_date', '>=', since_30_days),
                ('create_date', '>=', since_30_days),
            ])

            # Get recent orders (last 30 days)
            recent_orders = request.env['health.fieldservice.order'].search_count([
                '|',
                ('write_date', '>=', since_30_days),
                ('create_date', '>=', since_30_days),
            ])

            debug_info = {
                'current_user': request.env.user.name,
                'user_id': request.env.user.id,
                'total_patients': total_patients,
                'total_orders': total_orders,
                'total_teams': total_teams,
                'user_teams': [{'id': t.id, 'name': t.name} for t in user_teams],
                'recent_patients_30d': recent_patients,
                'recent_orders_30d': recent_orders,
                'server_time': fields.Datetime.now().isoformat(),
                'since_30d_filter': since_30_days.isoformat(),
            }

            return self._prepare_sync_response(data=debug_info)

        except Exception as e:
            return self._prepare_sync_response(error=str(e), status_code=500)

    # ------------------------------------------------------------------
    # Incremental delta pull
    # ------------------------------------------------------------------
    @http.route('/health_pwa/sync/changes', type='http', auth='user', methods=['GET'], csrf=False)
    def sync_get_changes(self, **kwargs):
        """Get changes since last sync timestamp for offline synchronization.

        SCOPED delta: orders by grants G1-G4 (sudo reads), patients only for
        the caller's 90-day order horizon, removals for changed-but-out-of-
        scope / archived / hard-deleted orders (client honours `is_deleted`).
        """
        if not self._check_sync_access():
            return self._prepare_sync_response(error=_('Access denied'), status_code=403)

        try:
            # 1. Capture the server-authoritative watermark BEFORE any query so
            #    the client's next `since` can never skip a concurrent write.
            watermark = fields.Datetime.now()

            force_full = kwargs.get('force_full')
            # 2. Parse `since` (hardened; 30-day fallback on garbage/absence).
            last_sync, used_fallback = self._parse_since(kwargs.get('since'), force_full)

            _logger.info(
                "Sync: since=%s force_full=%s fallback=%s",
                last_sync, force_full, used_fallback)

            scope = self._sync_scope()

            fso_changes, in_scope_orders = self._get_fso_changes(
                last_sync, scope, used_fallback)
            changes = {
                'patients': self._get_patient_changes(last_sync, scope, in_scope_orders),
                'field_service_orders': fso_changes,
                'teams': self._get_team_changes(last_sync, scope),
                'service_types': self._get_service_type_changes(last_sync),
                'facilities': self._get_facility_changes(last_sync),
            }

            total_changes = sum(len(changes[key]['records']) for key in changes)

            _logger.info(
                "Sync Summary: %s total changes - Patients: %s, Orders: %s",
                total_changes,
                len(changes['patients']['records']),
                len(changes['field_service_orders']['records']))

            sync_data = {
                'changes': changes,
                'total_changes': total_changes,
                'last_sync': last_sync.isoformat(),
                'current_time': fields.Datetime.now().isoformat(),
                # Server-authoritative watermark: the client persists THIS as
                # its next `since` rather than its own (drifting) device clock.
                'watermark': watermark.isoformat(),
                'debug_info': {
                    'since_datetime': last_sync.isoformat(),
                    'force_full': bool(force_full),
                    'patients_found': len(changes['patients']['records']),
                    'orders_found': len(changes['field_service_orders']['records']),
                    'teams_found': len(changes['teams']['records']),
                }
            }

            return self._prepare_sync_response(data=sync_data)

        except Exception as e:
            return self._prepare_sync_response(error=str(e), status_code=500)

    # ------------------------------------------------------------------
    # Per-model change builders (all reads sudo, scope enforced by caller)
    # ------------------------------------------------------------------
    def _patient_record(self, patient):
        """Per-record dict — shape unchanged from the pre-scope endpoint."""
        return {
            'id': patient.id,
            'name': patient.name,
            'patient_code': patient.patient_code,
            'first_name': patient.first_name,
            'last_name': patient.last_name,
            'phone': patient.phone,
            'mobile': patient.mobile,
            'zalo_user_id': patient.zalo_user_id if hasattr(patient, 'zalo_user_id') else None,
            'email': patient.email,
            'birth_date': patient.birth_date,
            'age': patient.age,
            'gender': patient.gender,
            'blood_group': patient.blood_group,
            'patient_status': patient.patient_status,
            'allergies': patient.allergies,
            'medical_history': patient.medical_history,
            'street': patient.street,
            'city': patient.city,
            'country': patient.country_id.name if patient.country_id else None,
            'emergency_contact_name': patient.emergency_contact_name,
            'emergency_contact_phone': patient.emergency_contact_phone,
            'last_visit_date': patient.last_visit_date,
            'next_visit_date': patient.next_visit_date,
            'created_date': patient.create_date,
            'updated_date': patient.write_date,
            'is_deleted': False,
        }

    def _get_patient_changes(self, since_datetime, scope, in_scope_orders):
        """Scoped patient delta. Changed patients FILTERED to the caller's
        patient scope, UNION the patients of the in-scope changed orders (a
        newly assigned order must bring its patient even if the partner row is
        untouched). All reads sudo — the minimal nurse reads PHI via sudo."""
        Partner = request.env['res.partner'].sudo()
        patient_scope_ids = scope['patient_scope_ids']

        # Scope INSIDE the domain: a global changed-partner search with a 500
        # cap could crowd an in-scope patient out of the window with unrelated
        # partner churn before the scope filter even ran.
        if patient_scope_ids:
            domain = [
                ('id', 'in', list(patient_scope_ids)),
                ('is_patient', '=', True),
                '|',
                ('write_date', '>=', since_datetime),
                ('create_date', '>=', since_datetime),
            ]
            changed_in_scope = Partner.search(domain, limit=500)
        else:
            changed_in_scope = Partner.browse()

        union_ids = set(changed_in_scope.ids) | set(in_scope_orders.mapped('patient_id').ids)
        patients = Partner.browse(sorted(union_ids))

        patient_records = [self._patient_record(p) for p in patients]

        _logger.info("Sync: %s scoped patients", len(patient_records))
        return {
            'model': 'res.partner',
            'count': len(patient_records),
            'records': patient_records,
        }

    def _fso_record(self, order):
        """Per-record dict — shape unchanged from the pre-scope endpoint."""
        return {
            'id': order.id,
            'name': order.name,
            'patient_id': order.patient_id.id if order.patient_id else None,
            'patient_name': order.patient_id.name if order.patient_id else None,
            'patient_code': order.patient_id.patient_code if order.patient_id else None,
            'stage_id': order.stage_id.id if order.stage_id else None,
            'stage_name': order.stage_id.name if order.stage_id else None,
            'priority': order.priority,
            'scheduled_datetime': order.scheduled_datetime,
            'estimated_end_datetime': order.estimated_end_datetime,
            'estimated_duration': order.estimated_duration,
            'duration_minutes': order.scheduled_duration,
            'service_type': order.service_type,
            'service_type_name': _selection_labels(
                order, 'service_type'
            ).get(order.service_type, ''),
            'team_id': order.team_id.id if order.team_id else None,
            'team_name': order.team_id.name if order.team_id else None,
            'booking_user_id': order.booking_user_id.id if order.booking_user_id else None,
            'booking_user_name': order.booking_user_id.name if order.booking_user_id else None,
            'service_address': order.service_address,
            'patient_phone': order.patient_phone,
            'patient_zalo': order.patient_id.zalo_user_id if order.patient_id and hasattr(order.patient_id, 'zalo_user_id') else None,
            'symptoms': order.symptoms,
            'patient_notes': order.patient_notes,
            'gps_coordinates': order.gps_coordinates,
            'state': order.state,
            'actual_start_datetime': order.actual_start_datetime if hasattr(order, 'actual_start_datetime') else None,
            'actual_end_datetime': order.actual_end_datetime if hasattr(order, 'actual_end_datetime') else None,
            'actual_duration': order.actual_duration if hasattr(order, 'actual_duration') else None,
            'address': order.service_address,  # Add duplicate for compatibility
            'created_date': order.create_date,
            'updated_date': order.write_date,
            'is_deleted': False,
        }

    def _get_fso_changes(self, since_datetime, scope, used_fallback):
        """Scoped FSO delta + removals.

        Returns (changes_dict, in_scope_orders_recordset). The recordset is
        used by the patient delta so a newly assigned order pulls its patient.

        Partition of the changed candidate set:
          * active AND not-deleted AND in-scope -> upsert record (cap 500)
          * NOT (active AND not-deleted) OR NOT in-scope -> removal
            {'id', 'is_deleted': True} (ids only — never leak fields of
            out-of-scope orders)
        Plus hard-delete tombstones (§2.3). §5.27: the candidate query runs
        active_test=False (and deleted_test=False for the lifecycle soft
        delete) or archived/deleted orders vanish instead of emitting a
        removal.
        """
        Order = request.env['health.fieldservice.order'].sudo()

        candidate_domain = [
            '|',
            ('write_date', '>=', since_datetime),
            ('create_date', '>=', since_datetime),
        ]
        candidates = Order.with_context(
            active_test=False, deleted_test=False).search(
            candidate_domain, order='write_date desc', limit=FSO_CANDIDATE_LIMIT)

        # Scope changes ride the ASSIGNMENT row, not the order: cancelling an
        # assignment (state write) bumps no stored compute on the order, so the
        # order row's write_date stays put. Orders whose assignments changed in
        # the window therefore join the candidate set for a scope re-check —
        # both directions: a newly assigned old order upserts into the nurse's
        # delta, a de-assigned order emits its removal.
        assign_fso_ids = set(request.env['health.staff.assignment'].sudo().search(
            [('write_date', '>=', since_datetime)],
            order='write_date desc', limit=4000).mapped('fso_id').ids)
        extra_ids = assign_fso_ids - set(candidates.ids)
        if extra_ids:
            candidates |= Order.with_context(
                active_test=False, deleted_test=False).browse(
                sorted(extra_ids)).exists()

        # in-scope AND active AND not-deleted partition — ONE batch search
        # over the candidate ids against the caller's grant domain (no
        # per-record queries). A soft-deleted order (lifecycle Delete request)
        # falls to the removal branch: field nurses must not see it.
        if candidates:
            in_scope_active = Order.with_context(active_test=False).search(
                scope['grant_domain'] + [
                    ('id', 'in', candidates.ids),
                    ('active', '=', True),
                    ('deleted', '=', False),
                ])
        else:
            in_scope_active = Order.browse()
        in_scope_ids = set(in_scope_active.ids)

        records = []
        removed_ids = set()

        # Removals first (UNCAPPED, unsorted): every changed candidate that is
        # NOT active-and-in-scope emits an id-only tombstone (§2.3 — never leak
        # the fields of an out-of-scope order). Removals must never be dropped
        # by the upsert cap, or a de-scoped order would linger on the device.
        for order in candidates:
            if order.id not in in_scope_ids:
                records.append({'id': order.id, 'is_deleted': True})
                removed_ids.add(order.id)

        # Upserts (CAPPED at FSO_UPSERT_CAP): when the caller's in-scope set
        # exceeds the cap we keep the LATEST orders by scheduled_datetime rather
        # than the write_date order the candidate query happened to return — a
        # nurse cares about upcoming/recent visits, not whichever rows were most
        # recently touched. Sort ONLY the in-scope upsert candidates; the
        # candidate WINDOW queries above (both §5.33 write-date windows) stay
        # untouched. `capped` is surfaced additively so the client SKIPS patient
        # GC on a truncated pull (order absence is not proof of de-scope).
        in_scope_sorted = in_scope_active.sorted(
            key=lambda o: o.scheduled_datetime or datetime.min, reverse=True)
        capped = len(in_scope_sorted) > FSO_UPSERT_CAP
        for order in in_scope_sorted[:FSO_UPSERT_CAP]:
            records.append(self._fso_record(order))
        upsert_count = min(len(in_scope_sorted), FSO_UPSERT_CAP)

        # Hard-delete tombstones (§2.3). On the 30-day fallback window use a
        # now-30d stamp floor (idempotent, harmless); otherwise `since`.
        tomb_floor = since_datetime
        if used_fallback:
            tomb_floor = fields.Datetime.now() - timedelta(days=30)
        tombstones = request.env['health.pwa.sync.tombstone'].sudo().search([
            ('res_model', '=', 'health.fieldservice.order'),
            ('stamp', '>=', tomb_floor),
        ])
        for tomb in tombstones:
            if tomb.res_id not in removed_ids and tomb.res_id not in in_scope_ids:
                records.append({'id': tomb.res_id, 'is_deleted': True})
                removed_ids.add(tomb.res_id)

        _logger.info(
            "Sync: %s FSO records (%s upserts, %s removals, capped=%s)",
            len(records), upsert_count, len(removed_ids), capped)
        fso_changes = {
            'model': 'health.fieldservice.order',
            'count': len(records),
            'records': records,
        }
        if capped:
            # Additive key — old clients ignore it, new clients skip patient GC.
            fso_changes['capped'] = True
        return (fso_changes, in_scope_active)

    def _get_team_changes(self, since_datetime, scope):
        """Get team changes since last sync (already member-scoped)."""
        domain = [
            '|',
            ('write_date', '>=', since_datetime),
            ('create_date', '>=', since_datetime),
        ]

        teams_scope = scope['teams']
        if teams_scope:
            domain.append(('id', 'in', teams_scope.ids))
        else:
            # No member teams -> no team reference data for this caller.
            return {'model': 'health.fieldservice.team', 'count': 0, 'records': []}

        teams = request.env['health.fieldservice.team'].sudo().search(domain)

        team_records = []
        for team in teams:
            team_records.append({
                'id': team.id,
                'name': team.name,
                'description': team.description,
                'active': team.active,
                'member_ids': team.member_ids.ids,
                'member_names': [m.name for m in team.member_ids],
                'created_date': team.create_date,
                'updated_date': team.write_date,
                'is_deleted': False,
            })

        return {
            'model': 'health.fieldservice.team',
            'count': len(team_records),
            'records': team_records,
        }

    def _get_service_type_changes(self, since_datetime):
        """Get service type changes since last sync (reference data, sudo)."""
        domain = [
            '|',
            ('write_date', '>=', since_datetime),
            ('create_date', '>=', since_datetime),
        ]

        service_types = request.env['health.service.type'].sudo().search(domain)

        service_type_records = []
        for stype in service_types:
            service_type_records.append({
                'id': stype.id,
                'name': stype.name,
                'code': stype.code,
                'description': stype.description,
                'duration_minutes': stype.duration_minutes,
                'base_price': stype.base_price,
                'category': stype.category,
                'active': stype.active,
                'available_home': stype.available_home,
                'available_clinic': stype.available_clinic,
                'available_telemedicine': stype.available_telemedicine,
                'requires_doctor': stype.requires_doctor,
                'requires_nurse': stype.requires_nurse,
                'staff_count': stype.staff_count,
                'created_date': stype.create_date,
                'updated_date': stype.write_date,
                'is_deleted': False,
            })

        return {
            'model': 'health.service.type',
            'count': len(service_type_records),
            'records': service_type_records,
        }

    def _get_facility_changes(self, since_datetime):
        """Get facility changes since last sync (reference data, sudo)."""
        domain = [
            '|',
            ('write_date', '>=', since_datetime),
            ('create_date', '>=', since_datetime),
        ]

        facilities = request.env['health.facility'].sudo().search(domain)

        facility_records = []
        for facility in facilities:
            facility_records.append({
                'id': facility.id,
                'name': facility.name,
                'code': facility.code,
                'facility_type': facility.facility_type,
                'street': facility.street,
                'street2': facility.street2,
                'city': facility.city,
                'state_id': facility.state_id.id if facility.state_id else None,
                'state_name': facility.state_id.name if facility.state_id else None,
                'zip': facility.zip,
                'country_id': facility.country_id.id if facility.country_id else None,
                'country_name': facility.country_id.name if facility.country_id else None,
                'phone': facility.phone,
                'email': facility.email,
                'website': facility.website,
                'operating_hours': facility.operating_hours,
                'active': facility.active,
                'created_date': facility.create_date,
                'updated_date': facility.write_date,
                'is_deleted': False,
            })

        return {
            'model': 'health.facility',
            'count': len(facility_records),
            'records': facility_records,
        }

    # ------------------------------------------------------------------
    # Push (offline writes back to server) — scoped
    # ------------------------------------------------------------------
    @http.route('/health_pwa/sync/push', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def sync_push_changes(self, **kwargs):
        """Push changes from mobile device back to server.

        Scoped: FSO writes require G1 assignment (money/state adjacent), patient
        writes require the patient to be in the caller's scope. Whitelisted
        writes run sudo so a minimal nurse can actually persist. `stage_id` is
        NOT writable via push (no producer repo-wide; pure attack surface)."""
        if not self._check_sync_access():
            return {'success': False, 'error': _('Access denied')}

        try:
            # jsonrpc dispatch passes params as kwargs.
            changes = kwargs.get('changes', {})
            scope = self._sync_scope()
            results = []

            # Process offline action replays FIRST (before the field-write
            # updates) so a queued Start lands before any same-batch field
            # write, and the pull that follows already reflects the new state
            # (pwa-offline-actions §2.2). Appended to the same `results` list —
            # the statistics keys count them too (shapes unchanged).
            if 'actions' in changes:
                results.extend(self._process_actions(changes.get('actions') or []))

            # Process FSO updates
            if 'field_service_orders' in changes:
                fso_results = self._process_fso_updates(changes['field_service_orders'])
                results.extend(fso_results)

            # Process patient updates (limited fields for mobile users)
            if 'patients' in changes:
                patient_results = self._process_patient_updates(changes['patients'], scope)
                results.extend(patient_results)

            # Calculate statistics
            successful_updates = len([r for r in results if r['success']])
            failed_updates = len([r for r in results if not r['success']])

            return {
                'success': True,
                'results': results,
                'statistics': {
                    'total_processed': len(results),
                    'successful_updates': successful_updates,
                    'failed_updates': failed_updates,
                },
                'server_time': fields.Datetime.now().isoformat(),
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ------------------------------------------------------------------
    # Offline action replay (pwa-offline-actions phase)
    # ------------------------------------------------------------------
    def _with_ref(self, result, client_ref):
        """Echo the incoming item's client_ref on its per-item result (§2.4 —
        additive key). Lets the client map each result back to the exact queued
        doc regardless of order, replacing the fragile index-based mapping."""
        if client_ref is not None:
            result['client_ref'] = client_ref
        return result

    def _parse_client_datetime(self, raw):
        """Parse a client's JS ISO datetime (from `new Date().toISOString()`)
        into a naive-UTC datetime, or None on absence/garbage. Mirrors
        `_parse_since`'s hardening (Z suffix, T separator, millis, tz offset)
        but returns None instead of a fallback so the caller can clamp to the
        server time. JS toISOString is always UTC, so the parsed naive value is
        directly comparable to `fields.Datetime.now()`."""
        if not raw or not isinstance(raw, str):
            return None
        try:
            value = raw
            if value.endswith('Z'):
                value = value[:-1] + '+00:00'
            value = value.replace('T', ' ').split('+')[0].split('.')[0].strip()
            return fields.Datetime.from_string(value) or None
        except Exception:
            return None

    def _action_error(self, action_type, fso_id, client_ref, message):
        """A per-item action error. `message` is a RAW (non-translated) machine
        string for the values the client keys on ('Access denied',
        'state_conflict') — the client renders its own localized toast, and a
        translated string here would break the JS clear/refetch match."""
        return self._with_ref({
            'type': 'action',
            'action_type': action_type,
            'id': fso_id,
            'success': False,
            'error': message,
        }, client_ref)

    def _receipt_result(self, receipt, client_ref):
        """Replay a stored receipt's exact per-item result verbatim (idempotent
        replay, fact 5). The current call's client_ref overrides the stored one
        so THIS device clears the right queued doc."""
        try:
            res = json.loads(receipt.result_json) if receipt.result_json else {}
        except Exception:
            res = {}
        if not isinstance(res, dict):
            res = {}
        # Drop the ORIGINAL device's stored ref before applying this call's —
        # a replay that carries no client_ref must not clear another device's
        # queued doc (review fix).
        res.pop('client_ref', None)
        return self._with_ref(res, client_ref)

    def _process_actions(self, actions):
        """Replay queued offline visit actions idempotently (§2.2).

        Each item is isolated in its OWN savepoint so one bad action cannot
        poison the batch (§2.2, batch isolation). Idempotency clones the
        health_evv append_event seam (fact 5): search the receipt ledger by
        (fso, type, uuid) first; a hit replays the stored result verbatim
        (applied AND rejected replays both return as-is). G1 assignment is
        required BEFORE any receipt is created so an unauthorized caller can
        never squat a uuid (§2.2.3)."""
        results = []
        Receipt = request.env['health.pwa.action.receipt'].sudo()
        Order = request.env['health.fieldservice.order'].sudo()

        for action in actions:
            client_ref = action.get('client_ref')
            action_type = action.get('action_type')
            fso_id = action.get('fso_id')
            client_action_uuid = (action.get('client_action_uuid') or '').strip()
            try:
                with request.env.cr.savepoint():
                    # 1. Validate action_type + uuid.
                    if action_type not in KNOWN_ACTION_TYPES:
                        results.append(self._action_error(
                            action_type, fso_id, client_ref, 'Unknown action type'))
                        continue
                    if not client_action_uuid or len(client_action_uuid) > 64:
                        results.append(self._action_error(
                            action_type, fso_id, client_ref,
                            'Invalid client_action_uuid'))
                        continue

                    # 2. Resolve order sudo; must exist and must not carry a
                    # lifecycle Delete request (the device may replay an
                    # offline action queued before the order was deleted).
                    order = Order.browse(fso_id) if fso_id else Order.browse()
                    if not fso_id or not order.exists():
                        results.append(self._action_error(
                            action_type, fso_id, client_ref, 'Order not found'))
                        continue
                    if order.deleted:
                        results.append(self._action_error(
                            action_type, fso_id, client_ref,
                            'Order was deleted (lifecycle)'))
                        continue

                    # 3. G1 required — no receipt for an unauthorized caller.
                    employee = self._employee_assigned_to(order)
                    if not employee:
                        results.append(self._action_error(
                            action_type, fso_id, client_ref, 'Access denied'))
                        continue

                    # 4. Idempotent replay — a hit returns the stored result.
                    domain = [
                        ('fso_id', '=', order.id),
                        ('action_type', '=', action_type),
                        ('client_action_uuid', '=', client_action_uuid),
                    ]
                    existing = Receipt.search(domain, limit=1)
                    if existing:
                        results.append(self._receipt_result(existing, client_ref))
                        continue

                    # Serialize replays per visit (clone fact 5's FOR UPDATE +
                    # re-search under the lock).
                    request.env.cr.execute(
                        "SELECT id FROM health_fieldservice_order "
                        "WHERE id = %s FOR UPDATE", (order.id,))
                    existing = Receipt.search(domain, limit=1)
                    if existing:
                        results.append(self._receipt_result(existing, client_ref))
                        continue

                    if action_type == 'start_service':
                        results.append(self._replay_start_service(
                            order, employee, action, client_action_uuid, client_ref))
                    else:
                        results.append(self._replay_save_clinical_notes(
                            order, employee, action, client_action_uuid, client_ref))
            except Exception as e:
                results.append(self._action_error(
                    action_type, fso_id, client_ref, str(e)))

        return results

    def _replay_start_service(self, order, employee, action, client_action_uuid, client_ref):
        """Replay a queued Start. State guard mirrors the online endpoint
        (api.py:721 / fact 1,3): only assigned/confirmed → in_progress. On
        conflict, record a REJECTED receipt so the same uuid stays rejected on
        every future replay (§2.2.5)."""
        Receipt = request.env['health.pwa.action.receipt'].sudo()
        claimed_at = self._parse_client_datetime(action.get('claimed_at'))

        if order.state not in ('assigned', 'confirmed'):
            result = self._with_ref({
                'type': 'action', 'action_type': 'start_service', 'id': order.id,
                'success': False, 'error': 'state_conflict', 'state': order.state,
            }, client_ref)
            Receipt.create({
                'fso_id': order.id, 'action_type': 'start_service',
                'client_action_uuid': client_action_uuid,
                'claimed_at': claimed_at, 'staff_id': employee.id,
                'state': 'rejected', 'reject_reason': 'state_conflict',
                'result_json': json.dumps(result, default=str),
            })
            return result

        # Apply the SAME transition as the online button (fact 1). This writes
        # state='in_progress' + actual_start_datetime=now() and fires the
        # timecard hook — expected and correct (§2.3).
        order.sudo().action_start_service()

        # Honor the CLAIMED start time (clamped) so timecards/EVV stay honest.
        now = fields.Datetime.now()
        clamped = False
        if (claimed_at and (now - timedelta(hours=48)) <= claimed_at
                <= (now + timedelta(minutes=5))):
            order.sudo().write({'actual_start_datetime': claimed_at})
        else:
            # Keep the server time action_start_service already wrote.
            clamped = True

        result = self._with_ref({
            'type': 'action', 'action_type': 'start_service', 'id': order.id,
            'success': True, 'state': 'in_progress',
        }, client_ref)
        if clamped:
            result['claimed_at_clamped'] = True

        Receipt.create({
            'fso_id': order.id, 'action_type': 'start_service',
            'client_action_uuid': client_action_uuid,
            'claimed_at': claimed_at, 'staff_id': employee.id,
            'state': 'applied',
            'result_json': json.dumps(result, default=str),
        })
        return result

    def _replay_save_clinical_notes(self, order, employee, action, client_action_uuid, client_ref):
        """Replay a queued clinical note as a health.clinical.note create. No
        state guard beyond order existence + G1 (mirrors the online endpoint,
        fact 2). Payload whitelisted to the fact-2 field set; unknown keys
        ignored. Note-create body duplicated from api.py:1002-1018 (A4)."""
        Receipt = request.env['health.pwa.action.receipt'].sudo()
        payload = action.get('payload') or {}

        note_vals = {'order_id': order.id}
        for field in NOTE_TEXT_FIELDS:
            val = payload.get(field, '')
            if val:
                note_vals[field] = val
        for count_field in NOTE_COUNT_FIELDS:
            if count_field in payload and payload[count_field] is not None:
                try:
                    note_vals[count_field] = int(payload[count_field])
                except (ValueError, TypeError):
                    pass

        note = request.env['health.clinical.note'].sudo().create(note_vals)

        result = self._with_ref({
            'type': 'action', 'action_type': 'save_clinical_notes', 'id': order.id,
            'success': True, 'note_id': note.id,
            'clinical_notes_submitted': order.clinical_notes_submitted,
            'clinical_note_count': order.clinical_note_count,
        }, client_ref)

        Receipt.create({
            'fso_id': order.id, 'action_type': 'save_clinical_notes',
            'client_action_uuid': client_action_uuid,
            'claimed_at': self._parse_client_datetime(action.get('claimed_at')),
            'staff_id': employee.id, 'state': 'applied',
            'result_json': json.dumps(result, default=str),
        })
        return result

    def _process_fso_updates(self, fso_changes):
        """Process field service order updates from mobile (assignment-scoped)."""
        results = []

        for change in fso_changes:
            client_ref = change.get('client_ref')
            try:
                order_id = change.get('id')
                if not order_id:
                    results.append(self._with_ref({
                        'type': 'field_service_order',
                        'id': None,
                        'success': False,
                        'error': _('Missing order ID')
                    }, client_ref))
                    continue

                order = request.env['health.fieldservice.order'].sudo().browse(order_id)
                if not order.exists():
                    results.append(self._with_ref({
                        'type': 'field_service_order',
                        'id': order_id,
                        'success': False,
                        'error': _('Order not found')
                    }, client_ref))
                    continue

                # G1 assignment required — no ACL fallback (write path).
                if not self._employee_assigned_to(order):
                    results.append(self._with_ref({
                        'type': 'field_service_order',
                        'id': order_id,
                        'success': False,
                        'error': _('Access denied')
                    }, client_ref))
                    continue

                # Only allow updating specific fields from mobile. `stage_id`
                # is deliberately NOT here (fact 10 — no producer, would let a
                # push drive booking state).
                allowed_fields = {
                    'patient_notes': 'patient_notes',
                    'completion_notes': 'completion_notes',
                    'duration_actual': 'duration_actual',
                    'service_lat': 'service_lat',
                    'service_lng': 'service_lng',
                }

                update_vals = {}
                for mobile_field, odoo_field in allowed_fields.items():
                    if mobile_field in change:
                        update_vals[odoo_field] = change[mobile_field]

                # Update the order (sudo — grant already checked)
                if update_vals:
                    order.sudo().write(update_vals)

                results.append(self._with_ref({
                    'type': 'field_service_order',
                    'id': order_id,
                    'success': True,
                    'updated_fields': list(update_vals.keys())
                }, client_ref))

            except Exception as e:
                results.append(self._with_ref({
                    'type': 'field_service_order',
                    'id': change.get('id'),
                    'success': False,
                    'error': str(e)
                }, client_ref))

        return results

    def _process_patient_updates(self, patient_changes, scope):
        """Process patient updates from mobile (limited fields, scope-checked)."""
        results = []
        patient_scope_ids = scope['patient_scope_ids']

        for change in patient_changes:
            client_ref = change.get('client_ref')
            try:
                patient_id = change.get('id')
                if not patient_id:
                    results.append(self._with_ref({
                        'type': 'patient',
                        'id': None,
                        'success': False,
                        'error': _('Missing patient ID')
                    }, client_ref))
                    continue

                patient = request.env['res.partner'].sudo().browse(patient_id)
                if not patient.exists() or not patient.is_patient:
                    results.append(self._with_ref({
                        'type': 'patient',
                        'id': patient_id,
                        'success': False,
                        'error': _('Patient not found')
                    }, client_ref))
                    continue

                # Scope: only patients in the caller's order horizon.
                if patient_id not in patient_scope_ids:
                    results.append(self._with_ref({
                        'type': 'patient',
                        'id': patient_id,
                        'success': False,
                        'error': _('Access denied')
                    }, client_ref))
                    continue

                # Only allow updating limited fields from mobile for security
                allowed_fields = {
                    'phone': 'phone',
                    'mobile': 'mobile',
                    'next_visit_date': 'next_visit_date',
                }

                update_vals = {}
                for mobile_field, odoo_field in allowed_fields.items():
                    if mobile_field in change:
                        update_vals[odoo_field] = change[mobile_field]

                if update_vals:
                    patient.sudo().write(update_vals)

                results.append(self._with_ref({
                    'type': 'patient',
                    'id': patient_id,
                    'success': True,
                    'updated_fields': list(update_vals.keys())
                }, client_ref))

            except Exception as e:
                results.append(self._with_ref({
                    'type': 'patient',
                    'id': change.get('id'),
                    'success': False,
                    'error': str(e)
                }, client_ref))

        return results

    # ------------------------------------------------------------------
    # Status / reset
    # ------------------------------------------------------------------
    @http.route('/health_pwa/sync/status', type='http', auth='user', methods=['GET'], csrf=False)
    def sync_status(self, **kwargs):
        """Get sync status and server information"""
        if not self._check_sync_access():
            return self._prepare_sync_response(error=_('Access denied'), status_code=403)

        try:
            # Get user's teams
            user_teams = request.env['health.fieldservice.team'].search([
                ('member_ids', 'in', [request.env.user.id])
            ])

            # Get recent activity counts
            today = fields.Date.today()
            recent_patients = request.env['res.partner'].search_count([
                ('is_patient', '=', True),
                ('write_date', '>=', today - timedelta(days=7))
            ])

            recent_orders = request.env['health.fieldservice.order'].search_count([
                ('write_date', '>=', today - timedelta(days=7))
            ])

            # Report the actually-installed health_pwa version (sudo read of
            # ir.module.module) instead of a hard-coded string.
            pwa_module = request.env['ir.module.module'].sudo().search(
                [('name', '=', 'health_pwa')], limit=1)

            status_data = {
                'server_time': fields.Datetime.now().isoformat(),
                'user_id': request.env.user.id,
                'user_name': request.env.user.name,
                'user_teams': [{'id': t.id, 'name': t.name} for t in user_teams],
                'sync_enabled': True,
                'recent_activity': {
                    'patients_updated_last_7_days': recent_patients,
                    'orders_updated_last_7_days': recent_orders,
                },
                'server_version': '19.0',
                'pwa_version': pwa_module.installed_version or '0',
            }

            return self._prepare_sync_response(data=status_data)

        except Exception as e:
            return self._prepare_sync_response(error=str(e), status_code=500)

    @http.route('/health_pwa/sync/reset', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def sync_reset_client(self, **kwargs):
        """Reset client sync state - force full resync"""
        if not self._check_sync_access():
            return {'success': False, 'error': _('Access denied')}

        try:
            # Return server time to reset client sync timestamp
            reset_data = {
                'success': True,
                'message': _('Client reset requested - perform full sync'),
                'reset_timestamp': fields.Datetime.now().isoformat(),
                'server_time': fields.Datetime.now().isoformat(),
            }

            return reset_data

        except Exception as e:
            return {'success': False, 'error': str(e)}
