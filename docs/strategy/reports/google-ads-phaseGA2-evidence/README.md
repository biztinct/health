# GA2 browser evidence — `health_google_ads` 19.0.2.0.0

**Server:** carejiox.com (master `carejiox`) · **Date:** 2026-09-15
**Personas:** two throwaway accounts created for this pass and **deleted at the
end of it** (§4):

| Login | Groups | Why |
|---|---|---|
| `ga2_qa_admin` (uid 9408) | the clinic-operator set **plus `base.group_system`** | the platform application screen is `base.group_system` only, and no password for `ash` was available in this session |
| `ga2_qa_ops` (uid 9407) | `base.group_user`, `sales_team.group_sale_manager`, `health_crm.group_health_crm_user` + `…_manager`, `health_base.group_healthcare_sales`, `…_operations_manager`, `…_base`, catchment Hà Nội — **deliberately NOT a system administrator** | the clinic persona the reporting flow is built for |

**No real Google credential exists anywhere in this pass.** The sign-in ID used
was `qa-ga2-throwaway-000000.apps.googleusercontent.com` and the two stored
values were `qa-secret-7f3a9c21` / `qa-devtoken-4b8e2d61`. Google refused them,
which is exactly what makes step 10 evidence rather than a claim.

**Console:** **0 errors, 0 warnings, 0 logs** across every screen — see
`console-log.txt`. The only console entries at all are two pre-existing
DevTools accessibility *issue* hints raised by the CMS shell's own form markup.

---

## 1. The navigation path, click by click

Every screen was reached by clicking, starting from the login page. The two
literal URL entries are called out below and neither proves a step.

| # | File | How it was reached / what it proves |
|---|---|---|
| 01 | `01-login-admin.png` | `https://carejiox.com/web/login` → User ID `ga2_qa_admin` + password. |
| 02 | `02-admin-sidebar-leaf.png` | **Log in** → lands on `/bizapp`, the CMS shell. Scrolled the sidebar to **ADMIN**, where the new **Google Ads application** leaf sits at sequence 94, between *Channel Go-Live* and *CMS Sidebar Config*, with the `fa fa-google` icon. |
| 03 | `03-platform-config-list-empty.png` | click **Google Ads application** → the action opens **inside the CMS chrome** (sidebar intact, leaf highlighted, breadcrumb *Google Ads application*). Honestly empty, with the nocontent help *"One set of Google credentials serves every clinic on this system. A clinic signs in with its own Google account; this is the application it signs in to."* |
| 04 | `04-platform-config-form-new.png` | click **New** → the form. Two header buttons, the **WHAT IS STILL MISSING** checklist reading *Sign-in ID — to do · Sign-in secret — to do · Advertising access token — to do · **?** Return address registered with Google — confirmed on the first successful sign-in*, and the **RETURN ADDRESS** chip with the copy widget showing `https://carejiox.com/channel_hub/oauth/callback/google_ads`. Neither `*_enc` column appears anywhere on the screen. |
| 05 | `05-set-signin-secret-wizard.png` | typed the throwaway sign-in ID → click **Set the sign-in secret** → the record saves (id 19) and the wizard opens. *What to set* reads **Sign-in secret**; *Value* is a masked field; the note says *"Pasted once. It is scrambled the moment it is stored and can never be read back from this screen."* |
| 06 | `06-signin-secret-stored.png` | the masked value typed, immediately before **Store it**. |
| 07 | `07-both-secrets-stored-checklist-done.png` | **Set the advertising access token** → *Store it* → the form re-opens by itself showing **both** hints (`••••9c21`, `••••2d61`) and the checklist at *✓ ✓ ✓ **?***. The chatter (step 05→07) carries status lines only — *"The Google sign-in secret was stored by ga2_qa_admin."* — never a value or a fragment of one. |
| 08 | `08-operator-sidebar-no-platform-leaf.png` | logged out, logged in as **`ga2_qa_ops`**. The sidebar shows **Google Ads** (CRM, seq 22) and, in ADMIN, **no Google Ads application leaf at all** — DOM read: `hasGoogleAdsLeaf: true, hasPlatformLeaf: false`. **This answers the handover's open question**: the CMS sidebar hides a leaf whose action the user has no ACL for, so the leaf needed no `role_ids`. |
| 09 | `09-campaign-reporting-tab-not-connected.png` | **Google Ads** → **New** → named *GA2 QA account (delete me)* → tab **Campaign reporting**. The statusbar reads *Not connected · Signing in · Choose account · Connected*; exactly one button, **Connect Google account**; the honest paragraph *"Connecting lets this system **read** your advertising account: campaign names, spend, clicks and Google-reported conversions. It never creates, edits or publishes ads, and never changes budgets."* plus *"Website enquiries keep arriving whatever this page says."* The two token columns are absent for this non-system persona. |
| 10 | `10-google-signin-invalid-client.png` + `10b-authorization-url.txt` | **Save**, then **Connect Google account** → the browser leaves for `accounts.google.com` and Google answers **"Access blocked: Authorization Error — The OAuth client was not found. Error 401: invalid_client"**, because the sign-in ID is a throwaway. `10b` is the **full authorization request, captured from the browser's own network log**: our exact return address, `scope=…/auth/adwords`, `access_type=offline`, `prompt=consent`, `include_granted_scopes=false`, `code_challenge_method=S256` and a one-time state. **Deviation from the handover's wording:** it asks for a URL-bar screenshot; Google 302s off the authorization URL instantly, so the landing URL no longer carries `redirect_uri`, and the CDP screenshot API captures the page, not the browser chrome. The network capture carries strictly more than a URL bar would have, and is quoted in full. |
| 11 | `11-bogus-state-generic-page.png` | typed `https://carejiox.com/channel_hub/oauth/callback/google_ads?state=bogus&code=nope` → the bilingual **"Không thể tiếp tục / This link can no longer be used"** page. Nothing from the query string is echoed; an unknown state is indistinguishable from a used or expired one. (One of the two literal URL entries — it is the address Google itself would call, and there is no click that produces it.) |
| 12 | `12-choose-account-state-buttons.png` | with the account **staged** into *Choose account* (§2), the tab now offers **Choose advertising account** + **Disconnect reporting**, the statusbar sits on *Choose account*, and *Google Account Connected* is ticked. |
| 13 | `13-reconnect-needed-plain-words.png` | click **Choose advertising account** → a **real** call to Google's token endpoint with the staged refresh token. Google refuses (`invalid_client`, HTTP 401) and the screen says, in plain words: *"Google Ads: reconnect needed. Google refused this request. Try again, and tell the platform operator if it keeps happening."* The statusbar moves to **Action required**, *Last Error Code* reads `invalid_client` — and **Website Leads stays exactly where it was** (rail R6: a lost reporting grant is not a lost website connector). |
| 14 | `14-action-required-reconnect-buttons.png` | the same tab in `action_required`: **Reconnect** + **Disconnect reporting**. |
| 15 | `15-disconnected-back-to-not-connected.png` | click **Disconnect reporting** → statusbar back to **Not connected**, *Last Error Code* cleared, and the notification *"Google Ads: reporting disconnected. This system no longer reads anything from Google Ads. Website enquiries keep arriving as before."* No call left this server (there is no revoke — a shared Google grant may also back the clinic's mailbox). |

The second literal URL entry was `/bizapp/action-1789/232`, used to re-open the
QA account after the staging step in §2 — a record the pass had already reached
by clicking twice (steps 09→10).

## 2. The one staged state, named as such

`select_account` cannot be reached without a real Google sign-in, and no real
Google credential exists. So that steps 12–15 could be driven at all, the QA
account was put into `select_account` from an `odoo-bin` shell
(`carejiox-deploy -x`) with two **throwaway strings** encrypted the same way a
real token would be:

```
access_token_enc  = encrypt('qa-staged-access-not-a-real-token')
refresh_token_enc = encrypt('qa-staged-refresh-not-a-real-token')
reporting_state   = 'select_account'
```

Nothing about that staging is a claim about Google. What steps 13–15 prove is
our own behaviour: the refresh path really calls
`https://oauth2.googleapis.com/token`, a refusal is mapped to a plain-words
message and `action_required`, the website capability does not move, and
disconnect clears our copy of the permission.

**Live sign-in is therefore UNVERIFIED** and says so in the report: it needs a
real Google Cloud OAuth client, a real Google Ads developer token, and a Google
login that manages the clinic's ads. None exists yet.

## 3. Server-side rows this pass created

| Row | id | What happened to it |
|---|---|---|
| `google.ads.platform.config` "Google Ads application" | **19** | created (04), two throwaway values stored (05–07), **unlinked** at teardown |
| `google.ads.account` "GA2 QA account (delete me)" | **232** | created (09), signed-in-with (10), staged (12), disconnected (15), **unlinked** at teardown |
| `google.ads.oauth.session` | **43** | minted by step 10, single-use, **unlinked** at teardown |
| `res.users` `ga2_qa_admin` / `ga2_qa_ops` | **9408 / 9407** | **unlinked** (not archived), partners unlinked with them |

## 4. Teardown, verified on a FRESH cursor

Taken in a separate `psql` session after the shell that made the deletions had
exited (ledger §5.34):

| Database | `google_ads_account` | `google_ads_platform_config` | `google_ads_oauth_session` |
|---|---|---|---|
| carejiox | **0** | **0** | **0** |
| carejiox_template | **0** | **0** | **0** |
| hhh | **0** | **0** | **0** |

`select count(*) from res_users where login like 'ga2_qa%'` → **0**.
`select count(*) from ir_cron where active` on `carejiox_template` → **0**.

No screenshot was created outside this folder. One capture attempt
(`10c-url-bar.png`) grabbed the desktop rather than the browser window and was
deleted; the network capture in `10b` replaces it.

## 5. One thing this pass found and fixed

Pressing **Set the sign-in secret** stored the value correctly and then left
the form showing *"Sign-in secret — to do"*, because `checklist` and the two
hints are non-stored computes and the wizard answered with a notification
alone. It reads exactly like a failure. Fixed in the same phase
(`google_ads_platform_config.py::_with_reload`, the posture the account's own
buttons already used) and re-driven on the fixed code — step 07 is the
after-shot, and the form re-opens by itself with both hints and a full
checklist.

## 6. One pre-existing thing worth reporting, not fixed

The public callback page (step 11) is `health_care_command_channels`'
`oauth_generic` template and calls the product **"Health19"** in both
languages. That is the repo's internal name, not the product name a clinic
knows, and it is on a page a clinic's operator can land on. It is not this
phase's file and was not touched; flagging it for whoever owns that template.
