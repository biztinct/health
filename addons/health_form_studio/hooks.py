# -*- coding: utf-8 -*-
"""Install-time wiring that data files cannot express.

1. The groups behind "Staff" and "Admins" were just set; any Studio field that
   already exists (a database that had the core first) is rebuilt with them.
2. The Form Studio entry sits beside Field Requirements under the "Master
   data" heading when the menu reorganisation that created that heading is
   installed. The heading belongs to another module, so this is looked up and
   never assumed: without it the entry stays a plain row of the Settings
   section. Install-time only, so a move made later by an Owner is kept.
"""
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    env['fs.studio']._reapply_visibility()
    item = env.ref('health_form_studio.item_admin_form_studio',
                   raise_if_not_found=False)
    parent = env.ref('health_cms_ia.parent_admin_master',
                     raise_if_not_found=False)
    if item and parent and parent._name == item._name:
        item.parent_id = parent.id
        _logger.info("Form Studio: menu entry placed under %s", parent.name)
