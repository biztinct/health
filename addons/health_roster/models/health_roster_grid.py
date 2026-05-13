from datetime import date, datetime, timedelta

import pytz
from odoo import api, fields, models

import logging

_logger = logging.getLogger(__name__)


class HealthRosterGrid(models.TransientModel):
    _name = 'health.roster.grid'
    _description = 'Nursing Roster Planning Grid API'

    @api.model
    def get_roster_grid_data(self, week_start_str, filters=None):
        filters = filters or {}
        tz = pytz.timezone(self.env.user.tz or 'Asia/Ho_Chi_Minh')
        week_start = fields.Date.from_string(week_start_str)
        week_end = week_start + timedelta(days=6)

        days = []
        today = date.today()
        for i in range(7):
            d = week_start + timedelta(days=i)
            days.append({
                'date': d.isoformat(),
                'label': d.strftime('%a'),
                'full_label': d.strftime('%a %d %b'),
                'is_today': d == today,
                'is_weekend': d.weekday() >= 5,
            })

        day_start_utc = tz.localize(
            datetime.combine(week_start, datetime.min.time())
        ).astimezone(pytz.utc).replace(tzinfo=None)
        day_end_utc = tz.localize(
            datetime.combine(week_end, datetime.max.time())
        ).astimezone(pytz.utc).replace(tzinfo=None)

        staff_domain = [
            ('is_healthcare_staff', '=', True),
            ('employment_status', '=', 'active'),
            ('is_nurse_role', '=', True),
        ]
        if filters.get('facility_id'):
            staff_domain.append(('primary_facility_id', '=', int(filters['facility_id'])))
        if filters.get('catchment_id'):
            staff_domain.append(('staff_catchment_province_id', '=', int(filters['catchment_id'])))
        if filters.get('search'):
            staff_domain.append(('name', 'ilike', filters['search']))

        staff_records = self.env['hr.employee'].sudo().search(staff_domain, order='name asc')
        staff_ids = staff_records.ids
        if not staff_ids:
            return self._empty_response(days, week_start_str, week_end)

        staff_read = staff_records.read([
            'name', 'access_role_display', 'primary_facility_id',
            'staff_catchment_province_id', 'color', 'max_daily_assignments',
        ])
        staff_map = {s['id']: s for s in staff_read}

        self.env.cr.execute("""
            SELECT
                a.id, a.staff_id, a.planned_start_time, a.planned_end_time,
                a.state, a.priority, a.assignment_role,
                a.fso_id, f.name AS fso_name, f.service_type,
                p.name AS patient_name
            FROM health_staff_assignment a
            LEFT JOIN health_fieldservice_order f ON f.id = a.fso_id
            LEFT JOIN res_partner p ON p.id = f.patient_id
            WHERE a.planned_start_time >= %s
              AND a.planned_start_time <= %s
              AND a.state NOT IN ('cancelled', 'template')
              AND a.staff_id IS NOT NULL
            ORDER BY a.planned_start_time
        """, (day_start_utc, day_end_utc))
        raw_assignments = self.env.cr.dictfetchall()

        assignments_by_staff = {}
        for row in raw_assignments:
            assignments_by_staff.setdefault(row['staff_id'], []).append(row)

        leaves = self._get_leaves(staff_ids, week_start, week_end)

        staff_data = []
        total_available = 0
        total_on_leave = 0
        total_assignments_count = 0
        total_conflicts = 0

        for emp_id in staff_ids:
            s = staff_map[emp_id]
            emp_rows = assignments_by_staff.get(emp_id, [])
            assignments_by_date = {}
            emp_conflicts = 0

            for row in emp_rows:
                pst = row['planned_start_time']
                if not pst:
                    continue
                if pst.tzinfo is None:
                    local_start = pytz.utc.localize(pst).astimezone(tz)
                else:
                    local_start = pst.astimezone(tz)
                d_key = local_start.strftime('%Y-%m-%d')
                start_h = local_start.hour + local_start.minute / 60.0
                end_h = start_h + 1.0

                pet = row['planned_end_time']
                end_str = ''
                if pet:
                    if pet.tzinfo is None:
                        local_end = pytz.utc.localize(pet).astimezone(tz)
                    else:
                        local_end = pet.astimezone(tz)
                    end_h = local_end.hour + local_end.minute / 60.0
                    end_str = local_end.strftime('%I:%M%p').lstrip('0').lower()

                entry = {
                    'id': row['id'],
                    'fso_id': row['fso_id'],
                    'booking_ref': row['fso_name'] or '',
                    'patient_name': row['patient_name'] or '',
                    'service_type': row['service_type'] or '',
                    'start': local_start.strftime('%I:%M%p').lstrip('0').lower(),
                    'end': end_str,
                    'start_hour': round(start_h, 2),
                    'end_hour': round(end_h, 2),
                    'state': row['state'],
                    'priority': row['priority'],
                    'assignment_role': row['assignment_role'],
                    'has_conflict': False,
                }
                assignments_by_date.setdefault(d_key, []).append(entry)

            for d_key, day_entries in assignments_by_date.items():
                day_entries.sort(key=lambda x: x['start_hour'])
                for i_idx in range(len(day_entries)):
                    for j_idx in range(i_idx + 1, len(day_entries)):
                        a = day_entries[i_idx]
                        b = day_entries[j_idx]
                        if a['start_hour'] < b['end_hour'] and b['start_hour'] < a['end_hour']:
                            a['has_conflict'] = True
                            b['has_conflict'] = True
                            emp_conflicts += 1

            total_hours = sum(
                (e['end_hour'] - e['start_hour']) for entries in assignments_by_date.values() for e in entries
            )
            max_daily = s.get('max_daily_assignments') or 8
            max_weekly_hours = max_daily * 7
            load_pct = round((total_hours / max_weekly_hours * 100) if max_weekly_hours else 0, 1)

            emp_leaves = leaves.get(emp_id, {})

            if emp_leaves and all(d['date'] in emp_leaves for d in days):
                total_on_leave += 1
            else:
                total_available += 1

            total_assignments_count += len(emp_rows)
            total_conflicts += emp_conflicts

            name = s.get('name') or ''
            facility = s.get('primary_facility_id')
            catchment = s.get('staff_catchment_province_id')
            staff_data.append({
                'id': emp_id,
                'name': name,
                'initials': ''.join([p[0].upper() for p in name.split()[:2]]) or 'N',
                'role': s.get('access_role_display') or 'Nurse',
                'facility': facility[1] if facility else '',
                'facility_id': facility[0] if facility else False,
                'catchment': catchment[1] if catchment else '',
                'color_index': s.get('color') or 0,
                'total_hours': round(total_hours, 1),
                'max_daily': max_daily,
                'load_pct': load_pct,
                'assignment_count': len(emp_rows),
                'assignments': assignments_by_date,
                'leaves': emp_leaves,
            })

        if filters.get('status') == 'on_leave':
            staff_data = [s for s in staff_data if s['leaves']]
        elif filters.get('status') == 'available':
            staff_data = [s for s in staff_data if not all(d['date'] in s['leaves'] for d in days)]

        self.env.cr.execute("""
            SELECT
                f.id, f.name, f.service_type, f.scheduled_datetime,
                f.estimated_duration, f.priority, f.state,
                p.name AS patient_name,
                cp.name AS catchment_name
            FROM health_fieldservice_order f
            LEFT JOIN res_partner p ON p.id = f.patient_id
            LEFT JOIN health_catchment_province cp ON cp.id = f.catchment_province_id
            WHERE f.scheduled_datetime >= %s
              AND f.scheduled_datetime <= %s
              AND f.has_staff_assigned = false
              AND f.state IN ('draft', 'confirmed')
            ORDER BY f.scheduled_datetime
        """, (day_start_utc, day_end_utc))
        unassigned_rows = self.env.cr.dictfetchall()

        unassigned_by_date = {}
        for row in unassigned_rows:
            sdt = row['scheduled_datetime']
            if not sdt:
                continue
            if sdt.tzinfo is None:
                local_dt = pytz.utc.localize(sdt).astimezone(tz)
            else:
                local_dt = sdt.astimezone(tz)
            d_key = local_dt.strftime('%Y-%m-%d')
            start_h = local_dt.hour + local_dt.minute / 60.0
            duration = row['estimated_duration'] or 1.0
            end_h = start_h + duration

            unassigned_by_date.setdefault(d_key, []).append({
                'id': row['id'],
                'booking_ref': row['name'] or '',
                'patient_name': row['patient_name'] or '',
                'service_type': row['service_type'] or '',
                'start': local_dt.strftime('%I:%M%p').lstrip('0').lower(),
                'end': (local_dt + timedelta(hours=duration)).strftime('%I:%M%p').lstrip('0').lower(),
                'start_hour': round(start_h, 2),
                'end_hour': round(end_h, 2),
                'priority': row['priority'] or '1',
                'state': row['state'],
                'catchment': row['catchment_name'] or '',
            })

        facilities = self.env['health.facility'].sudo().search_read([], ['name'], order='name')
        catchments = self.env['health.catchment.province'].sudo().search_read([], ['name'], order='name')

        return {
            'days': days,
            'staff': staff_data,
            'unassigned': unassigned_by_date,
            'summary': {
                'total_staff': len(staff_data),
                'available': total_available,
                'on_leave': total_on_leave,
                'total_assignments': total_assignments_count,
                'unassigned_bookings': len(unassigned_rows),
                'avg_utilization': round(
                    sum(s['load_pct'] for s in staff_data) / len(staff_data) if staff_data else 0, 1
                ),
                'conflicts': total_conflicts,
            },
            'filters': {
                'facilities': [{'id': f['id'], 'name': f['name']} for f in facilities],
                'catchments': [{'id': c['id'], 'name': c['name']} for c in catchments],
            },
            'week_start': week_start_str,
            'week_end': week_end.isoformat(),
        }

    def _get_leaves(self, staff_ids, week_start, week_end):
        leaves = {}
        try:
            self.env.cr.execute("""
                SELECT l.employee_id, l.date_from, l.date_to, ht.name AS leave_type
                FROM hr_leave l
                LEFT JOIN hr_leave_type ht ON ht.id = l.holiday_status_id
                WHERE l.state IN ('validate', 'validate1')
                  AND l.date_from <= %s
                  AND l.date_to >= %s
                  AND l.employee_id = ANY(%s)
            """, (
                datetime.combine(week_end, datetime.max.time()),
                datetime.combine(week_start, datetime.min.time()),
                list(staff_ids),
            ))
            for row in self.env.cr.dictfetchall():
                emp_id = row['employee_id']
                lv_start = row['date_from'].date() if isinstance(row['date_from'], datetime) else row['date_from']
                lv_end = row['date_to'].date() if isinstance(row['date_to'], datetime) else row['date_to']
                cur = max(lv_start, week_start)
                end_d = min(lv_end, week_end)
                while cur <= end_d:
                    leaves.setdefault(emp_id, {})[cur.isoformat()] = {
                        'type': row['leave_type'] or 'Leave',
                    }
                    cur += timedelta(days=1)
        except Exception:
            _logger.debug("hr.leave not available, skipping leave overlay")
        return leaves

    def _empty_response(self, days, week_start_str, week_end):
        facilities = self.env['health.facility'].sudo().search_read([], ['name'], order='name')
        catchments = self.env['health.catchment.province'].sudo().search_read([], ['name'], order='name')
        return {
            'days': days,
            'staff': [],
            'unassigned': {},
            'summary': {
                'total_staff': 0, 'available': 0, 'on_leave': 0,
                'total_assignments': 0, 'unassigned_bookings': 0,
                'avg_utilization': 0, 'conflicts': 0,
            },
            'filters': {
                'facilities': [{'id': f['id'], 'name': f['name']} for f in facilities],
                'catchments': [{'id': c['id'], 'name': c['name']} for c in catchments],
            },
            'week_start': week_start_str,
            'week_end': week_end.isoformat(),
        }
