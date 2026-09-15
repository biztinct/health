# -*- coding: utf-8 -*-
# ORDER IS LOAD-BEARING for the last three: Odoo runs `_auto_init()` and
# `init()` model by model in registry order, so the campaign-day TABLE has to
# be created before `google.ads.campaign.stat`'s `init()` runs `CREATE VIEW`
# over it.
from . import google_ads_platform_config
from . import google_ads_account
from . import google_ads_oauth_session
from . import google_ads_select_wizard
from . import google_ads_campaign
from . import google_ads_sync_run
from . import google_ads_campaign_day
from . import google_ads_campaign_stat
from . import google_ads_sync
from . import google_ads_backfill_wizard
from . import crm_lead
from . import lead_touchpoint
from . import web_lead_service
from . import channel_center
from . import care_channel_oauth_session
