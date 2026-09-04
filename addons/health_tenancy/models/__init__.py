# -*- coding: utf-8 -*-
# `cms_sidebar` FIRST, because `registrations` imports the menu-preview
# function out of it at import time and hands it to the generic cockpit.
from . import cms_sidebar
from . import registrations
# And the one line of glue that names WHICH record this product's seat limit
# counts (SAAS H4d §3.5). The decision lives in the platform link; only the
# choice of record belongs to the product.
from . import res_users
