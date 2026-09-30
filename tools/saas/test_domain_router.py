"""Run without Odoo: python3 -m unittest discover -s tools/saas -p 'test_domain_router.py'."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('router', Path(__file__).resolve().parents[2] / 'addons/biz_domain_router/router.py')
router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(router)

class DomainRouterTests(unittest.TestCase):
    def setUp(self):
        self.map = {'care.customer.test': 'clinic-one'}
        self.fallback = lambda dbs, host: ['fallback']

    def test_exact_mapping_overrides_first_label(self):
        self.assertEqual(router.select_database(['care', 'clinic-one', 'other'], 'care.customer.test', self.map, self.fallback), ['clinic-one'])

    def test_mapping_cannot_invent_database(self):
        self.assertEqual(router.select_database(['other'], 'care.customer.test', self.map, self.fallback), [])

    def test_case_port_and_trailing_dot(self):
        self.assertEqual(router.select_database(['clinic-one'], 'CARE.CUSTOMER.TEST.:443', self.map, self.fallback), ['clinic-one'])

    def test_prefix_suffix_and_header_like_values_do_not_match(self):
        for host in ('evilcare.customer.test', 'care.customer.test.evil', 'clinic-one', 'care.customer.test,other'):
            self.assertEqual(router.select_database(['clinic-one'], host, self.map, self.fallback), ['fallback'])

    def test_root_owned_file_and_replacement_invalidation(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/'domains.json'
            p.write_text(json.dumps(self.map)); p.chmod(0o644)
            original = router.os.stat
            def root_stat(path, **kwargs):
                info = original(path, **kwargs)
                class Stat:
                    st_uid=0
                    st_mode=info.st_mode
                    st_ino=info.st_ino
                    st_mtime_ns=info.st_mtime_ns
                    st_size=info.st_size
                return Stat()
            with patch.object(router.os, 'stat', side_effect=root_stat):
                self.assertEqual(router.domain_map(str(p)), self.map)
                p.write_text('{}')
                self.assertEqual(router.domain_map(str(p)), {})
                p.chmod(0o666)
                with self.assertRaises(ValueError):router.domain_map(str(p))
                p.chmod(0o644)
                p.write_text('{"care.customer.test":"clinic-staging"}')
                with self.assertRaises(ValueError):router.domain_map(str(p))
