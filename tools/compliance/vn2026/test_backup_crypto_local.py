"""Run the production crypto helpers without an Odoo registry."""
import importlib.util
import pathlib
import sys
import types
import unittest
root=pathlib.Path(__file__).resolve().parents[3]
package=types.ModuleType('backup_test');package.__path__=[];sys.modules['backup_test']=package
tests=types.ModuleType('backup_test.tests');tests.__path__=[];sys.modules['backup_test.tests']=tests
for name,path in [('backup_crypto','addons/biz_tenants/backup_crypto.py'),('test_backup_crypto','addons/biz_tenants/tests/test_backup_crypto.py')]:
    spec=importlib.util.spec_from_file_location('backup_test.'+('tests.' if name.startswith('test_') else '')+name,root/path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;setattr(package,name,module);spec.loader.exec_module(module)
result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(package.test_backup_crypto))
sys.exit(not result.wasSuccessful())
