# The manifest names `post_init_hook`, and Odoo looks that name up on the
# PACKAGE (`odoo.addons.health_cms_coverage`), not on the module it lives in.
# `from . import hooks` alone binds `hooks`, not `post_init_hook`, so a fresh
# install dies with:
#
#     AttributeError: module 'odoo.addons.health_cms_coverage' has no
#     attribute 'post_init_hook'
#
# Invisible on any database where this module was already installed, because a
# post-init hook runs on INSTALL and never again on upgrade. Found building the
# golden template (SAAS H3).
from . import hooks
from .hooks import post_init_hook
