# CC-G evidence pack — vietuat, 2026-07-29

**Read this first: there are no screenshots in this pack, and that is a gap, not a
choice.** The browser session on `care.biztinct.com` had expired and this session holds
no QA login (the CC-E pack records the step as "User ID `crm`, password" without the
password, correctly). Everything below was therefore driven through the **same server
methods the screens call**, as the **real personas**, on the live UAT database — the
service-side half of DoD item 5. The screenshot half (§7 steps 2–4 of the handover) is
outstanding and is the one thing this phase owes.

What that costs, stated plainly: these transcripts prove the *values* the Go-live tab
renders and the *answers* the Center gives, not the *rendering*. A view arch error or a
mis-parented notebook page would not show up here. The arch loaded without error during
the upgrade (`EXIT:0`), which is weaker evidence than a picture.

Personas used:

| Persona | User | Groups |
|---|---|---|
| Tenant | `crm` ("CRM") | Care Command manager, **not** `base.group_system` |
| Operator | `odoo` shell as uid 1 | `base.group_system` (the platform plane's only audience) |

---

## Step 2 — zero platform apps: the tenant Center is unchanged

`channel.platform.app` rows before: **0** (`SELECT count(*) FROM channel_platform_app`).

`care.channel.connection.center_overview()` **as the tenant persona**:

```
zalo     available=False  "Not available yet"
call     available=True   "Continue setup"
email    available=False  "Not available yet"
zns      available=False  "Not available yet"
whatsapp available=False  "Not available yet"
fb       available=False  "Not available yet"
telegram available=True   "Continue setup"
webchat  available=True   "Continue setup"
```

Identical to CC-F. CC-G with zero rows is a strict no-op tenant-side, and the four
provider cards still carry the pending-approval copy. (`call`/`telegram`/`webchat` read
"Continue setup" because this deployment has half-finished connections for them from
someone's Center drive on 2026-07-28/29 — nothing to do with this phase.)

## Step 3 — an EMPTY zalo row: the behaviour change

Created `channel.platform.app(provider='zalo')` with nothing else filled in — exactly what
an operator does when they start. **Before CC-G this lit the Zalo and ZNS cards up and
every Connect could only fail.**

```
row 452  client_id=False  secret=False
zalo     available=False  "Not available yet"
zns      available=False  "Not available yet"
whatsapp available=False  "Not available yet"
fb       available=False  "Not available yet"
```

Go-live tab, computed on that row:

```
Redirect URI : https://care.biztinct.com/channel_hub/oauth/callback/zalo
Webhook URLs : Zalo OA: https://care.biztinct.com/care_channels/zalo/webhook
Checklist    : Channels served by this application: zalo, zns
               Application (client) ID entered   [To do]
               Client secret stored              [To do]
               Until every row above is done, the channels served by this
               application stay "Not available yet" for every tenant.
               Done outside Health19 (Zalo Developers)
               1. Create an app on Zalo Developers and link the Official Account.
               2. Add the redirect URI above to the app's OAuth settings. …
Preflight    : none → unverifiable
               "No harmless server-side check exists for this provider — the
                credentials are proven on the first real sign-in."
```

Then the same row COMPLETED (`client_id` + `action_set_secret`) — the gate only ever
tightens, so a finished row still lights the card:

```
zalo     available=True   "Upgrade connection"   ← a legacy zalo connection exists here
zns      available=True   "Available in an upcoming update"
Checklist: Application (client) ID entered [Done] · Client secret stored [Done]
           "Every prerequisite Health19 can see is in place."
```

## Step 4 — a meta row, and a REAL preflight

Created `channel.platform.app(provider='meta', client_id='000000000000000')` with a
stored (fake) secret.

```
Checklist  : Channels served by this application: fb, whatsapp
             Application (client) ID entered   [Done]
             Client secret stored              [Done]
             Extra configuration: flb_config_id [To do]
             Extra configuration: verify_token  [To do]
             Extra configuration: es_config_id  [To do]
Redirect   : https://care.biztinct.com/channel_hub/oauth/callback/meta
Webhooks   : WhatsApp:  https://care.biztinct.com/care_channels/meta/whatsapp/webhook
             Messenger: https://care.biztinct.com/care_channels/meta/fb/webhook
whatsapp / fb cards: still "Not available yet" (three prerequisites missing)
```

Verify-token generator: minted a 32-character token, `extra_json` keys after the merge
`['verify_token']`; a second press refused with `UserError` (Meta's dashboard still holds
the first one).

**Preflight against the live Graph API** — a real HTTPS round trip from vietuat to
`graph.facebook.com/v21.0/oauth/access_token` with the deliberately invalid credentials:

```
preflight_status : fail            (persisted — the button returned a notification,
preflight_detail : HTTP 400: {"error":{"message":"Invalid Client ID",              it did not raise)
                    "type":"OAuthException",<redacted>,"fbtrace_id":"AibT-…"}}
return value     : {'tag': 'display_notification', …}
secret in detail : False
```

`redact()` removed the `"code":1` pair on the way in; the app secret appears nowhere. This
is the §5.65 posture working end to end: a provider refusal is an answer, the evidence
survives, and nothing explodes in the operator's face.

Audit rows written (append-only, deliberately NOT cleaned up — an operator really did do
these things):

```
preflight               platform app meta: fail
verify_token_generated  platform app meta
secret_rotated          platform app meta
secret_rotated          platform app zalo
preflight               platform app zalo: unverifiable
```

## Cleanup — fresh-cursor verified (§5.34)

Both QA rows unlinked, then re-checked in a **separate** shell invocation:

```
FRESH_CURSOR rows: 0
FRESH_CURSOR cards: zalo False "Not available yet"   zns   False "Not available yet"
                    whatsapp False "Not available yet"  fb  False "Not available yet"
                    email False "Not available yet"  call True "Continue setup"
                    telegram True "Continue setup"   webchat True "Continue setup"
SELECT count(*) FROM channel_platform_app  →  0
curl /web/login → HTTP:200
```

The database is back in exactly the state step 2 measured.

## Still owed

Screenshots of (a) the Center with zero rows, (b) the Go-live tab on an empty zalo row,
(c) the Go-live tab on a meta row. Blocked on a UAT login for `care.biztinct.com`.
