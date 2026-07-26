# CC-F evidence — vietuat, 2026-07-26

## Test run

```
odoo-bin -c /etc/odoo-server.conf -d vietuat \
  -u health_care_command_channels,health_voip24h \
  --test-enable --test-tags /health_care_command_channels,/health_voip24h \
  --stop-after-init --workers=0 --http-port=8169 --logfile=/tmp/ccf_run.log
```

```
EXIT:0        HTTP:200
odoo.tests.result: 0 failed, 0 error(s) of 127 tests
odoo.tests.stats: health_care_command_channels: 130 tests 24.61s 22604 queries
odoo.tests.stats: health_voip24h:                19 tests  0.37s   317 queries
FAIL: / ERROR: Test / ERROR: setUpClass lines — 0
```

`--workers=0` per §5.75. Channels went 100 → 130 test methods.

## Catalogue, as the real `crm` user's own RPC

```
zalo      legacy         available=False implemented=True
call      not_connected  available=True  implemented=True
email     not_connected  available=False implemented=True
zns       legacy         available=False implemented=False
whatsapp  not_connected  available=False implemented=True
fb        not_connected  available=False implemented=True
telegram  not_connected  available=True  implemented=True
webchat   not_connected  available=True  implemented=True

CALL_NOTICE: Calls arrive in Care Command. Placing calls and pulling call
             history need the VoIP24h API, which we cannot verify yet — so we
             do not offer them.
CALL_CHECKS: ['webhook_verified', 'inbound_ok']
EMAIL_ACTION: unavailable | Not available yet
EMAIL_PROVIDERS_AVAILABLE: []
SECRET_IN_PAYLOAD: False
```

`_find_mail_server_allowed_domain` composes with core's own clause rather than
replacing it (§5.79):

```
['&', ('owner_user_id', '=', False), ('care_connection_id', '=', False)]
```

## Live webhook — the adopted verifier, unchanged

A temporary `voip.config` (`CCF-EVIDENCE-TMP`) was created for these four
curls and **deleted afterwards**; the counts at the bottom of this file are
the post-cleanup state.

| # | Request | Result |
|---|---|---|
| 1 | unknown `account_id` | `HTTP:200 {"status": "ignored"}` — non-oracle |
| 2 | known account, **no** signature | `HTTP:403 {"status":"error","message":"Invalid signature"}` |
| 3 | known account, **wrong** signature | `HTTP:403` (same body — no oracle) |
| 4 | invalid JSON | `HTTP:400 {"status":"error","message":"Invalid JSON"}` |
| 5 | known account, **valid** HMAC-SHA256 over the raw body | `HTTP:200 {"status":"success","result":"created"}` |

No new public route. The full inventory across both modules is unchanged from
CC-E plus the pre-existing VoIP routes:

```
/care_channels/zalo/webhook
/care_channels/meta/<string:channel>/webhook   (GET + POST)
/care_channels/webchat/{start,message,poll,demo}
/care_channels/telegram/webhook/<string:path_secret>
/channel_hub/oauth/callback/<string:provider>
/voip24h/{click_to_dial,get_config,webhook}
```

## Browser pass — login page → CMS shell → Channel Center

Login `crm` at `https://care.biztinct.com/web/login` → lands in `/bizapp`
(§5.69) → sidebar **Channel Center** → `/bizapp/action-1706`. Seven top-level
cards (ZNS renders inside Zalo). **Zero console errors or warnings.**

- `01-catalogue-email-unavailable-calls-receive-only.png` — Email reads
  "Not available yet"; Calls carries the receive-only sentence on the card
  itself, without opening anything.
- `02-calls-stepper-own-copy-not-botfather.png` — the Calls stepper shows
  *its own* three steps ("Your phone system account" / "Point your phone
  system at us" / "Make a real call") and the receive-only alert. This is the
  §5.82 regression made visible: before the re-key, `call` joining
  `guided_secret` would have rendered Telegram's "Bot key" + @BotFather copy.
- `03-calls-webhook-step.png` — the webhook address
  (`https://care.biztinct.com/voip24h/webhook`), the secret field, and the
  plain-words warning that without a secret every event is refused. **Save is
  disabled with no secret** (verified: `saveDisabledWithNoSecret: true`).

Nothing was saved. The `authorizing` connection that `center_begin` created
during the pass (id 2862) was deleted afterwards.

## What is NOT proven

- **The email sign-in was never driven end to end.** With no `google` /
  `microsoft` platform app there is nothing to sign in to, so the honest
  browser evidence is the catalogue refusing it. The flow is covered against
  Odoo's real mixin computation in T142–T149 — including the consent URL,
  which those tests build for real rather than mocking.
- **No VoIP24h API call was made or tested**, by design. Item 5 of
  `docs/strategy/voip24h-contract-capture.md` (a real captured webhook
  payload, the true signature basis) is still the blocking unknown.
- **Google's CASA assessment** for the restricted `https://mail.google.com/`
  scope has not started. It is a human process, like Meta's App Review.

## Data honesty (post-cleanup)

| | |
|---|---|
| `channel.platform.app` rows | **0** (so email is unavailable, as designed) |
| `voip.config` rows | **0** |
| `voip.call.log` rows | **0** |
| `fetchmail.server` rows | **0** |
| `ir.mail_server` rows | **0** |
| `care.channel.connection` channel=call | **0** |
| `care.channel.connection` channel=email | **0** |
| CC-F facade migration | `{'created': 0, 'existing': 0, 'copied': 0}`, idempotent on re-run |

Nothing in CC-F has ever carried real traffic. Both halves are dark, and the
UI says so on every card.
