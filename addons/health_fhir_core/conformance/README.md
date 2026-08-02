# health_fhir_core/conformance

`capability_baseline.json` is the **committed CapabilityStatement of record**
for this facade: the exact output of `build_capability(env)` (default
`base_url`, i.e. `implementation.url == '/fhir/r4'`) with the `date` key
removed, because that key is a generation timestamp and not a claim about
capability.

It lives inside the module, not under `docs/`, so that exactly one copy exists:
the GC-1 test (`tests/test_fhir_conformance.py::test_22`) and the GC-3 weekly
conformance cron both read this file through `odoo.tools.misc.file_open`.
It is **not** a manifest `data` entry — nothing loads it into the database.

## Changing the capability

Regenerating this file is the ONLY sanctioned way to change what the server
declares. If `test_22` goes red, that is control C2 working — do not relax the
test. Decide whether the capability change was intended; if it was, regenerate
the baseline **in the same commit as the code that changed it**:

```bash
# on the server, AFTER the upgrade has completed and returned (never a second
# odoo-bin while a deploy is in flight — conventions §5.45)
ssh VietUcUAT 'sudo su - odoo -s /bin/bash -c "/odoo/odoo-server/odoo-bin \
  shell -c /etc/odoo-server.conf -d vietuat --no-http" ' <<'PY'
import json
from odoo.addons.health_fhir_core.capability import (
    build_capability, clear_capability_cache)
clear_capability_cache()
statement = build_capability(env)
print(json.dumps({k: v for k, v in statement.items() if k != 'date'},
                 sort_keys=True, indent=2, ensure_ascii=False))
PY
```

Note that `software.version` is the module's installed `latest_version`, so a
version bump in `__manifest__.py` is itself a capability change and requires a
regeneration. That is intentional: the deployed version is part of what the
server declares about itself (register item G3).
