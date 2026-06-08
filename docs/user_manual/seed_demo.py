# Seed clean, polished sample data for user-manual screenshots.
# Run on UAT via:  odoo-bin shell -d vietuat --no-http < seed_demo.py
# Idempotent (looks records up by name); commits at the end; writes a report.
import json
import pytz
from datetime import datetime
from odoo import fields

out = {"clients": {}, "bookings": [], "errors": []}
VN = pytz.timezone('Asia/Ho_Chi_Minh')


def to_utc(d, hour, minute=0):
    naive = datetime.combine(d, datetime.min.time()).replace(hour=hour, minute=minute)
    return VN.localize(naive).astimezone(pytz.utc).replace(tzinfo=None)


# Reference catchment + facility (HCMC)
hcm = (env['health.catchment.province'].search([('code', '=', '02')], limit=1)
       or env['health.catchment.province'].search([], limit=1))
fac = (env['health.facility'].search([('catchment_province_id', '=', hcm.id)], limit=1)
       or env['health.facility'].search([], limit=1))
out['catchment'] = hcm.id
out['facility'] = fac.id

# 1) Clean demo clients
clients_data = [
    ('Nguyễn Văn An', 'male', '0912345678', '12 Lê Lợi, Phường Bến Nghé', '1985-04-12'),
    ('Trần Thị Bích', 'female', '0987654321', '45 Nguyễn Huệ, Phường Bến Nghé', '1990-09-03'),
    ('Phạm Minh Đức', 'male', '0901122334', '88 Hai Bà Trưng, Phường Đa Kao', '1978-12-20'),
]
clients = []
P = env['res.partner'].with_context(mail_create_nolog=True, tracking_disable=True)
for name, gender, phone, street, dob in clients_data:
    vals = dict(name=name, is_patient=True, customer_rank=1, company_type='person',
                gender=gender, mobile=phone, phone=phone, street=street,
                city='Ho Chi Minh City', birth_date=dob,
                catchment_province_id=hcm.id, primary_facility_id=fac.id, source_type='phone')
    rec = env['res.partner'].search([('name', '=', name), ('is_patient', '=', True)], limit=1)
    try:
        if rec:
            rec.write(vals)
        else:
            rec = P.create(vals)
        clients.append(rec)
        out['clients'][name] = rec.id
    except Exception as e:
        out['errors'].append('client %s: %s' % (name, str(e)[:100]))

# 2) Bookings across every lifecycle state, scheduled TODAY
nurse = (env['hr.employee'].search([('is_healthcare_staff', '=', True), ('name', 'ilike', 'HCMC')], limit=1)
         or env['hr.employee'].search([('is_healthcare_staff', '=', True)], limit=1))
today = fields.Date.context_today(env['res.partner'])
states = [
    ('draft', 'health_fieldservice.stage_draft', 9),
    ('confirmed', 'health_fieldservice.stage_booked', 10),
    ('assigned', 'health_fieldservice.stage_assigned', 11),
    ('in_progress', 'health_fieldservice.stage_en_route', 13),
    ('completed', 'health_fieldservice.stage_completed', 15),
]
FSO = env['health.fieldservice.order'].with_context(
    mail_create_nolog=True, tracking_disable=True, skip_notification=True)
for i, (state, stage_xml, hour) in enumerate(states):
    client = clients[i % len(clients)] if clients else None
    if not client:
        continue
    stage = env.ref(stage_xml, raise_if_not_found=False)
    try:
        b = FSO.create({
            'patient_id': client.id, 'facility_id': fac.id,
            'service_type': 'home_visit', 'service_location': 'home',
            'scheduled_datetime': to_utc(today, hour), 'scheduled_duration': 60,
            'state': state, 'stage_id': stage.id if stage else False,
            'booking_source': 'phone',
            'patient_notes': 'Demo booking for user manual (%s).' % state,
        })
        if state in ('assigned', 'in_progress', 'completed') and nurse and 'assigned_staff_ids' in b._fields:
            try:
                b.with_context(skip_travel_recompute=True).write({'assigned_staff_ids': [(4, nurse.id)]})
            except Exception as e:
                out['errors'].append('assign %s: %s' % (b.id, str(e)[:80]))
        out['bookings'].append({'id': b.id, 'state': state})
    except Exception as e:
        out['errors'].append('booking %s: %s' % (state, str(e)[:120]))

# 3) CRM contact (lead)
try:
    lvals = {'name': 'Lê Thị Hồng', 'contact_name': 'Lê Thị Hồng', 'phone': '0934567890',
             'type': 'lead', 'contact_status': 'lead'}
    if 'service_interest' in env['crm.lead']._fields:
        lvals['service_interest'] = 'home_visit'
    if 'description' in env['crm.lead']._fields:
        lvals['description'] = 'Interested in home nursing care. Demo contact for user manual.'
    lead = env['crm.lead'].search([('name', '=', 'Lê Thị Hồng')], limit=1)
    if lead:
        lead.write(lvals)
    else:
        lead = env['crm.lead'].with_context(mail_create_nolog=True, tracking_disable=True).create(lvals)
    out['lead'] = lead.id
except Exception as e:
    out['errors'].append('lead: %s' % str(e)[:120])

# 4) Invoice + payment for the first client (best effort)
try:
    if clients:
        inv = env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': clients[0].id,
            'invoice_line_ids': [(0, 0, {'name': 'Home Visit — Nursing Care', 'quantity': 1, 'price_unit': 450000})],
        })
        inv.action_post()
        out['invoice'] = inv.id
        pt = env['health.payment.transaction'].with_context(mail_create_nolog=True, tracking_disable=True).create({
            'patient_id': clients[0].id, 'amount': 450000, 'payment_method': 'cash',
            'transaction_date': fields.Datetime.now(), 'transaction_type': 'immediate', 'status': 'collected',
        })
        out['payment'] = pt.id
except Exception as e:
    out['errors'].append('invoice/payment: %s' % str(e)[:150])

env.cr.commit()
open('/tmp/seed_demo.json', 'w').write(json.dumps(out, default=str, ensure_ascii=False))
print('SEED_DONE')
