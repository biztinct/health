# -*- coding: utf-8 -*-
"""The cockpit's engine: everything the platform owner's screen actually does.

WHAT THIS FILE IS ALLOWED TO DO, AND THE FOUR RAILS IT KEEPS.

  R1  NEVER A SILENT WRITE TO A CUSTOMER'S SYSTEM. Every cross-database write
      here happens because a person pressed something, has a dry run in front
      of it, and leaves a line in that customer's own log. The scheduled jobs at
      the bottom READ; they never install, upgrade or repair anything.

  R2  THE NEVER-LIST STANDS, and it is re-asked of the LITERAL list about to be
      written — not of the list it was computed from. Every earlier check is a
      check of something else.

  R5  CROSS-DATABASE WRITES GO THROUGH THE ORM (`_tenant_env`), NEVER RAW SQL.
      A settings row changed behind a running registry's back stays cached
      there until something happens to clear it, which on a system nobody
      restarts is "never". Raw SQL is for READS, and reads are most of this
      file: opening a whole registry per customer to answer "what is installed"
      would make a read-only screen the most expensive thing on the machine.

  R6  ANY DECISION A TEST CANNOT REACH IS LIFTED OUT. `sync_rules.py` and
      `provision_rules.py` hold every judgement; what is left here is reads,
      writes and acts.

AND ONE MORE THAT IS NOT OPTIONAL ON THIS MACHINE (ledger F56 / H1). This box
runs TWO worker processes plus a gevent one, so a cross-database commit that
does not call `signal_changes()` is invisible to the other two: the platform
would say a customer had been told something, their database would agree in
SQL, and their people would go on seeing the old answer. `_tenant_env` calls it.
"""
import json
import logging
import os
import re
import secrets
import shutil
import socket
import ssl
import subprocess
import tarfile
import tempfile
import time
import urllib.request
from contextlib import contextmanager
from datetime import date, datetime, timedelta

import odoo
from odoo import SUPERUSER_ID, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.modules.registry import Registry
from odoo.service import db as db_service

from . import module_set as mset
from . import tenants_common as common
from .module_set import customer_module_set, module_set_rows
from .provision_rules import (
    PROVISION_STEPS, STEP_KEYS, backup_verdict, check_slug, free_memory_mb,
    generated_password, human_bytes, memory_verdict, next_step, step_label,
)
from .sync_rules import (
    held_back_rows, log_lines_of_interest, master_behind_files, norm_version,
    release_name, release_state, sync_diff, template_cron_plan,
)

_logger = logging.getLogger(__name__)

#: How many nightly copies of one customer are kept. Copies taken by hand and
#: the final one before a customer is closed are kept for ever.
NIGHTLY_KEEP = 14

#: The tail of the log the health reader looks at. The file is tens of
#: megabytes and grows; reading all of it to answer "did anything go wrong in
#: the last day" would be the most expensive thing on the screen (ledger F27).
LOG_TAIL_BYTES = 20 * 1024 * 1024
LOG_PATH = '/var/log/odoo/odoo-server.log'

#: The three scripts the application account may run as root, and nothing else
#: (`/etc/sudoers.d/biz-tenants`). Named here so that a missing one is a
#: sentence on screen rather than a traceback.
CERT_SCRIPT = '/usr/local/bin/biz-tenant-cert'
DETACH_SCRIPT = '/usr/local/bin/biz-domain-detach'

_DBNAME_RE = re.compile(r'^[a-z][a-z0-9_-]{1,62}$')


def _direct(fn):
    """Run one database-service function with the management gate lifted.

    The framework's own `odoo.service.db` helpers are wrapped by
    `check_db_management_enabled`, which refuses while `list_db` is False — and
    `list_db` is False here on purpose, for the web surface, on top of the web
    server answering 404 to every database-manager address on every hostname.

    So the flag is lifted for the length of ONE call and put back in a
    `finally`. Our own `_require_platform_admin()` guards every entry point that
    reaches this, so nothing is opened up by it; what is bypassed is the
    RPC-exposure gate and nothing else.
    """
    def run(*args, **kwargs):
        cfg = odoo.tools.config
        prev = cfg['list_db']
        cfg['list_db'] = True
        try:
            return fn(*args, **kwargs)
        finally:
            cfg['list_db'] = prev
    return run


class BizTenants(models.AbstractModel):
    _name = 'biz.tenants'
    _description = 'Platform cockpit'

    # =====================================================================
    #  GUARDS AND HELPERS
    # =====================================================================
    def _require_platform_admin(self):
        """THIS IS THE PLATFORM OWNER'S SCREEN, NOT A CUSTOMER-FACING ONE.

        `base.group_system` and nothing softer. Everything below can create,
        copy, restore and remove a database — including the master's — so the
        gate is the same one that owns the machine. A customer's own
        administrator deliberately does not hold it (the two-ring rule), and
        that is what makes it the right gate here.
        """
        user = self.env.user
        if not (self.env.su or user._is_admin()
                or user.has_group('base.group_system')):
            raise AccessError(self.env._(
                "The customers screen belongs to whoever runs this machine."))

    # ------------------------------------------------------------- settings
    def _apex(self):
        return common.apex(self.env)

    def _template_db(self):
        return common.template_db(self.env)

    def _backup_root(self):
        return common.param(self.env, common.P_BACKUP_ROOT)

    def _http_port(self):
        return int(odoo.tools.config['http_port'] or 8069)

    def _tenant_host(self, slug):
        apex = self._apex()
        return '%s.%s' % (slug, apex) if apex else slug

    def _tenant_url(self, slug):
        return 'https://%s' % self._tenant_host(slug)

    def _platform_url(self):
        apex = self._apex()
        return 'https://%s' % apex if apex else ''

    # ------------------------------------------------------- reading a box
    @contextmanager
    def _pg_cursor(self, dbname='postgres'):
        """An autocommit cursor on another database of this cluster. READS ONLY.

        AUTOCOMMIT IS THE POINT. A failed probe on one number must not poison
        the ones after it — that is exactly how a schema change once zeroed
        every count that followed the first one to fail, silently.

        And it is READS ONLY as a rule, not as a habit: a write here would be
        invisible to the registry serving that customer, which is what rail R5
        exists to stop.
        """
        conn = odoo.sql_db.db_connect(dbname)
        cr = conn.cursor()
        try:
            cr._cnx.autocommit = True
            yield cr
        finally:
            cr.close()

    def _db_exists(self, name):
        with self._pg_cursor() as cr:
            cr.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
            return bool(cr.fetchone())

    def _all_databases(self):
        with self._pg_cursor() as cr:
            cr.execute("SELECT datname FROM pg_database ORDER BY 1")
            return [r[0] for r in cr.fetchall()]

    def _db_owner(self, name):
        """Who owns a database. THE FAILURE THIS ANSWERS LOOKS LIKE A ROUTING
        BUG (ledger H58): the application lists only the databases owned by the
        account it connects as, so a system owned by anybody else is invisible
        to it and its address answers a redirect to a chooser rather than a
        sign-in page — with nothing in the log to say why."""
        with self._pg_cursor() as cr:
            cr.execute("SELECT r.rolname FROM pg_database d "
                       "JOIN pg_roles r ON r.oid = d.datdba "
                       "WHERE d.datname = %s", (name,))
            row = cr.fetchone()
            return row[0] if row else ''

    def _db_size(self, name):
        try:
            with self._pg_cursor() as cr:
                cr.execute("SELECT pg_database_size(%s)", (name,))
                row = cr.fetchone()
                return float(row[0]) if row else 0.0
        except Exception:                                    # noqa: BLE001
            return 0.0

    def _filestore_path(self, dbname):
        return odoo.tools.config.filestore(dbname)

    def _filestore_size(self, dbname):
        total, count = 0.0, 0
        try:
            for root, _dirs, files in os.walk(self._filestore_path(dbname)):
                for f in files:
                    try:
                        total += os.path.getsize(os.path.join(root, f))
                        count += 1
                    except OSError:
                        pass
        except OSError:
            pass
        return total, count

    @contextmanager
    def _tenant_env(self, dbname):
        """A data environment on another database of this cluster.

        COMMITS ON SUCCESS, AND THEN TELLS EVERY OTHER PROCESS WHAT IT CHANGED
        (ledger F56). A bare commit writes the row and clears the cache of THIS
        process's copy of that registry — and stops there. The cluster-wide
        invalidation sequence is only bumped by `signal_changes()`, which the
        framework calls at the end of a request or a scheduled job and which
        nothing calls here.

        ON A SINGLE-PROCESS BOX that is survivable, because the registry being
        cleared IS the one serving that customer. This box runs two workers and
        a gevent process (ledger H1), so without this line the platform says a
        customer has been told something, their database agrees in SQL, and
        two-thirds of their people go on seeing yesterday's answer.
        """
        reg = Registry(dbname)
        with reg.cursor() as cr:
            yield api.Environment(cr, SUPERUSER_ID, {})
            cr.commit()
        reg.signal_changes()

    def _probe(self, host):
        """Ask this machine's own web port for a page, as that hostname.

        Through 127.0.0.1 with the Host header set, so it measures the
        APPLICATION rather than the internet between here and a browser. The
        certificate is measured separately.
        """
        url = 'http://127.0.0.1:%d/web/login' % self._http_port()
        req = urllib.request.Request(url, headers={'Host': host})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                return resp.status, int((time.time() - t0) * 1000)
        except urllib.error.HTTPError as e:
            return e.code, int((time.time() - t0) * 1000)
        except Exception:                                    # noqa: BLE001
            return 0, -1

    def _peer_cert(self, server_name):
        """The certificate the web server ACTUALLY SERVES for this address.

        Probed over https on 127.0.0.1 with the address as the SNI name, so it
        reports what a visitor would really be handed — including which server
        block won. Reading files off disk instead would be a lie by omission:
        it is root-only, and it cannot tell you which block the web server
        picked.
        """
        blank = {'text': '', 'expires': None, 'days_left': None}
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with socket.create_connection(('127.0.0.1', 443), timeout=4) as sock:
                with ctx.wrap_socket(sock, server_hostname=server_name) as tls:
                    der = tls.getpeercert(binary_form=True)
            pem = ssl.DER_cert_to_PEM_cert(der)
            with tempfile.NamedTemporaryFile('w', suffix='.pem',
                                             delete=False) as fh:
                fh.write(pem)
                path = fh.name
            try:
                out = subprocess.run(
                    ['openssl', 'x509', '-in', path, '-noout', '-text'],
                    capture_output=True, text=True, timeout=6).stdout
            finally:
                os.unlink(path)
        except Exception:                                    # noqa: BLE001
            return blank
        res = {'text': out, 'expires': None, 'days_left': None}
        match = re.search(r'Not After\s*:\s*(.+)', out)
        if match:
            try:
                # "Nov 12 02:24:43 2026 GMT" — the day is space-padded under 10.
                end = datetime.strptime(' '.join(match.group(1).split()),
                                        '%b %d %H:%M:%S %Y %Z')
                res['expires'] = end.date()
                res['days_left'] = (end - datetime.utcnow()).days
            except ValueError:
                pass
        return res

    # ---------------------------------------------------------------- misc
    def _human(self, nbytes):
        return human_bytes(nbytes)

    def _stamp(self, dt):
        return dt.isoformat(sep=' ', timespec='minutes') if dt else None

    def _free_memory_mb(self):
        try:
            with open('/proc/meminfo', encoding='utf-8') as fh:
                return free_memory_mb(fh.read())
        except OSError:
            return -1

    def _tenants(self):
        return self.env['biz.tenant'].sudo()

    # =====================================================================
    #  1. THE FLEET
    #
    #  READ THROUGH SQL, NEVER THROUGH A DATA ENVIRONMENT. One registry load
    #  per customer would make the cheapest screen in the cockpit the most
    #  expensive thing on the machine — and on a box with 2 GB of memory it
    #  would be the most dangerous too (ACCESS H4).
    # =====================================================================
    @api.model
    def get_fleet(self):
        self._require_platform_admin()
        tenants = self._tenants().search([])
        serving = tenants.filtered(lambda t: t.state in ('live', 'provisioning',
                                                         'error'))
        live = tenants.filtered(lambda t: t.state == 'live')
        free_mb = self._free_memory_mb()
        try:
            usage = shutil.disk_usage('/')
            disk_free, disk_pct = self._human(usage.free), int(
                usage.free * 100 / usage.total)
        except OSError:
            disk_free, disk_pct = '—', 0
        last_backups = [t.last_backup_at for t in live if t.last_backup_at]
        return {
            'apex': self._apex(),
            'brand': common.brand(self.env),
            'platform_url': self._platform_url(),
            'master_db': self.env.cr.dbname,
            'template_db': self._template_db(),
            'steps': [{'key': k, 'label': label} for k, label in PROVISION_STEPS],
            'tenants': [self._brief(t) for t in tenants],
            'counts': {
                'live': len(live),
                'setting_up': len(tenants.filtered(
                    lambda t: t.state in ('draft', 'provisioning'))),
                'attention': len(tenants.filtered(lambda t: t.state == 'error'))
                             + len(tenants.filtered(
                                 lambda t: t.health_state in ('down', 'warn'))),
                'closed': len(tenants.filtered(
                    lambda t: t.state == 'decommissioned')),
            },
            # THE GAUGE. `free_mb` and `floor_mb` are kept as the words the
            # fleet strip has always used; `capacity` is the real answer —
            # how many MORE customers fit — and the refusal on new customers
            # reads that and nothing else.
            'capacity': self._capacity(),
            'alert': self.alert_banner(),
            'machine': {
                'free_mb': free_mb,
                'floor_mb': common.memory_floor_mb(self.env),
                'disk_free': disk_free,
                'disk_free_pct': disk_pct,
                'storage': self._human(
                    sum(serving.mapped('db_size'))
                    + sum(serving.mapped('filestore_size'))),
            },
            'backups': {
                'last': self._stamp(max(last_backups)) if last_backups else None,
                # A customer with no copy in the last thirty hours is a customer
                # whose nightly job did not run. Said as a COUNT rather than a
                # green tick, because "all fine" over nought customers is not
                # the same sentence as "all fine" over five.
                'stale': len([t for t in live
                              if not t.last_backup_at
                              or t.last_backup_at < datetime.now()
                              - timedelta(hours=30)]),
            },
            'release': self._release_brief(),
            'drift': {
                'tenants': len(live.filtered(
                    lambda t: t.release_state == 'behind'
                    or (t.behind_count or 0) or (t.stale_count or 0))),
                'parts': sum((t.behind_count or 0) + (t.stale_count or 0)
                             for t in live),
            },
            'never': [{'module': n, 'reason': r}
                      for n, r in sorted(common.never_list().items())],
            # Honest when nobody has told the cockpit what this product is.
            'configured': bool(self._apex() and self._template_db()),
        }

    def _brief(self, t):
        """One customer, as the fleet row reads them. All off OUR record."""
        return {
            'id': t.id, 'name': t.name, 'slug': t.slug, 'state': t.state,
            'url': self._tenant_url(t.slug),
            'host': self._tenant_host(t.slug),
            'contact_name': t.contact_name or '',
            'contact_email': t.contact_email or '',
            'release': t.release_id.name or '',
            'release_state': t.release_state or 'unknown',
            'behind_count': t.behind_count or 0,
            'stale_count': t.stale_count or 0,
            'skipped_count': t.skipped_count,
            'health': t.health_state or 'unknown',
            'health_checked_at': self._stamp(t.health_checked_at),
            'size': self._human((t.db_size or 0) + (t.filestore_size or 0)),
            'users': t.user_count or 0,
            'modules': t.module_count or 0,
            'http_status': t.http_status or 0,
            'ping_ms': t.ping_ms,
            'cert_state': t.cert_state or 'none',
            'cert_expires_on': t.cert_expires_on.isoformat()
                               if t.cert_expires_on else '',
            'last_backup': self._stamp(t.last_backup_at),
            'created_on': self._stamp(t.created_on),
            'step': t.provision_step or '',
            'next_step': next_step(t.provision_step),
            'error': t.last_error or '',
            'notice': (t.notice or '').strip(),
            'notice_sent_at': self._stamp(t.notice_sent_at),
        }

    def _release_brief(self):
        rel = self.env['biz.release'].sudo().current()
        if not rel:
            return None
        live = self._tenants().search([('state', '=', 'live')])
        return {
            'id': rel.id, 'name': rel.name,
            'cut_on': self._stamp(rel.cut_on),
            'module_count': rel.module_count,
            'notes': rel.notes or '',
            'on': len(live.filtered(lambda t: t.release_state == 'on')),
            'total': len(live),
        }

    # =====================================================================
    #  2. PROVISIONING — six steps, resumable, each one logged
    # =====================================================================
    @api.model
    def check_slug(self, slug):
        """Answers while somebody types, so it never writes and never raises."""
        self._require_platform_admin()
        taken = set(self._all_databases())
        taken |= set(self._tenants().search([]).mapped('slug'))
        ok, reason = check_slug(
            slug, taken=taken, apex_db=self.env.cr.dbname,
            template_db=self._template_db())
        out = {'ok': ok, 'reason': reason}
        if ok:
            out['url'] = self._tenant_url((slug or '').strip())
        return out

    @api.model
    def provision_preview(self, form):
        """THE DRY RUN. Reads everything, writes nothing, anywhere (rail R1).

        It exists because the alternative is finding out what the six steps
        would have done by watching them do it on a live machine.
        """
        self._require_platform_admin()
        slug = (form.get('slug') or '').strip().lower()
        name = (form.get('name') or '').strip()
        email = (form.get('contact_email') or '').strip().lower()
        problems = []
        chk = self.check_slug(slug)
        if not chk['ok']:
            problems.append(chk['reason'])
        if not name:
            problems.append("Give the customer a name — it is what their "
                            "people will see at the top of every page.")
        if not email or '@' not in email:
            problems.append("An email address is needed: it becomes their "
                            "administrator's sign-in name.")
        template = self._template_db()
        if not template:
            problems.append("Nobody has told this machine which blank system "
                            "new customers are copied from.")
        elif not self._db_exists(template):
            problems.append('There is no blank system called "%s" on this '
                            'machine.' % template)
        # THE DRY RUN ASKS THE SAME QUESTION THE REAL RUN WILL, so that a
        # preview which says "this would work" cannot be followed by a refusal.
        cap = self._capacity()
        if cap['level'] == 'full':
            problems.append(
                "%s Nothing is broken — but there is no room for another "
                "customer until this machine is made bigger "
                "(docs/SAAS_RESIZE_RUNBOOK.md), or the memory one customer is "
                "allowed (the %s setting) is re-weighed."
                % (cap['reason'], common.P_TENANT_COST))
        template_size = self._db_size(template) if template else 0
        fs_size, fs_files = (self._filestore_size(template) if template
                             else (0, 0))
        return {
            'ok': not problems,
            'problems': problems,
            'warnings': ([cap['reason']] if cap['level'] == 'warn' else []),
            'url': self._tenant_url(slug) if slug else '',
            'host': self._tenant_host(slug) if slug else '',
            'plan': [
                {'key': 'clone',
                 'what': 'Copy "%s" (%s of data and %s of attachments in %d '
                         'files) to a new system called "%s".'
                         % (template, self._human(template_size),
                            self._human(fs_size), fs_files, slug)},
                {'key': 'configure',
                 'what': 'Point it at %s, lock that address, give it the '
                         'name "%s", and switch its scheduled jobs back on.'
                         % (self._tenant_url(slug), name)},
                {'key': 'admin',
                 'what': 'Create an administrator called "%s" (%s) with a '
                         'one-time password, and make sure they do NOT hold '
                         'the keys to this machine.'
                         % ((form.get('contact_name') or name), email)},
                {'key': 'https',
                 'what': 'Ask for a certificate for %s so a browser trusts it.'
                         % self._tenant_host(slug)},
                {'key': 'verify',
                 'what': 'Check the address answers, that nothing was skipped, '
                         'and that the administrator can get in.'},
                {'key': 'done',
                 'what': 'Mark them live and show you the address, the sign-in '
                         'name and the password.'},
            ],
            'machine': {'free_mb': cap['mem_available_mb'],
                        'floor_mb': cap['reserve_mb']},
            'capacity': cap,
        }

    @api.model
    def provision_start(self, form):
        """Create the RECORD. Nothing is copied until the first step runs."""
        self._require_platform_admin()
        preview = self.provision_preview(form)
        if not preview['ok']:
            raise UserError('\n\n'.join(preview['problems']))
        tenant = self._tenants().create({
            'name': (form.get('name') or '').strip(),
            'slug': (form.get('slug') or '').strip().lower(),
            'contact_name': (form.get('contact_name') or '').strip(),
            'contact_email': (form.get('contact_email') or '').strip().lower(),
            'note': (form.get('note') or '').strip(),
            'state': 'provisioning',
            'provision_log': '',
            'skipped_count': -1,
        })
        tenant.log('Started. %s will live at %s.'
                   % (tenant.name, self._tenant_url(tenant.slug)))
        return {'tenant_id': tenant.id, 'tenant': self._brief(tenant),
                'steps': [{'key': k, 'label': label}
                          for k, label in PROVISION_STEPS]}

    @api.model
    def provision_run(self, tenant_id, step, preview=False):
        """Run ONE step. Every step is a person pressing a button (rail R1).

        A failure leaves the customer in `error` with the reason ON the record
        and in the log, and the screen then offers exactly two doors: continue
        from here, or undo. There is no third state where somebody has to go and
        look at a machine to find out what happened.
        """
        self._require_platform_admin()
        tenant = self._tenants().browse(int(tenant_id)).exists()
        if not tenant:
            raise UserError(self.env._("That customer is not on the list."))
        if tenant.state not in ('draft', 'provisioning', 'error'):
            raise UserError(self.env._(
                "%s is already set up. This screen only builds new customers.",
                tenant.name))
        step = (step or '').strip()
        if step not in STEP_KEYS:
            raise UserError(self.env._('There is no step called "%s".', step))

        lines = []

        def say(text, level='info'):
            lines.append({'line': text, 'level': level})
            if not preview:
                tenant.log(text, level)
            return text

        if preview:
            say('DRY RUN — nothing below is written.', 'warn')

        t0 = time.time()
        try:
            extra = getattr(self, '_step_%s' % step)(tenant, say, bool(preview))
            if not preview:
                tenant.write({'provision_step': step, 'last_error': False,
                              'state': 'live' if step == 'done'
                                       else 'provisioning'})
            return {
                'ok': True, 'step': step, 'preview': bool(preview),
                'ms': int((time.time() - t0) * 1000), 'log': lines,
                'next': next_step(step) if not preview else step,
                'tenant': self._brief(tenant), **(extra or {}),
            }
        except Exception as e:                               # noqa: BLE001
            _logger.exception("biz_tenants: step %s failed for %s",
                              step, tenant.slug)
            msg = str(e) or e.__class__.__name__
            say('%s — %s' % (step_label(step), msg), 'error')
            if not preview:
                tenant.write({'state': 'error', 'last_error': msg})
            return {'ok': False, 'step': step, 'preview': bool(preview),
                    'error': msg, 'ms': int((time.time() - t0) * 1000),
                    'log': lines, 'next': step,
                    'tenant': self._brief(tenant)}

    # ------------------------------------------------------------- 1. clone
    def _step_clone(self, tenant, say, preview):
        """Copy the blank system, database and attachments together.

        THROUGH THE FRAMEWORK'S OWN COPY ROUTINE, and that is a decision worth
        writing down. It does, in one call and in the right order, every part
        the runbook does by hand:

          * it CLOSES and terminates every connection to the blank system
            first — necessary now that the scheduled-job worker connects to
            every database on the machine;
          * it creates the copy as the ACCOUNT THE APPLICATION CONNECTS AS, so
            the new system is owned by that account. A system owned by anybody
            else is invisible to the application and its address answers a
            redirect to a chooser instead of a sign-in page, with nothing in the
            log to say why (ledger H58). The runbook's `-O odoo` says the same
            thing; this way it cannot be forgotten;
          * it gives the copy a NEW identity rather than the blank system's;
          * and it copies the attachments folder from inside the application's
            own process, whose home folder is the right one — which is the whole
            of ledger F59, obtained by construction rather than by remembering.
        """
        template = self._template_db()
        slug = tenant.slug
        if not template or not self._db_exists(template):
            raise UserError(self.env._(
                'There is no blank system called "%s" on this machine.',
                template or '(not set)'))
        if self._db_exists(slug):
            raise UserError(self.env._(
                'Something on this machine is already called "%s". Remove it '
                'first, or undo this customer and pick another short name.',
                slug))
        # ⚠ THE REAL CAPACITY GUARD, AND IT REPLACED A RAW MEMORY FLOOR. The
        # floor asked "is there 400 MB free" — a fair question with no
        # relationship at all to how much of it another customer would need.
        # This asks the question that matters: is there room for ONE MORE,
        # given what one customer is allowed and what has to stay free for the
        # database and the operating system. It refuses BY NAME and points at
        # the setting and at the one-page resize guide.
        self._capacity_gate()
        say('Copying "%s" to "%s"…' % (template, slug))
        if preview:
            say('Would copy %s of data and %s of attachments.'
                % (self._human(self._db_size(template)),
                   self._human(self._filestore_size(template)[0])), 'warn')
            return {}
        _direct(db_service.exp_duplicate_database)(template, slug)
        owner = self._db_owner(slug)
        size = self._db_size(slug)
        fs_size, fs_files = self._filestore_size(slug)
        if owner and owner != self._db_owner(self.env.cr.dbname):
            # Repaired rather than reported: the symptom is indistinguishable
            # from a routing fault, so leaving it would cost somebody an hour.
            with self._pg_cursor() as cr:
                cr.execute('ALTER DATABASE "%s" OWNER TO "%s"'
                           % (slug, self._db_owner(self.env.cr.dbname)))
            say('Ownership corrected — the copy belonged to the wrong account.',
                'warn')
        say('Copied: %s of data, %s of attachments in %d files.'
            % (self._human(size), self._human(fs_size), fs_files))
        tenant.write({'db_size': size, 'filestore_size': fs_size})
        return {}

    # --------------------------------------------------------- 2. configure
    def _step_configure(self, tenant, say, preview):
        """Its address, its name, its settings, and its scheduled jobs.

        EVERYTHING HERE GOES THROUGH THE DATA LAYER (rail R5), because the
        registry for this new system is already loaded in this process by the
        copy above — a settings row changed behind it in SQL would sit unread
        until something happened to clear the cache.
        """
        slug = tenant.slug
        url = self._tenant_url(slug)
        if preview:
            say('Would set the address to %s and lock it.' % url, 'warn')
            say('Would switch its scheduled jobs back on.', 'warn')
            return {}
        say('Setting its address to %s…' % url)
        with self._tenant_env(slug) as env:
            icp = env['ir.config_parameter'].sudo()
            icp.set_param('web.base.url', url)
            icp.set_param('web.base.url.freeze', 'True')

            # WHO THIS SYSTEM IS. The presence of this setting is how a system
            # knows it is a customer rather than the platform.
            icp.set_param(common.T_SLUG, slug)

            # THE PRODUCT'S NAME, from the platform's own setting so that a
            # customer opens on the brand rather than on a framework word.
            brand = common.brand(self.env)
            if brand:
                icp.set_param('biz_debranding.brand_name', brand)

            # THE TOP BAR. Belt and braces: the blank system already carries
            # both of these, and this sets them again because a blank system
            # that was ever wrong is a blank system every future customer
            # inherits (handover §3.8).
            icp.set_param('biz_access.topbar_mode', 'admin_only')
            home = common.param_row(self.env,
                                    'biz_access.topbar_home_xmlids')
            if home:
                icp.set_param('biz_access.topbar_home_xmlids', home)

            # WHAT THE PLATFORM HAS TO SAY TO THEM, from their first minute.
            for key, value in self._tenancy_values().items():
                icp.set_param(key, value or '')

            # WHICH PARTS OF THE PRODUCT THEY HAVE, from their first minute
            # too. Written here rather than left to the absent-means-on rule,
            # so that the switched-off page can say the part's NAME the very
            # first time somebody meets it rather than a key nobody recognises.
            icp.set_param(common.T_FEATURES,
                          self._feature_settings_value(tenant))
            say('Told them which parts of the product they have.')

            company = env['res.company'].browse(1)
            if company.exists():
                vals = {'name': tenant.name}
                if tenant.contact_email:
                    vals['email'] = tenant.contact_email
                company.write(vals)
                say('Named: %s.' % tenant.name)

            # ⚠ THE LIST OF SCHEDULED JOBS LIVES ON THE BLANK SYSTEM'S OWN
            # SETTINGS, NOT THE MASTER'S (ledger F20) — looking for it here
            # finds nothing and looks exactly like data loss. It came across
            # with the copy, which is why it is read from `icp` (the CLONE's)
            # rather than from the platform's own.
            raw = icp.get_param(common.P_TEMPLATE_CRONS, '')
            ids = [int(x) for x in str(raw).split(',') if x.strip().isdigit()]
            if ids:
                crons = env['ir.cron'].sudo().with_context(
                    active_test=False).browse(ids).exists()
                crons.write({'active': True})
                icp.set_param(common.P_TEMPLATE_CRONS, '')
                say('Switched %d scheduled jobs back on.' % len(crons))
            else:
                say('No scheduled jobs were recorded on the blank system, so '
                    'none were switched on. Check the blank system before the '
                    'next customer.', 'warn')
        return {}

    # ------------------------------------------------------------- 3. admin
    def _step_admin(self, tenant, say, preview):
        """The customer's own administrator. A NEW account, never a reused one.

        THE FINDING THIS SHAPE EXISTS FOR. The obvious thing to do is to take
        the blank system's own administrator account, rename it and switch it
        on. That account carries the keys to the whole machine — the view
        editor, every table's raw rows, the module list, the developer switch —
        so every customer's administrator would hold them, not because anybody
        decided that but because that is what the blank system happened to have.

        So a NEW account is created, given the role the product registered, and
        CHECKED: if it still holds the keys afterwards, nothing is handed over
        at all. A customer told they are restricted when they are not is worse
        than one who was never restricted.

        THE PASSWORD IS SHOWN ONCE AND STORED NOWHERE. Not on our record, not in
        the log, not in an email — this platform has no outgoing mail account,
        and inventing a place to keep a password so that it could be sent later
        would be the wrong answer to that.
        """
        slug = tenant.slug
        login = (tenant.contact_email or '').strip().lower()
        if not login:
            raise UserError(self.env._(
                "This customer has no email address, so there is no sign-in "
                "name to give their administrator."))
        password = generated_password(secrets.token_urlsafe(16))
        spec = common.tenant_admin()
        if preview:
            say('Would create %s as their administrator and give them the '
                '"%s" role.' % (login, spec.get('role_xmlid') or '(none set)'),
                'warn')
            return {}
        with self._tenant_env(slug) as env:
            existing = env['res.users'].sudo().with_context(
                active_test=False).search([('login', '=', login)], limit=1)
            if existing:
                raise UserError(self.env._(
                    'There is already an account called "%s" on their system. '
                    'Undo this customer, or give them a different address.',
                    login))
            group_ids = []
            internal = env.ref('base.group_user', raise_if_not_found=False)
            if internal:
                group_ids.append(internal.id)
            for xmlid in spec.get('group_xmlids') or ():
                group = env.ref(xmlid, raise_if_not_found=False)
                if group:
                    group_ids.append(group.id)
                else:
                    say('The tier "%s" is not on their system, so it was not '
                        'given.' % xmlid, 'warn')
            user = env['res.users'].sudo().create({
                'name': tenant.contact_name or tenant.name,
                'login': login,
                'email': login,
                'password': password,
                'active': True,
                'group_ids': [(6, 0, sorted(set(group_ids)))],
            })
            user.partner_id.sudo().write({'active': True})

            # THE ROLE, GRANTED THROUGH THE ACCESS HOME so that it is AUDITED.
            # Writing the permissions straight onto the account would work and
            # would leave no record of who gave them or when, on the one account
            # where that question is most likely to be asked.
            role_xmlid = spec.get('role_xmlid')
            granted = ''
            if role_xmlid:
                role = env.ref(role_xmlid, raise_if_not_found=False)
                if not role:
                    say('The role "%s" is not on their system, so the '
                        'administrator has a plain login and nothing else. '
                        'Bring them in step and grant it.' % role_xmlid, 'warn')
                else:
                    if 'biz.access' in env:
                        try:
                            env['biz.access'].sudo().grant(
                                role.id, user.id,
                                reason="Given when this customer was created.")
                            granted = role.name
                        except Exception:                    # noqa: BLE001
                            _logger.warning(
                                "biz_tenants: could not record the grant of %s "
                                "on %s", role_xmlid, slug, exc_info=True)
                    if not granted:
                        user.sudo().write({
                            'group_ids': [(4, g.id) for g in role.group_ids]})
                        granted = role.name
                        say('The role was given directly — their access home '
                            'could not record it. The access itself is right; '
                            'only the history line is missing.', 'warn')

            # THE HOME SCREEN. Without one the framework drops somebody into
            # the messaging app on their first sign-in.
            home_xmlid = common.home_action()
            if home_xmlid:
                action = env.ref(home_xmlid, raise_if_not_found=False)
                if action:
                    user.sudo().write({'action_id': action.id})
                else:
                    say('Their home screen was left at the default: "%s" is '
                        'not on their system.' % home_xmlid, 'warn')

            # ⚠ THE ONE ABSOLUTE, CHECKED ON THE WHOLE LADDER AND NOT ON TWO
            # ROWS. A permission can be held THROUGH another one, so "we did
            # not give it" is a different question from "do they hold it".
            user.invalidate_recordset()
            forbidden = set()
            for xmlid in common.PLATFORM_GROUP_XMLIDS:
                group = env.ref(xmlid, raise_if_not_found=False)
                if group:
                    forbidden.add(group.id)
            if forbidden & set(user.sudo().all_group_ids.ids):
                raise UserError(self.env._(
                    "The administrator this would create still holds the keys "
                    "to this machine, so nothing has been handed over. Nobody "
                    "is locked out; the role this product registered carries "
                    "too much."))
            say('Administrator created: %s%s.'
                % (login, (' — %s' % granted) if granted else ''))
        say('The password is shown once, at the end. It is not stored '
            'anywhere and no email was sent.', 'warn')
        return {'credentials': {'url': self._tenant_url(slug),
                                'login': login, 'password': password}}

    # ------------------------------------------------------------- 4. https
    def _step_https(self, tenant, say, preview):
        """Its own certificate, so a browser trusts the address.

        NEVER FATAL ON ITS OWN. Until this runs the address still works — it
        falls through to the shared block and a browser warns about the name.
        A slow certificate authority must not fail an otherwise good customer,
        so a failure here is a warning carrying the EXACT command to run by
        hand, and the customer goes live with the warning on their record.
        """
        host = self._tenant_host(tenant.slug)
        command = 'sudo %s %s %s' % (CERT_SCRIPT, host, tenant.slug)
        if preview:
            say('Would run: %s' % command, 'warn')
            return {}
        if not os.path.exists(CERT_SCRIPT):
            say('The certificate tool is not installed on this machine, so '
                'their address will show a name warning in a browser until '
                'somebody runs: %s' % command, 'warn')
            return {'retry': command}
        say('Asking for a certificate for %s…' % host)
        try:
            proc = subprocess.run(['sudo', '-n', CERT_SCRIPT, host, tenant.slug],
                                  capture_output=True, text=True, timeout=240)
        except subprocess.TimeoutExpired:
            say('The certificate request took too long. Their address works, '
                'but a browser will warn about the name until somebody runs: '
                '%s' % command, 'warn')
            return {'retry': command}
        if proc.returncode == 0:
            say('Certificate issued for %s. It renews itself.' % host)
        else:
            tail = ((proc.stdout or '') + '\n' + (proc.stderr or '')).strip()
            say('The certificate could not be issued (%s). Their address works, '
                'but a browser will warn about the name. Run this by hand and '
                'then press this step again: %s' % (tail[-300:] or 'no reason '
                                                    'given', command), 'warn')
            return {'retry': command}
        return {}

    # ------------------------------------------------------------ 5. verify
    def _step_verify(self, tenant, say, preview):
        """Everything that has to be true before anybody is told the address.

        THIS STEP REFUSES rather than warns, and that is the difference between
        it and the one before it. A certificate can be fixed afterwards; a
        system that does not answer, or that quietly dropped half the product on
        its first load, cannot be handed to anybody.
        """
        slug = tenant.slug
        host = self._tenant_host(slug)
        if preview:
            say('Would check that %s answers, that nothing was skipped, and '
                'that the administrator can get in.' % host, 'warn')
            return {}
        problems = []

        code, ms = self._probe(host)
        if code == 200:
            say('%s answers in %d ms.' % (host, ms))
        else:
            problems.append(
                'Their address answered %s instead of a sign-in page.'
                % (code or 'nothing at all'))

        # ⚠ THE SKIPPED CHECK, AND IT ANSWERS -1 RATHER THAN A GREEN NOUGHT
        # WHEN IT CANNOT TELL (ledger F7). A part of the product that says it
        # is installed and did not load is invisible in every list and shows up
        # weeks later as a scheduled job failing on a name that no longer
        # exists. Twenty-seven parts sat like that for a day once.
        skipped_count, skipped = self._skipped_on(slug)
        if skipped_count > 0:
            problems.append(
                '%d parts of the product say they are installed but did not '
                'load: %s.' % (skipped_count, ', '.join(skipped[:8])))
        elif skipped_count == 0:
            say('Everything installed loaded — nothing was skipped.')
        else:
            say('Whether anything was skipped could not be determined.', 'warn')

        installed = self._installed_on(slug)
        template_installed = self._installed_on(self._template_db()) \
            if self._db_exists(self._template_db()) else {}
        if template_installed and len(installed) != len(template_installed):
            problems.append(
                'They have %d parts of the product and the blank system has '
                '%d.' % (len(installed), len(template_installed)))
        else:
            say('They have all %d parts of the product.' % len(installed))

        with self._pg_cursor(slug) as cr:
            cr.execute("SELECT count(*) FROM res_users "
                       "WHERE active AND share IS NOT TRUE")
            users = cr.fetchone()[0]
        say('%d people can sign in.' % users)

        # The platform link has to be there, or nothing can ever be said to
        # them again.
        if common.TENANCY_MODULE not in installed:
            problems.append(
                'The platform link is not installed on their system, so they '
                'cannot be told anything. Bring them in step first.')
        else:
            say('The platform link is installed — they can be sent messages.')

        # THE ACCESS HOME HAS ITS ROLES. A customer whose roles did not seed is
        # a customer whose administrator can sign in and open nothing.
        with self._pg_cursor(slug) as cr:
            cr.execute("SELECT to_regclass('biz_access_role')")
            if cr.fetchone()[0]:
                cr.execute("SELECT count(*) FROM biz_access_role WHERE active")
                roles = cr.fetchone()[0]
                if roles:
                    say('Their access home has %d roles.' % roles)
                else:
                    problems.append('Their access home has no roles at all.')

        cert = self._read_cert(tenant)
        tenant.write({
            'http_status': code, 'ping_ms': ms,
            'module_count': len(installed), 'user_count': users,
            'skipped_count': skipped_count,
            'db_size': self._db_size(slug),
            'filestore_size': self._filestore_size(slug)[0],
            'health_state': 'ok' if code == 200 and not problems else 'warn',
            'health_checked_at': fields.Datetime.now(),
            **cert,
        })
        if problems:
            raise UserError('\n\n'.join(problems))
        say('Everything answers.')
        return {}

    # -------------------------------------------------------------- 6. done
    def _step_done(self, tenant, say, preview):
        """Mark them live, stamp the release, and write the one summary line."""
        if preview:
            say('Would mark %s live.' % tenant.name, 'warn')
            return {}
        rel = self.env['biz.release'].sudo().current()
        vals = {'state': 'live'}
        if rel:
            vals.update({'release_id': rel.id, 'release_state': 'on'})
        tenant.write(vals)
        self._seed_domain(tenant)
        if rel:
            try:
                self.push_settings(tenant.id, self._release_values(rel))
                say('Told their system it is on release %s.' % rel.name)
            except Exception:                                # noqa: BLE001
                _logger.warning("biz_tenants: could not stamp the release on "
                                "%s", tenant.slug, exc_info=True)
                say('Their system could not be told which release it is on. '
                    'Their About screen catches up next time.', 'warn')
        say('%s is live at %s.' % (tenant.name, self._tenant_url(tenant.slug)))
        return {'url': self._tenant_url(tenant.slug)}

    def _seed_domain(self, tenant):
        """Their one address, written down so the Domains tab has something
        true to show. It is READ-ONLY — see the tab's own sentence."""
        host = self._tenant_host(tenant.slug)
        Domain = self.env['biz.tenant.domain'].sudo()
        if not Domain.search_count([('hostname', '=', host)]):
            Domain.create({'tenant_id': tenant.id, 'hostname': host,
                           'kind': 'platform'})

    # ------------------------------------------------------------ undo / off
    @api.model
    def provision_undo(self, tenant_id, confirm_slug):
        """Take back a half-made customer, completely.

        ONLY WHILE NOBODY HAS SIGNED IN. After that this is not an undo, it is
        a deletion of somebody's work, and it goes through `decommission` —
        which takes a final copy first and cannot be reached without typing the
        customer's short name.
        """
        self._require_platform_admin()
        tenant = self._tenants().browse(int(tenant_id)).exists()
        if not tenant:
            raise UserError(self.env._("That customer is not on the list."))
        if (confirm_slug or '').strip().lower() != tenant.slug:
            raise UserError(self.env._(
                'Type "%s" to confirm.', tenant.slug))
        if tenant.state == 'live' and self._someone_signed_in(tenant.slug):
            raise UserError(self.env._(
                "Somebody has already signed in to %s, so this is no longer an "
                "undo. Close the customer down instead — that takes a final "
                "copy first.", tenant.name))
        removed = []
        if self._db_exists(tenant.slug):
            _direct(db_service.exp_drop)(tenant.slug)
            removed.append('their system')
        self._detach_cert(tenant)
        removed.append('their address')
        tenant.log('Undone: %s removed. Nobody had signed in.'
                   % ' and '.join(removed), 'warn')
        tenant.write({'state': 'draft', 'provision_step': False,
                      'health_state': 'unknown', 'http_status': 0,
                      'module_count': 0, 'user_count': 0,
                      'db_size': 0, 'filestore_size': 0})
        tenant.domain_ids.sudo().unlink()
        return {'ok': True, 'removed': removed}

    def _someone_signed_in(self, dbname):
        """Has anybody but the platform ever signed in to this system?

        Read off the framework's own record of devices that have been seen. A
        system nobody has ever opened is a system that can still be undone.
        """
        try:
            with self._pg_cursor(dbname) as cr:
                cr.execute("SELECT to_regclass('res_device_log')")
                if not cr.fetchone()[0]:
                    return False
                cr.execute("SELECT count(*) FROM res_device_log")
                return bool(cr.fetchone()[0])
        except Exception:                                    # noqa: BLE001
            # If it cannot be answered, assume somebody HAS: the safe direction
            # for a question whose wrong answer deletes a customer's work.
            return True

    def _detach_cert(self, tenant):
        """Take the address's own block and certificate down with the system.

        Best-effort: closing a customer must not fail because the web server's
        housekeeping did. A block that proxies to a database that is gone is
        untidy; a customer who cannot be closed is worse.
        """
        if not os.path.exists(DETACH_SCRIPT):
            return
        host = self._tenant_host(tenant.slug)
        try:
            subprocess.run(['sudo', '-n', DETACH_SCRIPT, host],
                           capture_output=True, text=True, timeout=120)
        except Exception as e:                               # noqa: BLE001
            _logger.warning("biz_tenants: could not detach %s: %s", host, e)

    @api.model
    def decommission(self, tenant_id, confirm_slug):
        """Close a customer down: final copy, address off, system removed.

        THE FINAL COPY IS TAKEN FIRST AND THE WHOLE THING REFUSES IF IT FAILS.
        Everything else here is reversible with that file and irreversible
        without it.
        """
        self._require_platform_admin()
        tenant = self._tenants().browse(int(tenant_id)).exists()
        if not tenant:
            raise UserError(self.env._("That customer is not on the list."))
        if (confirm_slug or '').strip().lower() != tenant.slug:
            raise UserError(self.env._('Type "%s" to confirm.', tenant.slug))
        if tenant.state == 'decommissioned':
            raise UserError(self.env._("%s is already closed.", tenant.name))
        final = None
        if self._db_exists(tenant.slug):
            final = self._take_backup(tenant, 'final')
            if final.state != 'done':
                raise UserError(self.env._(
                    "Refusing to close %s down: the final copy failed (%s). "
                    "Nothing has been removed.",
                    tenant.name, final.note or 'no reason given'))
            staging = '%s-staging' % tenant.slug
            if self._db_exists(staging):
                _direct(db_service.exp_drop)(staging)
            _direct(db_service.exp_drop)(tenant.slug)
        self._detach_cert(tenant)
        tenant.log('Closed down. Final copy kept at %s.'
                   % (final.path if final else '(there was no system)'), 'warn')
        tenant.write({'state': 'decommissioned', 'health_state': 'unknown',
                      'http_status': 0, 'release_state': 'unknown'})
        return {'ok': True,
                'final_backup': final.path if final else '',
                'final_size': self._human(final.size) if final else ''}

    @api.model
    def reopen(self, tenant_id, confirm_slug):
        """Build a closed customer's system again, on their own record.

        ⚠ THE GAP THIS CLOSES, AND IT IS A DEAD END OF EXACTLY THE KIND H73
        FORBIDS. Closing a customer down leaves their record holding their
        short name — which the new-customer screen then refuses, because a
        short name in use is a short name in use. So a customer whose system
        had to be rebuilt (a bad restore, a corrected blank system, a move to
        another machine) could be closed and never re-created, and the only
        way forward was to go and edit the database.

        THE SAME RECORD, NOT A NEW ONE, and that is the important half. Their
        copies — including the final one taken when they were closed — hang off
        this record, and so does every line of their log. A second record with
        the same short name would put a customer's history in two places and
        their address in one.

        It refuses while anything with that name still exists on the machine,
        because that is the one state where "build it again" would mean
        "overwrite what is there".
        """
        self._require_platform_admin()
        tenant = self._tenants().browse(int(tenant_id)).exists()
        if not tenant:
            raise UserError(self.env._("That customer is not on the list."))
        if tenant.state != 'decommissioned':
            raise UserError(self.env._(
                '"%(name)s" has not been closed down (%(state)s), so there is '
                'nothing to build again.',
                name=tenant.name, state=tenant.state))
        if (confirm_slug or '').strip().lower() != tenant.slug:
            raise UserError(self.env._('Type "%s" to confirm.', tenant.slug))
        if self._db_exists(tenant.slug):
            raise UserError(self.env._(
                'Something on this machine is still called "%s". Nothing was '
                'changed — a system with that name has to be gone before '
                'another can take it.', tenant.slug))
        kept = tenant.backup_ids.filtered(lambda b: b.kind == 'final')[:1]
        tenant.log('Being set up again from the blank system. The system they '
                   'had was closed down%s.'
                   % (' and its final copy is kept at %s' % kept.path
                      if kept else ''), 'warn')
        tenant.write({
            'state': 'draft', 'provision_step': '', 'last_error': '',
            'health_state': 'unknown', 'health_detail': '', 'http_status': 0,
            'ping_ms': -1, 'cert_state': 'none', 'cert_expires_on': False,
            'release_id': False, 'release_state': 'unknown',
            'behind_count': 0, 'stale_count': 0, 'skipped_count': -1,
            'db_size': 0, 'filestore_size': 0, 'module_count': 0,
            'user_count': 0,
        })
        return {'ok': True, 'tenant': self._brief(tenant),
                'kept_backup': kept.path if kept else '',
                'message': ("%s is back at the start. Nothing has been copied "
                            "yet — press Create and watch the six steps."
                            % tenant.name)}

    # =====================================================================
    #  3. ONE CUSTOMER — the detail screen and its health reading
    # =====================================================================
    @api.model
    def get_tenant(self, tenant_id):
        self._require_platform_admin()
        t = self._tenants().browse(int(tenant_id)).exists()
        if not t:
            raise UserError(self.env._("That customer is not on the list."))
        staging = '%s-staging' % t.slug
        return {
            **self._brief(t),
            'note': t.note or '',
            'log': t.provision_log or '',
            'db_size_h': self._human(t.db_size),
            'filestore_size_h': self._human(t.filestore_size),
            'health_detail': self._health_detail(t),
            'last_sync_at': self._stamp(t.last_sync_at),
            'last_sync_result': t.last_sync_result or '',
            'signed_in': self._someone_signed_in(t.slug)
                         if self._db_exists(t.slug) else False,
            'staging_db': staging,
            'staging_exists': self._db_exists(staging),
            'backups': [{
                'id': b.id, 'kind': b.kind, 'path': b.path,
                'filestore_path': b.filestore_path or '',
                'size_h': self._human(b.size),
                'filestore_size_h': self._human(b.filestore_size),
                'filestore_files': b.filestore_files,
                'state': b.state, 'note': b.note or '',
                'taken_at': self._stamp(b.taken_at),
            } for b in t.backup_ids],
            'domains': [{
                'id': d.id, 'hostname': d.hostname, 'kind': d.kind,
                'url': 'https://%s' % d.hostname,
            } for d in t.domain_ids],
            # THE ONE SENTENCE THE DOMAINS TAB EXISTS TO SAY. Routing on this
            # machine is by the FIRST WORD of the address, so a customer's own
            # address cannot reach their system until the application can be
            # told which system an address belongs to — and this build cannot.
            # A tool that silently does nothing is worse than one that says no.
            'custom_domains_note': (
                "A customer's own web address does not work yet. Every address "
                "on this machine is routed by its first word, so "
                "booking.theircompany.com would look for a system called "
                "\"booking\". Making it work needs a change to the application "
                "itself. Until then, give them %s — or let them point their own "
                "address at it as a forward." % self._tenant_url(t.slug)),
            'meters': self.read_meters(t.id),
        }

    def _health_detail(self, t):
        try:
            data = json.loads(t.health_detail or '{}')
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    @api.model
    def refresh_health(self, tenant_id=None):
        """Read one customer, or all of them. WRITES ONLY OUR OWN RECORD."""
        self._require_platform_admin()
        domain = ([('id', '=', int(tenant_id))] if tenant_id
                  else [('state', 'in', ('live', 'provisioning', 'error'))])
        for t in self._tenants().search(domain):
            self._read_health(t)
        return (self.get_tenant(tenant_id) if tenant_id else self.get_fleet())

    def _read_health(self, t):
        """One customer's health, as SQL plus one request. Never raises.

        EVERY PROBE HAS ITS OWN GUARD. They used to share one, so the first
        schema difference silently zeroed everything after it and every
        customer reported nought staff.
        """
        slug = t.slug
        detail = {'read_at': fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        vals = {'health_checked_at': fields.Datetime.now()}
        if not self._db_exists(slug):
            t.write({**vals, 'health_state': 'unknown',
                     'health_detail': json.dumps(
                         {**detail, 'reason': 'There is no system with that '
                                              'name on this machine.'})})
            return
        vals['db_size'] = self._db_size(slug)
        fs_size, fs_files = self._filestore_size(slug)
        vals['filestore_size'] = fs_size
        detail['filestore_files'] = fs_files
        detail['owner'] = self._db_owner(slug)

        try:
            installed = self._installed_on(slug)
            vals['module_count'] = len(installed)
        except Exception as e:                               # noqa: BLE001
            detail['modules_error'] = str(e)
        skipped_count, skipped = self._skipped_on(slug)
        vals['skipped_count'] = skipped_count
        detail['skipped'] = skipped

        try:
            with self._pg_cursor(slug) as cr:
                for key, table, sql in (
                        ('users', None,
                         "SELECT count(*) FROM res_users "
                         "WHERE active AND share IS NOT TRUE"),
                        ('failing_jobs', 'ir_cron',
                         "SELECT count(*) FROM ir_cron "
                         "WHERE active AND nextcall < now() - interval '1 day'"),
                        ('last_seen', 'res_device_log',
                         "SELECT max(last_activity) FROM res_device_log")):
                    try:
                        if table:
                            cr.execute("SELECT to_regclass(%s)", (table,))
                            if not cr.fetchone()[0]:
                                continue
                        cr.execute(sql)
                        detail[key] = cr.fetchone()[0]
                    except Exception as e:                   # noqa: BLE001
                        _logger.warning("biz_tenants: %s failed on %s: %s",
                                        key, slug, e)
                        detail['%s_error' % key] = str(e)
        except Exception as e:                               # noqa: BLE001
            detail['sql_error'] = str(e)
        if detail.get('users') is not None:
            vals['user_count'] = detail['users'] or 0
        if detail.get('last_seen'):
            detail['last_seen'] = str(detail['last_seen'])[:19]

        code, ms = self._probe(self._tenant_host(slug))
        vals['http_status'], vals['ping_ms'] = code, ms
        vals.update(self._read_cert(t))

        errors = self._log_errors(slug)
        detail['errors'] = errors['errors'][-8:]
        detail['error_count'] = len(errors['errors'])
        detail['ignored_count'] = len(errors['ignored'])

        stale = (not t.last_backup_at
                 or t.last_backup_at < datetime.now() - timedelta(hours=48))
        detail['backup_stale'] = stale
        if code != 200:
            vals['health_state'] = 'down'
        elif (skipped_count > 0 or errors['errors'] or stale or ms > 3000
              or (detail.get('failing_jobs') or 0) > 0):
            vals['health_state'] = 'warn'
        else:
            vals['health_state'] = 'ok'
        vals['health_detail'] = json.dumps(detail, default=str)
        t.write(vals)

    def _read_cert(self, t):
        """What a browser is actually handed for this customer's address."""
        host = self._tenant_host(t.slug)
        info = self._peer_cert(host)
        if not info['text']:
            return {'cert_state': 'none', 'cert_expires_on': False}
        own = ('CN=%s' % host) in info['text'] or ('DNS:%s' % host) in info['text']
        return {'cert_state': 'own' if own else 'shared',
                'cert_expires_on': info['expires'] or False}

    def _log_errors(self, dbname, since=None):
        """This customer's own error lines, out of the last part of the log.

        THE TAIL AND NOT THE FILE (ledger F27). And the ignore list is applied
        HERE, with the ignored lines still counted and still returned, because
        a gate that cries wolf on every load teaches the owner to click past it
        — and one that hides what it ignored cannot be checked.
        """
        since = since or (datetime.utcnow() - timedelta(hours=24)).strftime(
            '%Y-%m-%d %H:%M:%S')
        try:
            size = os.path.getsize(LOG_PATH)
            with open(LOG_PATH, 'r', encoding='utf-8', errors='replace') as fh:
                if size > LOG_TAIL_BYTES:
                    fh.seek(size - LOG_TAIL_BYTES)
                    fh.readline()          # drop the half line we landed in
                lines = fh.readlines()
        except OSError:
            return {'errors': [], 'ignored': []}
        return log_lines_of_interest(lines, dbname, since,
                                     common.health_ignore(self.env))

    # =====================================================================
    #  4. BACKUPS AND THE PRACTICE COPY
    # =====================================================================
    @api.model
    def backup_now(self, tenant_id, kind='manual'):
        self._require_platform_admin()
        t = self._tenants().browse(int(tenant_id)).exists()
        if not t or not self._db_exists(t.slug):
            raise UserError(self.env._(
                "There is no system to copy for this customer."))
        rec = self._take_backup(t, kind if kind in ('manual', 'nightly',
                                                    'final') else 'manual')
        if rec.state != 'done':
            raise UserError(self.env._("The copy failed: %s",
                                       rec.note or 'no reason given'))
        return self.get_tenant(tenant_id)

    def _take_backup(self, t, kind):
        """The database AND the attachments, and BOTH sizes checked.

        ⚠ A BACKUP TAKEN WITH THE WRONG HOME FOLDER CONTAINS NO ATTACHMENTS AND
        STILL SAYS "DONE" (ledger F59). There is no data folder in the
        configuration, so the attachments live under the running account's home
        — and anything started with a different one reads a DIFFERENT, EMPTY
        folder. A 9 MB archive with five files in it once sat beside a real one
        of 219 MB with 1,280 and was recorded as good.

        This runs inside the application's own process, whose home folder is
        the right one BY CONSTRUCTION. And it is checked anyway: a suspiciously
        small attachments archive FAILS the backup and the files are removed,
        rather than being written down as something somebody could rely on.
        """
        Backup = self.env['biz.tenant.backup'].sudo()
        root = os.path.join(self._backup_root(), t.slug)
        stamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        dump_path = os.path.join(root, '%s_%s_%s.dump' % (t.slug, kind, stamp))
        fs_path = os.path.join(root, '%s_%s_%s.filestore.tar.gz'
                                     % (t.slug, kind, stamp))
        try:
            os.makedirs(root, exist_ok=True)
            proc = subprocess.run(
                ['pg_dump', '-Fc', '-Z1', '-d', t.slug, '-f', dump_path],
                capture_output=True, text=True, timeout=3600)
            if proc.returncode != 0:
                raise RuntimeError((proc.stderr or 'pg_dump failed')[-300:])
            src = self._filestore_path(t.slug)
            files = 0
            with tarfile.open(fs_path, 'w:gz') as tar:
                if os.path.isdir(src):
                    tar.add(src, arcname='filestore')
                    for _root, _dirs, names in os.walk(src):
                        files += len(names)
            dump_size = os.path.getsize(dump_path)
            fs_size = os.path.getsize(fs_path)
            ok, reason = backup_verdict(dump_size, fs_size, files)
            if not ok:
                for path in (dump_path, fs_path):
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
                t.log('Copy REFUSED: %s' % reason, 'error')
                return Backup.create({
                    'tenant_id': t.id, 'kind': kind, 'path': dump_path,
                    'state': 'failed', 'note': reason[:500]})
            rec = Backup.create({
                'tenant_id': t.id, 'kind': kind, 'path': dump_path,
                'filestore_path': fs_path, 'size': dump_size,
                'filestore_size': fs_size, 'filestore_files': files,
                'state': 'done'})
            t.write({'last_backup_at': fields.Datetime.now()})
            t.log('Copy kept: %s of data and %s of attachments in %d files.'
                  % (self._human(dump_size), self._human(fs_size), files))
            self._prune_nightly(t)
            return rec
        except Exception as e:                               # noqa: BLE001
            _logger.exception("biz_tenants: backup failed for %s", t.slug)
            for path in (dump_path, fs_path):
                try:
                    if os.path.exists(path):
                        os.unlink(path)
                except OSError:
                    pass
            t.log('Copy failed: %s' % e, 'error')
            return Backup.create({
                'tenant_id': t.id, 'kind': kind, 'path': dump_path,
                'state': 'failed', 'note': str(e)[:500]})

    def _prune_nightly(self, t):
        """Keep the last fourteen nightly copies. Taken-by-hand and final ones
        are kept for ever — somebody took those on purpose."""
        rows = self.env['biz.tenant.backup'].sudo().search(
            [('tenant_id', '=', t.id), ('kind', '=', 'nightly'),
             ('state', '=', 'done')], order='taken_at desc')
        for old in rows[NIGHTLY_KEEP:]:
            for path in (old.path, old.filestore_path):
                try:
                    if path and os.path.exists(path):
                        os.unlink(path)
                except OSError:
                    pass
            old.unlink()

    @api.model
    def restore_to_staging(self, tenant_id, backup_id=None):
        """Put a copy back, into a PRACTICE system, to prove it is good.

        ⚠ THE RESTORE BELONGS INSIDE THE TRY WHOSE FINALLY DROPS THE COPY
        (ledger F26). Outside it, a damaged file leaves a half-restored database
        sitting on a machine with 2 GB of memory — which is the one outcome this
        whole method exists to make impossible.

        AND IT REFUSES IF A PRACTICE COPY IS ALREADY THERE. Two people
        rehearsing on one name destroy each other's work, and the second one
        finds out by watching the first one's restore fail.
        """
        self._require_platform_admin()
        t = self._tenants().browse(int(tenant_id)).exists()
        if not t:
            raise UserError(self.env._("That customer is not on the list."))
        Backup = self.env['biz.tenant.backup'].sudo()
        rec = (Backup.browse(int(backup_id)).exists() if backup_id
               else Backup.search([('tenant_id', '=', t.id),
                                   ('state', '=', 'done')], limit=1))
        if not rec or not rec.path or not os.path.exists(rec.path):
            raise UserError(self.env._(
                "There is no copy of %s on this machine to put back.", t.name))
        staging = '%s-staging' % t.slug
        if self._db_exists(staging):
            raise UserError(self.env._(
                'There is already a practice copy called "%s". Remove that one '
                'first — two people rehearsing on one name destroy each '
                "other's work.", staging))
        kept = False
        try:
            with self._pg_cursor() as cr:
                cr.execute('CREATE DATABASE "%s"' % staging)
            proc = subprocess.run(
                ['pg_restore', '--no-owner', '-d', staging, rec.path],
                capture_output=True, text=True, timeout=3600)
            # pg_restore returns non-zero for warnings as well as failures, so
            # the test is "did the tables arrive", not "was the exit code nought".
            with self._pg_cursor(staging) as cr:
                cr.execute("SELECT to_regclass('ir_module_module')")
                if not cr.fetchone()[0]:
                    raise RuntimeError(
                        (proc.stderr or 'the copy did not restore')[-400:])
            if rec.filestore_path and os.path.exists(rec.filestore_path):
                dest = self._filestore_path(staging)
                if os.path.exists(dest):
                    shutil.rmtree(dest, ignore_errors=True)
                with tempfile.TemporaryDirectory() as tmp:
                    with tarfile.open(rec.filestore_path, 'r:gz') as tar:
                        tar.extractall(tmp)
                    src = os.path.join(tmp, 'filestore')
                    if os.path.isdir(src):
                        shutil.copytree(src, dest)
            with self._pg_cursor(staging) as cr:
                cr.execute("UPDATE ir_config_parameter SET value = %s "
                           "WHERE key = 'web.base.url'",
                           (self._tenant_url(staging),))
                # A practice copy must never send anything to anybody.
                cr.execute("UPDATE ir_cron SET active = false")
            kept = True
            t.log('Practice copy "%s" restored from %s.'
                  % (staging, os.path.basename(rec.path)))
            return {'ok': True, 'staging_db': staging,
                    'from_backup': os.path.basename(rec.path),
                    'note': "Its scheduled jobs are switched off and it sends "
                            "nothing to anybody. Remove it when you are done — "
                            "every extra system on this machine costs memory."}
        finally:
            if not kept and self._db_exists(staging):
                _direct(db_service.exp_drop)(staging)

    @api.model
    def drop_staging(self, tenant_id):
        self._require_platform_admin()
        t = self._tenants().browse(int(tenant_id)).exists()
        staging = '%s-staging' % t.slug
        if self._db_exists(staging):
            _direct(db_service.exp_drop)(staging)
            t.log('Practice copy "%s" removed.' % staging)
        return self.get_tenant(tenant_id)

    # =====================================================================
    #  5. IN STEP WITH THE MASTER
    # =====================================================================
    #: The blank system is not a customer and has no record of its own — but it
    #: is what every future customer is copied from, so a blank system that is
    #: behind hands its arrears to everybody who arrives after it. It gets a row
    #: on the same screen under this key.
    TEMPLATE_KEY = 'template'

    def _installed_on(self, dbname):
        """What another system has installed, and at what version. SQL, READ.

        The value is the version THAT SYSTEM has applied — not the version of
        the file on the machine, which every system shares. The two differ, and
        the difference is the whole subject of this screen (F1/F2/F8).
        """
        with self._pg_cursor(dbname) as cr:
            cr.execute("SELECT name, coalesce(latest_version, '') "
                       "FROM ir_module_module WHERE state = 'installed'")
            return {r[0]: r[1] for r in cr.fetchall()}

    def _skipped_on(self, dbname):
        """Parts a system claims to have, which it did not actually load.

        THE SILENT FAILURE THIS CATCHES. When a part of the product gains a
        dependency a system has never heard of, that system quietly drops the
        whole family on its next start: the rows still read "installed", the log
        says everything loaded, and the only loud symptom is a scheduled job
        failing weeks later on a name that no longer exists.

        The framework keeps the set a registry really loaded, so the answer is
        that set subtracted from what the database says it has.

        Returns `(count, names)`, and count is **-1** when there is nothing to
        compare against. An honest "could not tell" beats a green nought
        (ledger F7).
        """
        try:
            installed = set(self._installed_on(dbname))
        except Exception:                                    # noqa: BLE001
            return -1, []
        try:
            loaded = set(getattr(Registry(dbname), '_init_modules', None) or ())
        except Exception:                                    # noqa: BLE001
            _logger.warning("biz_tenants: could not read what %s loaded",
                            dbname, exc_info=True)
            return -1, []
        if not loaded:
            return -1, []
        missing = sorted(installed - loaded)
        return len(missing), missing

    def _master_modules(self):
        """What the master has, and what its own files say it should have.

        `have` is what this database has applied; `file` is what is on the
        machine's disk. When `file` is newer the master is running a mixture of
        old data and new code, and rail R3 stops everything until somebody
        applies it.
        """
        out = {}
        for m in self.env['ir.module.module'].sudo().search(
                [('state', '=', 'installed')]):
            out[m.name] = {'label': m.shortdesc or m.name,
                           'have': m.latest_version or '',
                           'file': m.installed_version or ''}
        return out

    def _labels(self, master):
        return {n: d['label'] for n, d in master.items()}

    def _decorate(self, items, master):
        out = []
        for item in items or ():
            if isinstance(item, dict):
                row = dict(item)
                row['label'] = master.get(row['module'], {}).get(
                    'label', row['module'])
                out.append(row)
            else:
                out.append({'module': item,
                            'label': master.get(item, {}).get('label', item)})
        return out

    def _targets(self, master):
        """What everybody is measured against, and where it came from.

        A cut release if there is one — a frozen photograph, so that a fix
        applied to the master at 11:00 does not put every customer "behind" at
        11:01 through nobody's decision. The live master otherwise, and the
        screen says so and invites somebody to cut one.
        """
        rel = self.env['biz.release'].sudo().current()
        if rel:
            snap = rel.fingerprint()
            if snap:
                return snap, rel
        return ({n: d['have'] for n, d in master.items()},
                self.env['biz.release'].sudo().browse())

    # ---------------------------------------------------------------------
    #  WHAT A CUSTOMER IS MADE OF
    #
    #  Computed from the product's own dependencies, never listed by hand
    #  (`module_set.py` holds the rule). Read here, judged there.
    # ---------------------------------------------------------------------
    def _manifests(self):
        """Every module this database has heard of, and what it declares.

        READ FROM `ir.module.module`, NOT FROM DISK, and the reason is the one
        thing that would otherwise be lost: the framework stores `auto_install`
        as a plain boolean on the module and marks WHICH dependencies are the
        triggers on the dependency row (`auto_install_required`). A module whose
        manifest says `auto_install = ['sale_management', 'project_account']`
        therefore survives the round trip exactly, which reading the boolean
        alone would not.
        """
        out = {}
        Dep = self.env['ir.module.module.dependency'].sudo()
        deps = {}
        for d in Dep.search([]):
            deps.setdefault(d.module_id.id, []).append(
                (d.name, bool(d.auto_install_required)))
        for m in self.env['ir.module.module'].sudo().search([]):
            rows = deps.get(m.id, [])
            triggers = [n for n, req in rows if req]
            out[m.name] = {
                'depends': [n for n, _r in rows],
                'auto_install': (triggers or True) if m.auto_install else False,
            }
        return out

    def _module_set(self, master=None):
        """The answer, computed. No screen vocabulary, no guards."""
        master = master if master is not None else self._master_modules()
        return customer_module_set(sorted(master), self._manifests())

    @api.model
    def module_set_report(self):
        """What a customer's system is made of, and what is held back.

        The "In step with master" screen's own first question, answered from
        the product's dependencies rather than from anybody's memory. Every
        held-back row carries its plain reason, which is what makes this a
        screen somebody can argue with rather than a number to take on trust.
        """
        self._require_platform_admin()
        master = self._master_modules()
        answer = self._module_set(master)
        labels = self._labels(master)
        return {
            'total': len(answer['modules']),
            'master_total': len(master),
            'seeds': len(answer['seeds']),
            'prefixes': list(mset.product_prefixes()),
            'extras': [{'module': n, 'label': labels.get(n, n)}
                       for n in sorted(mset.extras())],
            'followers': [
                {'module': n, 'label': labels.get(n, n),
                 'because': ', '.join(sorted(t))}
                for n, t in sorted(answer['followers'].items())],
            'held_back': module_set_rows(answer, labels),
            'conflicts': [
                {**c, 'label': labels.get(c['module'], c['module'])}
                for c in answer['conflicts']],
        }

    @api.model
    def sync_report(self):
        """Where everybody stands against the master. READ ONLY, everywhere."""
        self._require_platform_admin()
        master = self._master_modules()
        behind_files = master_behind_files(
            [(n, d['have'], d['file']) for n, d in master.items()])
        targets, rel = self._targets(master)
        rows = []
        template = self._template_db()
        if template:
            rows.append(self._sync_row(template, master, targets,
                                       key=self.TEMPLATE_KEY,
                                       name="The blank system new customers "
                                            "are copied from",
                                       slug=template, is_template=True))
        for t in self._tenants().search([]):
            rows.append(self._sync_row(t.slug, master, targets, key=str(t.id),
                                       name=t.name, slug=t.slug, tenant=t))
        measured = [r for r in rows if r['checked']]
        return {
            'master_db': self.env.cr.dbname,
            'master_count': len(master),
            'master_behind_files': self._decorate(behind_files, master),
            'release': ({'id': rel.id, 'name': rel.name,
                         'cut_on': self._stamp(rel.cut_on),
                         'module_count': rel.module_count,
                         'notes': rel.notes or '',
                         'cut_by': rel.cut_by.name or ''} if rel else None),
            'on_release': len([r for r in measured
                               if r['release_state'] == 'on']),
            'measured': len(measured),
            'drift_total': sum(r['behind_count'] + r['stale_count']
                               for r in measured),
            'never': [{'module': n, 'label': master.get(n, {}).get('label', n),
                       'reason': r}
                      for n, r in sorted(common.never_list().items())],
            # WHAT A CUSTOMER IS MADE OF, on the same screen as what they are
            # missing — because the second question is meaningless without the
            # first. Computed here rather than fetched separately so the two
            # halves of the screen can never disagree about the same master.
            'module_set': self.module_set_report(),
            'rows': rows,
            # SAID ON THE SCREEN, in these words, so nobody has to read a
            # comment to know it: nothing installs on a schedule, ever.
            'schedule_note': (
                "Nothing is ever installed on a customer's system by a "
                "schedule. The nightly check only READS, so this screen is "
                "true in the morning; a person presses the button."),
        }

    def _sync_row(self, dbname, master, targets, *, key, name, slug,
                  is_template=False, tenant=None):
        row = {
            'key': key, 'name': name, 'slug': slug, 'database': dbname,
            'is_template': is_template,
            'id': tenant.id if tenant else 0,
            'state': tenant.state if tenant else 'template',
            'checked': False, 'error': '', 'installed': 0,
            'to_install': [], 'to_update': [], 'held_back': [], 'ahead': [],
            'in_step': False, 'release_state': 'unknown',
            'release': (tenant.release_id.name if tenant and tenant.release_id
                        else ''),
            'behind_count': 0, 'stale_count': 0,
            'skipped_count': tenant.skipped_count if tenant else -1,
            'drift_checked': self._stamp(tenant.drift_checked) if tenant else None,
            'last_sync_at': self._stamp(tenant.last_sync_at) if tenant else None,
        }
        if tenant is not None and tenant.state == 'decommissioned':
            row['error'] = "This customer has been closed down."
            return row
        if not self._db_exists(dbname):
            row['error'] = "There is no system for this one yet."
            return row
        try:
            have = self._installed_on(dbname)
        except Exception as e:                               # noqa: BLE001
            row['error'] = "This system could not be read: %s" % e
            return row
        diff = sync_diff({n: d['have'] for n, d in master.items()}, have)
        row.update({
            'checked': True, 'installed': len(have),
            'to_install': self._decorate(diff['to_install'], master),
            'to_update': self._decorate(diff['to_update'], master),
            'held_back': held_back_rows(diff['held_back'], self._labels(master)),
            'ahead': self._decorate(diff['ahead'], master),
            'behind_count': len(diff['to_install']),
            'stale_count': len(diff['to_update']),
            'in_step': not diff['to_install'] and not diff['to_update'],
            'release_state': release_state(targets, have),
        })
        return row

    def _resolve_target(self, target):
        """Which system is the button pointing at, and may it be pointed there?

        THREE ANSWERS AND NOTHING ELSE (ledger F12): the blank system, ONE
        customer, or a `<customer>-staging` practice copy. The practice copy is
        the only reason a bare name is accepted at all — it is the rehearsal
        door — and it is accepted ONLY when the stem is a real customer.
        """
        Tenant = self._tenants()
        if isinstance(target, str) and target.strip().isdigit():
            target = int(target.strip())
        if isinstance(target, int) and not isinstance(target, bool):
            t = Tenant.browse(target).exists()
            if not t:
                raise UserError(self.env._(
                    "That customer is not on the list any more."))
            return t.slug, t.name, t, False
        name = (target or '').strip()
        if not name:
            raise UserError(self.env._("Which system?"))
        if name == self.env.cr.dbname:
            raise UserError(self.env._(
                "This is the platform's own system. It is where the parts come "
                "FROM — it is never a place to bring them to."))
        if name in (self.TEMPLATE_KEY, self._template_db()):
            return (self._template_db(),
                    "The blank system new customers are copied from",
                    None, True)
        if name.endswith('-staging'):
            stem = name[:-len('-staging')]
            t = Tenant.search([('slug', '=', stem)], limit=1)
            if t:
                return name, "%s (practice copy)" % t.name, None, False
        raise UserError(self.env._(
            'There is nothing here called "%s". This button works on the blank '
            'system, on one customer, or on a customer\'s practice copy — and '
            'on nothing else.', name))

    @api.model
    def sync_bring_in_step(self, target, dry_run=True):
        """Bring ONE system up to what the master runs. The whole unit.

        The order is the one the runbook proved out, with the checks it learned
        the hard way:

          1. refuse the master itself, a closed customer, and — above all — a
             master that has not applied its own files yet (rail R3);
          2. refresh the target's list of available parts, because a part that
             gained a dependency the target has never heard of cannot install
             (ledger F3), and NEVER by upgrading `base`, which would run every
             migration in the product on somebody's live system;
          3. install what is missing;
          4. update what is older;
          5. ask the access home to re-read its catalogue, because one seeded
             by an install hook only ever saw the modules that loaded BEFORE it
             (ACCESS H1);
          6. check that nothing was quietly skipped;
          7. on the blank system only, switch its scheduled jobs back off —
             an install switches them ON (ledger F9);
          8. read the versions back and write down where this system stands.

        A dry run does every read and none of the writes, anywhere.
        """
        self._require_platform_admin()
        dbname, label, tenant, is_template = self._resolve_target(target)
        dry_run = bool(dry_run)
        master = self._master_modules()
        behind_files = master_behind_files(
            [(n, d['have'], d['file']) for n, d in master.items()])
        targets, rel = self._targets(master)
        log = []

        def say(text, level='info'):
            log.append({'line': text, 'level': level})
            _logger.info("biz_tenants sync[%s]: %s", dbname, text)
            if tenant is not None and not dry_run:
                tenant.log(text, level)
            return text

        plan = {
            'target': str(target), 'database': dbname, 'label': label,
            'is_template': is_template, 'dry_run': dry_run,
            'master_behind_files': self._decorate(behind_files, master),
            'installed_before': 0, 'installed_after': 0,
            'to_install': [], 'to_update': [], 'held_back': [], 'ahead': [],
            'installed': [], 'updated': [], 'still_missing': [],
            'still_stale': [], 'skipped': [], 'skipped_count': -1,
            'crons_disabled': 0, 'release_state': 'unknown',
            'release': rel.name if rel else '', 'log': log, 'message': '',
        }

        # ---- 1. the refusals --------------------------------------------
        if dbname == self.env.cr.dbname:
            raise UserError(self.env._(
                "This is the platform's own system. It is where the parts come "
                "FROM — it is never a place to bring them to."))
        if tenant is not None and tenant.state == 'decommissioned':
            raise UserError(self.env._(
                '"%s" has been closed down. Nothing is installed on a system '
                'that is on its way out.', tenant.name))
        if not self._db_exists(dbname):
            raise UserError(self.env._(
                'There is no system called "%s".', dbname))
        if behind_files:
            raise UserError(self.env._(
                "The master has not caught up with its own files yet — %(n)s "
                "parts are waiting, starting with %(first)s. Until the master "
                "runs what it is holding, nothing can be sent out from it.",
                n=len(behind_files), first=behind_files[0]))

        have = self._installed_on(dbname)
        diff = sync_diff({n: d['have'] for n, d in master.items()}, have)
        to_install = list(diff['to_install'])
        to_update = [r['module'] for r in diff['to_update']]
        plan.update({
            'installed_before': len(have), 'installed_after': len(have),
            'to_install': self._decorate(to_install, master),
            'to_update': self._decorate(diff['to_update'], master),
            'held_back': held_back_rows(diff['held_back'], self._labels(master)),
            'ahead': self._decorate(diff['ahead'], master),
        })

        # ⚠ THE LAST GUARD, AND IT IS DELIBERATELY THE THIRD (rail R2).
        # `sync_diff` already took the exceptions out; this re-asks the question
        # of the EXACT LISTS ABOUT TO BE WRITTEN, because those lists are what
        # actually run and every earlier check is a check of something else.
        blocked = [n for n in to_install + to_update if common.is_never(n)]
        if blocked:
            raise UserError(self.env._(
                "Refusing to put %s onto a customer's system.",
                ', '.join(sorted(blocked))))

        if not to_install and not to_update:
            plan['release_state'] = release_state(targets, have)
            if not dry_run:
                plan['skipped_count'], plan['skipped'] = self._skipped_on(dbname)
                if tenant is not None:
                    self._write_standing(tenant, dbname, master, targets, rel,
                                         plan)
                self._push_release_stamp(target, plan, rel, say)
            plan['message'] = ("This system already has everything the master "
                               "has, at the same versions.")
            return plan

        if dry_run:
            bits = []
            if to_install:
                bits.append("%d to add" % len(to_install))
            if to_update:
                bits.append("%d to bring to a newer version, and anything that "
                            "depends on them" % len(to_update))
            plan['message'] = "%s. Nothing has been changed." % ', '.join(bits)
            return plan

        # ---- 2. refresh what this system knows about ---------------------
        say("Refreshing the list of available parts on %s…" % dbname)
        with self._tenant_env(dbname) as env:
            env['ir.module.module'].sudo().update_list()
        say("List refreshed.")

        # ---- 3. install --------------------------------------------------
        if to_install:
            with self._tenant_env(dbname) as env:
                mods = env['ir.module.module'].sudo().search(
                    [('name', 'in', to_install)])
                missing = set(to_install) - set(mods.mapped('name'))
                if missing:
                    raise UserError(self.env._(
                        '"%(db)s" has never heard of %(mods)s, even after '
                        'refreshing its list.',
                        db=dbname, mods=', '.join(sorted(missing))))
                say("Adding %d parts…" % len(to_install))
                mods.button_immediate_install()
            # That call rebuilds the system's registry and closes the
            # environment above with it, so everything after this asks for a
            # fresh one (ledger F4).
            say("Added.")

        # ---- 4. update ---------------------------------------------------
        if to_update:
            with self._tenant_env(dbname) as env:
                mods = env['ir.module.module'].sudo().search(
                    [('name', 'in', to_update), ('state', '=', 'installed')])
                if mods:
                    say("Bringing %d parts to the master's version…" % len(mods))
                    mods.button_immediate_upgrade()
            say("Versions matched.")

        # ---- 5. the access catalogue -------------------------------------
        with self._tenant_env(dbname) as env:
            if 'biz.access' in env:
                try:
                    env['biz.access'].sudo().reseed_catalogue()
                    say("Who-can-do-what list re-read.")
                except Exception:                            # noqa: BLE001
                    _logger.warning("biz_tenants: catalogue re-read failed on "
                                    "%s", dbname, exc_info=True)
                    say("The who-can-do-what list could not be re-read. Open "
                        "the access home on that system and press Re-read.",
                        'warn')

        # ---- 6. was anything skipped? ------------------------------------
        plan['skipped_count'], plan['skipped'] = self._skipped_on(dbname)
        if plan['skipped_count'] > 0:
            say("%d parts say they are installed but did not load: %s"
                % (plan['skipped_count'], ', '.join(plan['skipped'][:8])),
                'error')
        elif plan['skipped_count'] == 0:
            say("Everything installed loaded — nothing was skipped.")
        else:
            say("Whether anything was skipped could not be determined.", 'warn')

        # ---- 7. the blank system's jobs go back off ----------------------
        if is_template:
            plan['crons_disabled'] = self._quiet_template(dbname, say)

        # ---- 8. read it back and write down where it stands --------------
        after = self._installed_on(dbname)
        after_diff = sync_diff({n: d['have'] for n, d in master.items()}, after)
        plan.update({
            'installed_after': len(after),
            'installed': self._decorate(
                sorted(set(to_install) & set(after)), master),
            'updated': self._decorate(
                sorted(n for n in to_update
                       if n in after
                       and norm_version(after[n])
                       >= norm_version(master[n]['have'])), master),
            'still_missing': self._decorate(after_diff['to_install'], master),
            'still_stale': self._decorate(after_diff['to_update'], master),
            'release_state': release_state(targets, after),
        })
        plan['message'] = "%d added, %d brought up to date. %s" % (
            len(plan['installed']), len(plan['updated']),
            "Nothing was skipped." if plan['skipped_count'] == 0
            else ("%d did not load — see below." % plan['skipped_count'])
            if plan['skipped_count'] > 0
            else "The skipped check could not be run.")
        say(plan['message'])

        if tenant is not None:
            self._write_standing(tenant, dbname, master, targets, rel, plan)
            try:
                self._read_health(tenant)
            except Exception:                                # noqa: BLE001
                _logger.warning("biz_tenants: health read after sync failed "
                                "for %s", dbname, exc_info=True)
        self._push_release_stamp(target, plan, rel, say)
        return plan

    def _quiet_template(self, dbname, say):
        """Switch the blank system's scheduled jobs off and record what was on.

        ⚠ RUN AFTER EVERY TOUCH OF IT (ledger F9): installing or upgrading
        anything creates its jobs switched ON, so this is not a build-time chore.
        """
        with self._tenant_env(dbname) as env:
            crons = env['ir.cron'].sudo().with_context(
                active_test=False).search([('active', '=', True)])
            icp = env['ir.config_parameter'].sudo()
            to_disable, new_param = template_cron_plan(
                crons.ids, icp.get_param(common.P_TEMPLATE_CRONS, ''))
            if to_disable:
                env['ir.cron'].sudo().browse(to_disable).write({'active': False})
            icp.set_param(common.P_TEMPLATE_CRONS, new_param)
        say("%d scheduled jobs switched back off on the blank system. A new "
            "customer gets them back when they are created." % len(to_disable))
        return len(to_disable)

    @api.model
    def template_quiet_now(self):
        """The same, on its own button. Run after any upgrade of the blank
        system, which is exactly when it is needed and never remembered."""
        self._require_platform_admin()
        dbname = self._template_db()
        if not dbname or not self._db_exists(dbname):
            raise UserError(self.env._(
                'There is no blank system called "%s".', dbname or '(not set)'))
        lines = []
        count = self._quiet_template(dbname, lambda t, l='info': lines.append(t))
        return {'ok': True, 'disabled': count, 'log': lines}

    def _write_standing(self, tenant, dbname, master, targets, rel, plan):
        """Where this customer now stands. ON OUR RECORD, never on theirs."""
        after = self._installed_on(dbname)
        diff = sync_diff({n: d['have'] for n, d in master.items()}, after)
        state = release_state(targets, after)
        vals = {
            'behind_count': len(diff['to_install']),
            'stale_count': len(diff['to_update']),
            'skipped_count': plan.get('skipped_count', -1),
            'release_state': state,
            'drift_checked': fields.Datetime.now(),
            'last_sync_at': fields.Datetime.now(),
            'last_sync_result': json.dumps(plan, default=str)[:200000],
            'module_count': len(after),
        }
        if rel and state == 'on':
            vals['release_id'] = rel.id
        tenant.write(vals)

    # =====================================================================
    #  6. RELEASES
    # =====================================================================
    @api.model
    def release_cut(self, notes=''):
        """Freeze what the master runs right now, and name it.

        Refuses while the master has not applied its own files: a photograph of
        a system halfway through catching up is a photograph of a mixture, and
        every customer would then be aimed at it.
        """
        self._require_platform_admin()
        master = self._master_modules()
        behind = master_behind_files(
            [(n, d['have'], d['file']) for n, d in master.items()])
        if behind:
            raise UserError(self.env._(
                "The master has not caught up with its own files yet — %(n)s "
                "parts are waiting, starting with %(first)s. A release is a "
                "photograph of what the master runs, so it cannot be taken "
                "while the master is halfway through.",
                n=len(behind), first=behind[0]))
        Release = self.env['biz.release'].sudo()
        name = release_name(date.today(), Release.search([]).mapped('name'))
        snapshot = {n: d['have'] for n, d in master.items()}
        rel = Release.create({
            'name': name, 'cut_on': fields.Datetime.now(),
            'notes': (notes or '').strip(),
            'module_fingerprint': json.dumps(snapshot, sort_keys=True),
            'module_count': len(snapshot), 'cut_by': self.env.uid,
        })
        rel.make_current()
        _logger.info("biz_tenants: release %s cut with %d parts",
                     name, len(snapshot))
        # THE MASTER READS ITS OWN ABOUT SCREEN TOO. Written straight onto this
        # database rather than through `push_settings`, which refuses the master
        # by design: the owner is a user of the product, and a changelog nobody
        # can see on their own screen is a changelog nobody proof-reads.
        icp = self.env['ir.config_parameter'].sudo()
        for key, value in self._release_values(rel).items():
            icp.set_param(key, value or '')
        icp.set_param(common.T_PUSHED_AT,
                      fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        # Re-measure everybody against the new photograph. READ ONLY on their
        # systems: the only thing written is our own record of where they are.
        targets = snapshot
        for t in self._tenants().search([('state', '=', 'live')]):
            try:
                self._measure(t, master, targets, rel)
            except Exception:                                # noqa: BLE001
                _logger.warning("biz_tenants: could not measure %s against %s",
                                t.slug, name, exc_info=True)
        return self.sync_report()

    @api.model
    def release_list(self):
        self._require_platform_admin()
        return [{
            'id': r.id, 'name': r.name, 'cut_on': self._stamp(r.cut_on),
            'notes': r.notes or '', 'module_count': r.module_count,
            'current': r.is_current, 'cut_by': r.cut_by.name or '',
            'tenants': len(r.tenant_ids),
        } for r in self.env['biz.release'].sudo().search([], limit=30)]

    def _release_values(self, rel):
        """The settings a system is given when it lands on a release."""
        Release = self.env['biz.release'].sudo()
        history = [{
            'name': r.name,
            'date': r.cut_on.date().isoformat() if r.cut_on else '',
            'notes': r.notes or '',
        } for r in Release.search([], limit=10)]
        return {
            common.T_RELEASE: rel.name if rel else '',
            common.T_RELEASE_NOTES: (rel.notes or '') if rel else '',
            common.T_RELEASE_AT: (rel.cut_on.date().isoformat()
                                  if rel and rel.cut_on else ''),
            common.T_RELEASES: json.dumps(history),
        }

    def _push_release_stamp(self, target, plan, rel, say):
        """Tell a system which release it is on — but only if it IS.

        THE ONE MOMENT A CUSTOMER IS TOLD ABOUT A RELEASE. Cutting one
        announces it to nobody: a changelog for software somebody does not have
        yet is worse than no changelog. It happens here, at the end of the run
        that actually put them on it, and only when that run SUCCEEDED.

        Never fatal. A message that could not be delivered must not turn a
        successful update into a failed one; it becomes a line in the log.
        """
        plan['release_pushed'] = False
        if plan.get('release_state') != 'on' or not rel:
            return
        # ⚠ INSIDE A ROLLOUT THIS IS DEFERRED UNTIL THE HEALTH GATE HAS PASSED.
        # The unit would otherwise announce "you are on release X — here is
        # what changed" the moment the install finished, which on an update
        # that is about to be called a failure is a message that cannot be
        # taken back. The rollout stamps it itself, last, and only on success.
        if self.env.context.get('biz_defer_release_stamp'):
            plan['release_deferred'] = True
            return
        try:
            res = self.push_settings(target, self._release_values(rel))
        except Exception:                                    # noqa: BLE001
            _logger.warning("biz_tenants: could not stamp the release on %s",
                            plan.get('database'), exc_info=True)
            say("This system is on the release but could not be told so — its "
                "About screen catches up next time.", 'warn')
            return
        plan['release_pushed'] = bool(res.get('ok'))
        if res.get('ok'):
            say("Told it that it is now on release %s. Its people get one note "
                "about it and a screen saying what changed." % rel.name)
        elif res.get('reason'):
            say(res['reason'], 'warn')

    def _measure(self, tenant, master, targets, rel):
        """Read one customer and write down where they stand. WRITES NOTHING
        on their system."""
        if not self._db_exists(tenant.slug):
            tenant.write({'release_state': 'unknown',
                          'drift_checked': fields.Datetime.now()})
            return
        have = self._installed_on(tenant.slug)
        diff = sync_diff({n: d['have'] for n, d in master.items()}, have)
        state = release_state(targets, have)
        vals = {
            'behind_count': len(diff['to_install']),
            'stale_count': len(diff['to_update']),
            'release_state': state,
            'module_count': len(have),
            'drift_checked': fields.Datetime.now(),
        }
        if rel and state == 'on':
            vals['release_id'] = rel.id
        tenant.write(vals)

    # =====================================================================
    #  7. SAYING SOMETHING TO A CUSTOMER
    #
    #  ONE DOOR, AND IT IS `push_settings`. Everything the platform ever writes
    #  onto somebody else's system goes through this method, so there is exactly
    #  one place that refuses the systems it must never touch and exactly one
    #  place that leaves a line in that customer's own log.
    # =====================================================================
    def _tenancy_values(self):
        """What every customer is told about the platform itself."""
        icp = self.env['ir.config_parameter'].sudo()
        rel = self.env['biz.release'].sudo().current()
        vals = {
            common.T_PLATFORM_URL: self._platform_url(),
            common.T_SUPPORT_EMAIL: (
                icp.get_param('biz_tenants.support_email', '') or ''),
        }
        if rel:
            vals.update(self._release_values(rel))
        return vals

    def _tenancy_installed(self, dbname):
        try:
            return common.TENANCY_MODULE in self._installed_on(dbname)
        except Exception:                                    # noqa: BLE001
            return False

    def push_settings(self, target, values):
        """Write what the platform has to say onto ONE system.

        THROUGH THE DATA LAYER, NEVER SQL (rail R5) — and then telling every
        other process (F56, in `_tenant_env`).

        A system without the platform link is a SKIP with a sentence saying what
        to do about it, never an error: sending one message to eleven customers
        must not fail wholesale because the twelfth has not been brought in step.
        """
        self._require_platform_admin()
        dbname, label, tenant, _is_template = self._resolve_target(target)
        # Belt and braces on top of the resolver, which already refuses the
        # master by name: the LITERAL database about to be written is re-asked
        # the never question, because that list is what actually runs (R2).
        if dbname == self.env.cr.dbname or common.is_never(dbname):
            raise UserError(self.env._(
                "This is the platform's own system. Messages go OUT from "
                "here — they are not sent to it."))
        if not self._db_exists(dbname):
            return {'ok': False, 'database': dbname, 'label': label,
                    'reason': 'There is no system called "%s".' % dbname}
        if not self._tenancy_installed(dbname):
            return {'ok': False, 'database': dbname, 'label': label,
                    'reason': ("%s does not have the platform link yet, so "
                               "there is nowhere to put the message. Bring it "
                               "in step first — the button is on the \"In step "
                               "with master\" screen." % label)}
        vals = dict(values or {})
        vals[common.T_PUSHED_AT] = fields.Datetime.now().strftime(
            '%Y-%m-%d %H:%M:%S')
        with self._tenant_env(dbname) as env:
            icp = env['ir.config_parameter'].sudo()
            for key, value in vals.items():
                icp.set_param(key, value or '')
        _logger.info("biz_tenants: pushed %d settings to %s", len(vals), dbname)
        return {'ok': True, 'database': dbname, 'label': label, 'reason': '',
                'keys': sorted(vals)}

    @api.model
    def notice_send(self, tenant_ids, kind, text, starts_at='', ends_at=''):
        """Put a message at the top of every page on one or more systems.

        THE WINDOW IS STORED AS THE PLATFORM'S OWN CLOCK — the browser sends it
        already converted, and the reader's browser converts it back. Two
        conversions, both explicit, so nobody's morning is announced as
        somebody else's evening (ledger F17/F32).
        """
        self._require_platform_admin()
        text = (text or '').strip()
        if not text:
            raise UserError(self.env._(
                "Write the message — it is the line people read."))
        if len(text) > 400:
            raise UserError(self.env._(
                "The message is %d characters. Keep it under 400: this is a "
                "bar at the top of a page, not an email.", len(text)))
        if kind not in ('maintenance', 'info'):
            raise UserError(self.env._(
                "Say whether this is a planned update or information."))
        if starts_at and ends_at and str(ends_at) <= str(starts_at):
            raise UserError(self.env._("It has to finish after it starts."))
        values = {
            common.T_NOTICE: text,
            common.T_NOTICE_KIND: kind,
            common.T_NOTICE_FROM: starts_at or '',
            common.T_NOTICE_TO: ends_at or '',
        }
        out = []
        for t in self._tenants().browse([int(i) for i in tenant_ids]).exists():
            res = self.push_settings(t.id, values)
            if res.get('ok'):
                t.write({'notice': text, 'notice_kind': kind,
                         'notice_from': starts_at or False,
                         'notice_to': ends_at or False,
                         'notice_sent_at': fields.Datetime.now()})
                t.log('Message sent to their people: "%s"' % text[:120])
            out.append({**res, 'tenant_id': t.id, 'name': t.name})
        # The public page carries anything the owner is telling customers, so
        # it is rewritten here. QUIETLY: sending a message must not fail
        # because a folder on this machine is missing — that is an alert of its
        # own, raised by the sweep, which is where it belongs.
        self._refresh_status_page_quietly()
        return {'results': out,
                'sent': len([r for r in out if r.get('ok')]),
                'skipped': len([r for r in out if not r.get('ok')])}

    @api.model
    def notice_clear(self, tenant_ids):
        """Take the bar down. Writes an EMPTY value rather than removing the
        row — "cleared" and "never set" are different facts (F24/F20)."""
        self._require_platform_admin()
        out = []
        for t in self._tenants().browse([int(i) for i in tenant_ids]).exists():
            res = self.push_settings(t.id, {
                common.T_NOTICE: '', common.T_NOTICE_KIND: '',
                common.T_NOTICE_FROM: '', common.T_NOTICE_TO: ''})
            if res.get('ok'):
                t.write({'notice': '', 'notice_kind': False,
                         'notice_from': False, 'notice_to': False})
                t.log('Message cleared.')
            out.append({**res, 'tenant_id': t.id, 'name': t.name})
        self._refresh_status_page_quietly()
        return {'results': out}

    # =====================================================================
    #  8. THE NUMBERS
    # =====================================================================
    @api.model
    def read_meters(self, tenant_id, start=None, end=None):
        """Every number the product registered, for one customer, for a period.

        EACH ONE GUARDS ON ITS OWN TABLE AND COLUMN, and answers "not available
        here" rather than raising. A customer who has not been brought in step
        does not have every table, and one number that raises must not take the
        other three with it.
        """
        self._require_platform_admin()
        t = self._tenants().browse(int(tenant_id)).exists()
        if not t:
            raise UserError(self.env._("That customer is not on the list."))
        today = date.today()
        start = start or today.replace(day=1).isoformat()
        end = end or today.isoformat()
        rows = []
        if not self._db_exists(t.slug):
            return {'start': start, 'end': end, 'rows': [], 'measurable': False}
        for spec in common.meters():
            rows.append(self._read_meter(t.slug, spec, start, end))
        return {'start': start, 'end': end, 'rows': rows, 'measurable': True}

    def _read_meter(self, dbname, spec, start, end):
        row = {'key': spec['key'], 'label': spec['label'],
               'unit': spec.get('unit') or '', 'help': spec.get('help') or '',
               'value': 0, 'available': False, 'reason': ''}
        try:
            with self._pg_cursor(dbname) as cr:
                if spec.get('table_guard'):
                    cr.execute("SELECT to_regclass(%s)", (spec['table_guard'],))
                    if not cr.fetchone()[0]:
                        row['reason'] = ("This part of the product is not on "
                                         "their system, so there is nothing to "
                                         "count.")
                        return row
                if spec.get('column_guard'):
                    table, _, column = spec['column_guard'].partition('.')
                    cr.execute(
                        "SELECT 1 FROM information_schema.columns "
                        "WHERE table_name = %s AND column_name = %s",
                        (table, column))
                    if not cr.fetchone():
                        row['reason'] = ("Their system records this "
                                         "differently, so it cannot be "
                                         "counted here.")
                        return row
                cr.execute(spec['sql'], {'start': start, 'end': end})
                got = cr.fetchone()
                row['value'] = int((got and got[0]) or 0)
                row['available'] = True
        except Exception as e:                               # noqa: BLE001
            _logger.warning("biz_tenants: meter %s failed on %s: %s",
                            spec['key'], dbname, e)
            row['reason'] = "This number could not be read: %s" % e
        return row

    @api.model
    def snapshot_meters(self, tenant_id=None, start=None, end=None):
        """Write the readings down. THE SEAM THE NEXT PHASE BILLS FROM.

        Nothing uses these rows yet, and that is deliberate: a table that starts
        collecting on the day billing is switched on has no history to bill from.
        """
        self._require_platform_admin()
        domain = ([('id', '=', int(tenant_id))] if tenant_id
                  else [('state', '=', 'live')])
        today = date.today()
        start = start or today.replace(day=1).isoformat()
        end = end or today.isoformat()
        written = 0
        Meter = self.env['biz.tenant.meter'].sudo()
        for t in self._tenants().search(domain):
            data = self.read_meters(t.id, start, end)
            for row in data['rows']:
                Meter.record(t, row, start, end)
                written += 1
        return {'written': written, 'start': start, 'end': end}

    # =====================================================================
    #  9. THE SCHEDULED JOBS — THEY READ, THEY NEVER INSTALL (rail R1)
    # =====================================================================
    @api.model
    def _cron_health(self):
        """Read every customer's health. Writes only our own records."""
        for t in self._tenants().search(
                [('state', 'in', ('live', 'provisioning', 'error'))]):
            try:
                self._read_health(t)
            except Exception as e:                           # noqa: BLE001
                _logger.warning("biz_tenants: health read failed for %s: %s",
                                t.slug, e)
            self.env.cr.commit()

    @api.model
    def _cron_drift(self):
        """Nightly: how far has each customer drifted from the release?

        READS every customer's system and WRITES only our own record of what it
        found. Nothing is installed, upgraded or repaired here, and nothing ever
        will be: a customer's system does not change while everybody is asleep.
        That sentence is on the screen too, so nobody has to read this comment
        to know it.
        """
        master = self._master_modules()
        targets, rel = self._targets(master)
        for t in self._tenants().search([('state', 'in', ('live', 'error'))]):
            try:
                self._measure(t, master, targets, rel)
            except Exception as e:                           # noqa: BLE001
                _logger.warning("biz_tenants: drift read failed for %s: %s",
                                t.slug, e)
            self.env.cr.commit()

    @api.model
    def _cron_nightly_backups(self):
        """A copy of every live customer, every night, kept for a fortnight."""
        for t in self._tenants().search([('state', '=', 'live')]):
            try:
                self._take_backup(t, 'nightly')
            except Exception as e:                           # noqa: BLE001
                _logger.warning("biz_tenants: nightly copy failed for %s: %s",
                                t.slug, e)
            self.env.cr.commit()
