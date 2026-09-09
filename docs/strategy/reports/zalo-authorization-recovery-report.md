# Zalo authorization recovery — 2026-09-09

The production Zalo callback saved the new access/refresh tokens on an independent
cursor, then tried to update the same connection from the request's older
REPEATABLE READ snapshot. PostgreSQL refused the update. The preserved token
made `has_credentials` true while the account identity and authorization checks
remained stale, and the wizard incorrectly advanced to webhook confirmation.

## Change

- `services/adapters.py`: finish the verified OA profile and readiness in a fresh,
  retryable transaction after durable token persistence. The one-use provider
  authorization code is exchanged once; only database finalization retries.
  Keep the legacy config bridge inside a savepoint.
- `models/care_channel_connection.py`: distinguish an uncommitted connection from
  an existing one before the independent credential write.
- `models/channel_center.py`: expose verified `signed_in` evidence and reject
  webhook-secret submission until authorization is complete.
- `static/src/center/channel_center.js`: advance from server authorization
  evidence, including polling when `noopener` prevents a popup handle. Closing
  or focusing a popup no longer asserts sign-in success.
- Vietnamese error translation, module version `19.0.11.5.1`, and regression tests.

No PWA shell assets changed. All code was based on the latest combined `19.0`
branch state, starting at `c8232a01`; no unrelated working-tree edits were present.
Implementation commit: `54900e29`.

## Deployment and recovery

Used the serialized `carejiox-deploy` wrapper on `VietUcUAT` for all installed
copies: `carejiox`, `carejiox_template`, and `hhh`. All three report
`19.0.11.5.1`; successful deploys exited 0 and service health returned HTTP 200.
The template has zero active scheduled jobs after its upgrade.

Recovered connection 1207 using its already-preserved access token and a real
Zalo `getoa` profile response. The returned OA ID was checked against
`1485357202584688773` before writing anything. It is now associated with
**Chăm sóc tại nhà Việt Úc**, with valid authorization/account/token checks and
its existing encrypted webhook secret preserved. Recovery added a
`resource_selected` audit entry; it did not manufacture a successful callback or
an inbound message. No new grant or token rotation was needed.

## Verification

- Zalo suite and committed-transaction regressions: **14/14 passed**.
- OAuth engine, including the shared durable token writer: **6/6 passed**.
- Existing G1/G2 catalogue check methods, scoped to the changed module and run
  in the deployment ORM: **5/5 passed** (file shape, code occurrences, filename,
  Python translation loading, and translated database field label).
- Python compilation, JavaScript syntax, and `git diff --check`: passed.
- Wider framework suite: **10 passed, 1 error**. The unchanged
  `test_89_settings_param` calls global settings, whose `biz_debranding` digest
  translation encounters the inactive language `sq_AL` and raises
  `UserError: Invalid language code: sq_AL`. The Zalo code is absent from that
  traceback. This is reported separately; no unrelated language/branding repair
  was included, and the broader suite is not claimed green.

The durable regression uses committed, inactive, test-owned connections and
real independent PostgreSQL cursors even with tests enabled. It proves successful
finalization and single-use callback replay rejection, and proves a failed
profile fetch preserves issued tokens without claiming authorization. Fixtures
and their audit rows are removed and absence is checked in a fresh cursor.

## Chrome and provider checks

Reloaded the deployed app, clicked the normal **Channel Center** sidebar entry,
then **Zalo → Finish setup**. The card now shows the real OA name and 4/6 checks;
the wizard resumes at **Wait for confirmation** using the saved secret. No
browser console errors were reported for this drive.

Zalo Developers → Official Account → OA Management → account details confirms
the matching OA, its Verified/Advanced status, and grants for message APIs and
message webhooks. The webhook URL is correct and `user_send_text` is enabled.

Zalo's built-in synthetic text-event delivery test reached the deployed endpoint
at 08:14:48 UTC and received HTTP 200. Its sample recipient is a different OA,
so it was correctly not accepted as proof for the user's connection. No synthetic
traffic was used to turn the real connection green.

At the last inspection, no real message webhook had reached the server after
recovery. The user reports sending a message to the matching account name.
Real inbound confirmation and the outbound setup test remain pending.
No message was sent to a person by this session.

## Confirmed regional API restriction

A read-only `GET /v2.0/oa/listrecentchat` with the saved connection token returned
HTTP 200 but provider error **-501**:

> Personal information is limited due to IP address not inside Vietnam: 54.206.18.111

Only the error and response shape were printed; no credentials or conversation
content were exported. The diagnostic used `carejiox-deploy -x`, rolled back its
database transaction, and ended with service health HTTP 200.

Zalo Developers' webhook URL check independently identifies this endpoint as
`54.206.18.111 [AU]` and advises a Vietnam IP for full webhook/API responses.
The URL was checked without saving any configuration changes. Zalo's
[official regional-data notice](https://developers.zalo.me/docs/api/developer-notification/-quan-trong-gioi-han-du-lieu-theo-dia-chi-ip-post-7594)
and its [published English announcement](https://vn.linkedin.com/pulse/zalo-openapi-gi%E1%BB%9Bi-h%E1%BA%A1n-d%E1%BB%AF-li%E1%BB%87u-theo-%C4%91%E1%BB%8Ba-ch%E1%BB%89-ip-zalo-cloud-bwozc)
say this restriction applies to user-related API and webhook data.

The regional API restriction is proven; it is a plausible explanation for the
missing real webhook, not proof that every missing event has this cause. No
Vietnam deployment target for this integration is configured in the project.
The next step needs the user's Vietnam hosting target/access, followed by a
provider check and a real inbound/outbound test. No unrelated host was accessed
and no speculative hosting migration was made.

No test PNGs or screenshot files were created. Evidence is textual.
