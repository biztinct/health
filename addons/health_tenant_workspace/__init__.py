from . import models
from . import controllers

def post_init_hook(env):
    env["health.tenant.workspace"]._seed_navigation()
