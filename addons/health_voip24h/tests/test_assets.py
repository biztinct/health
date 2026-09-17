# -*- coding: utf-8 -*-
"""A guard on the one JavaScript mistake that takes the WHOLE product down.

A service whose ``dependencies`` name something the framework does not provide
fails to start, and Odoo refuses to start the web client at all when any service
fails:

    Error: Some services could not be started: voip24h_phone.
    Missing dependencies: rpc

Every screen in the product goes blank — the CMS, Healthcare, Discuss, all of
them — from one wrong word in this module. It reaches nothing on the server, so
no Python test, no view validation and no HTTP check can see it; it is only
visible in a browser console. This box has no headless browser, so a tour test
would SKIP here rather than fail, which is worse than not having one.

So this reads the declarations out of our own JavaScript and checks each name
against the services the installed framework actually registers. It is a text
scan, deliberately: the alternative is trusting that somebody opened a browser.

The specific trap, for the record: on Odoo 19 ``rpc`` is an exported FUNCTION
(``@web/core/network/rpc``), not a service. It was a service on earlier
versions, and naming it here is the shape of an upgrade that was never
re-validated in a browser.
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

# `dependencies: ["a", "b"]` in a service definition.
_DEPS_RE = re.compile(r'dependencies\s*:\s*\[([^\]]*)\]', re.S)
# `registry.category("services").add("name"` wherever the framework declares one.
_SERVICE_RE = re.compile(
    r'category\(\s*["\']services["\']\s*\)\s*\.\s*add\(\s*["\']([\w.]+)["\']')

# Where the framework's own services live. Scanning every addon would read tens
# of thousands of files for no extra safety: a dependency our code may name is
# one the framework provides, and the framework is these.
_FRAMEWORK_MODULES = ('web', 'bus', 'mail', 'base_setup', 'web_tour',
                      'portal', 'website')


@tagged('post_install', '-at_install')
class TestJsServiceDependencies(TransactionCase):

    @staticmethod
    def _js_files(module):
        path = get_module_path(module)
        if not path:
            return
        for root, _dirs, files in os.walk(os.path.join(path, 'static', 'src')):
            for name in files:
                if name.endswith('.js'):
                    yield os.path.join(root, name)

    @classmethod
    def _registered_services(cls):
        found = set()
        for module in _FRAMEWORK_MODULES:
            for path in cls._js_files(module):
                try:
                    with open(path, encoding='utf-8') as fh:
                        found.update(_SERVICE_RE.findall(fh.read()))
                except OSError:
                    continue
        return found

    def test_90_every_service_dependency_really_exists(self):
        available = self._registered_services()
        # A scan that found nothing means the framework moved and this guard is
        # the thing that is broken — say so rather than passing vacuously.
        self.assertIn('orm', available,
                      'the service scan found nothing; this guard needs '
                      'updating, it has not proved anything')

        ours = {}
        declared = set()
        for path in self._js_files('health_voip24h'):
            with open(path, encoding='utf-8') as fh:
                source = fh.read()
            declared.update(_SERVICE_RE.findall(source))
            for block in _DEPS_RE.findall(source):
                for name in re.findall(r'["\'](\w+)["\']', block):
                    ours.setdefault(name, path)

        self.assertTrue(ours, 'no service dependencies found to check')
        for name, path in sorted(ours.items()):
            # A service this module declares itself is legitimate too.
            if name in declared:
                continue
            self.assertIn(
                name, available,
                'the browser service %r named in %s does not exist on this '
                'version. One unknown name stops EVERY screen in the product '
                'from loading, not just the phone.'
                % (name, os.path.basename(path)))

    def test_91_rpc_is_imported_not_depended_on(self):
        """The exact regression, pinned by name.

        `rpc` is a function on Odoo 19. It read as a service for years, so it is
        the one a future edit is most likely to reach for again.
        """
        for path in self._js_files('health_voip24h'):
            with open(path, encoding='utf-8') as fh:
                source = fh.read()
            for block in _DEPS_RE.findall(source):
                self.assertNotIn(
                    'rpc', re.findall(r'["\'](\w+)["\']', block),
                    '%s names "rpc" as a service dependency. Import it '
                    'instead: `import { rpc } from "@web/core/network/rpc"`.'
                    % os.path.basename(path))
