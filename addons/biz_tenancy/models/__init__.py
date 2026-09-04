# -*- coding: utf-8 -*-
# `support` first: `tenancy` reads the support session from `state()` and
# `ir_http` imports one of its pure helpers, so the module has to exist before
# either of them is set up.
from . import support
from . import tenancy
# `standing` extends the model `tenancy` declares, so it comes after it and
# before `ir_http`, whose paused door reads it.
from . import standing
from . import ir_http
