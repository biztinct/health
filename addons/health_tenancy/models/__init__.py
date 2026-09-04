# -*- coding: utf-8 -*-
# `cms_sidebar` FIRST, because `registrations` imports the menu-preview
# function out of it at import time and hands it to the generic cockpit.
from . import cms_sidebar
from . import registrations
