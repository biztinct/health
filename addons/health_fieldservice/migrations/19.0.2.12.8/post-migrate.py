"""UAT round 6, item 9b: the booking model's user-facing name is "Booking"
(Vietnamese "Lịch hẹn", the term the booking screens already use). The
registry writes the English name; the Vietnamese one is set here because a
module upgrade does not overwrite an existing translation (it was a machine
rendering of the old technical name)."""
import json


def migrate(cr, version):
    cr.execute("""
        UPDATE ir_model
           SET name = name || %s::jsonb
         WHERE model = 'health.fieldservice.order'
    """, [json.dumps({'en_US': 'Booking', 'vi_VN': 'Lịch hẹn'})])
