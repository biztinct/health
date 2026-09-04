# -*- coding: utf-8 -*-
# The registries first: `service.py` imports them at module load, and a product
# overlay registers into them at ITS import time. Reading a registry at CALL
# time rather than at import time is what makes the order stop mattering.
from . import tenants_common
from . import module_set
from . import sync_rules
from . import provision_rules
from . import rollout_rules
from . import alert_rules
from . import release
from . import tenant
from . import rollout
from . import alert
from . import feature
from . import service
# ⚠ THE TWO HALVES OF THE FACADE COME AFTER `service`, because they inherit the
# model it declares. They are separate files rather than three thousand more
# lines in one, and each is named for what it does: a helper added to a shared
# facade is a helper added to every file that shares it, and a name collision
# there breaks a button two phases old (ledger F52).
from . import rollout_service
from . import alert_service
from . import feature_service
from . import support_service
