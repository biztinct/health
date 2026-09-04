# -*- coding: utf-8 -*-
# The registries first: `service.py` imports them at module load, and a product
# overlay registers into them at ITS import time. Reading a registry at CALL
# time rather than at import time is what makes the order stop mattering.
from . import tenants_common
from . import sync_rules
from . import provision_rules
from . import release
from . import tenant
from . import service
