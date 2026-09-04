# -*- coding: utf-8 -*-
"""What a role IS, as opposed to what it lets somebody do.

THE TWO QUESTIONS THAT USED TO SHARE ONE FIELD. Until now a person had one role,
and that single row answered both "what may this person open" and "what is this
person" — the schedule called them a nurse, the pickers offered them as a doctor,
the dashboards counted them as an operations manager, all off the same pointer.

Bundles cannot answer the second question. An owner holds the Doctor bundle
because an owner can do everything a doctor can; that does not make the owner a
doctor, and a roster that put them on the ward round because of it would be
wrong in a way nobody could argue with.

So the two questions are separated. PERMISSION is the roles somebody HOLDS, on
the Access home. CLASSIFICATION is one field on the staff record — their job —
and this is what tells the product what a job COUNTS AS: a doctor, a nurse, an
operations manager, or none of those.

WHY A SEPARATE FIELD AND NOT THE NAME. The old rule read the role's name and
looked for the word "doctor" in it. That is right for exactly the nine roles
this clinic has today and wrong for the tenth: "Doctor's assistant" matches and
is not a doctor, "Bác sĩ" does not match and is. A clinic that renames a role on
its own card should not silently change who is on the duty roster.
"""

from odoo import fields, models

#: What the product's own screens ask about a job. Deliberately short: this is
#: not a taxonomy of the profession, it is the list of questions the schedule,
#: the pickers and the dashboards actually ask.
CLINICAL_KINDS = [
    ('doctor', 'A doctor'),
    ('nurse', 'A nurse'),
    ('operations_manager', 'An operations manager'),
    ('other', 'Something else'),
]

#: How the nine roles this clinic already runs on are read the first time, and
#: only the first time. Exactly the rule that was in the code before — the word
#: in the name — applied ONCE by the migration so that nothing changes on the
#: day this ships, and then never again: after that the field is what somebody
#: has said, not what a substring happened to match.
FIRST_READ = (
    ('doctor', 'doctor'),
    ('nurse', 'nurse'),
    ('operations manager', 'operations_manager'),
)


def kind_from_name(name):
    """The one-off reading of a role's name. See FIRST_READ."""
    lowered = (name or '').strip().lower()
    for needle, kind in FIRST_READ:
        if needle in lowered:
            return kind
    return 'other'


class BizAccessRole(models.Model):
    _inherit = 'biz.access.role'

    clinical_kind = fields.Selection(
        CLINICAL_KINDS, string='What this role is, clinically',
        default='other', required=True,
        help='What somebody employed in this job COUNTS AS on the rest of the '
             'screens — the duty roster, the staff pickers and the reports. It '
             'has nothing to do with what the role lets them open; that is the '
             'list of abilities above.')

    def counts_as_line(self):
        """"Counts as: a nurse" — one line for the role card."""
        self.ensure_one()
        labels = dict(CLINICAL_KINDS)
        if self.clinical_kind in (False, 'other'):
            return ''
        return labels.get(self.clinical_kind, '')
