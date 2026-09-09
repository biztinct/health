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
recovery. The user reports sending a message; the remaining diagnostic is to
compare the messaged account's profile/share link with the verified OA. Real
inbound confirmation and the outbound setup test are therefore still pending.
No message was sent to a person by this session.

No test PNGs or screenshot files were created. Evidence is textual.
