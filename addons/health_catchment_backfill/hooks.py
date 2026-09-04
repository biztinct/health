import logging

_logger = logging.getLogger(__name__)


def _facility_province(env, user):
    """The catchment province of the user's healthcare facility, or empty.

    Derives via the employee link, which is where `healthcare_facility_id`
    lives ([[project_employee_facility_gap]]: employee=healthcare_facility_id).
    """
    employee = env['hr.employee'].with_context(active_test=False).search(
        [('user_id', '=', user.id)], limit=1)
    facility = employee.healthcare_facility_id if employee else False
    return facility.catchment_province_id if facility else env['health.catchment.province']


def backfill_doctor_catchment(env):
    """T-012: set catchment_province_id for Doctor-role users who have none.

    Idempotent — only NULL-catchment rows are written, so re-installing or
    running on a database that is already correct changes nothing. Doctors
    only; nurses are excluded by design (a separate visibility decision).
    """
    Users = env['res.users'].with_context(active_test=False)
    if 'job_role_id' not in Users._fields:
        # The job lives on the Access overlay, which this module does not
        # depend on. Without it there is no way to tell who is a doctor, and
        # guessing from a name is exactly what this stopped doing.
        _logger.info("T-012: the Access overlay is not on this database, so "
                     "no doctor can be identified — nothing backfilled")
        return
    doctors = Users.search([
        # WHOSE JOB IS DOCTOR, not whose role name contains the word. An owner
        # holds the Doctor bundle and is not a doctor; a role called "Doctor's
        # assistant" matched the word and was not one either.
        ('job_role_id.clinical_kind', '=', 'doctor'),
        ('catchment_province_id', '=', False),
    ])
    if not doctors:
        _logger.info("T-012: no Doctor-role user needs a catchment backfill")
        return

    fixed, undecidable = env['res.users'], []
    for user in doctors:
        province = _facility_province(env, user)
        if not province:
            undecidable.append(user.login)
            continue
        user.catchment_province_id = province.id
        fixed |= user
        _logger.info(
            "T-012: set catchment %r (id %s) on %r from their facility",
            province.display_name, province.id, user.login)

    _logger.info(
        "T-012: backfilled %s of %s NULL-catchment Doctor-role user(s): %s",
        len(fixed), len(doctors), ', '.join(sorted(fixed.mapped('login'))) or '(none)')
    if undecidable:
        _logger.warning(
            "T-012: %s Doctor-role user(s) have no derivable facility province "
            "and were LEFT NULL (they still see no catchment-scoped rows): %s",
            len(undecidable), ', '.join(sorted(undecidable)))


def post_init_hook(env):
    # §5.11: the post_init_hook signature is (env).
    backfill_doctor_catchment(env)
