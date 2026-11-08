# CareJiyo Learning

The `health_learn` module adds four complementary surfaces:

- Task guides and videos under Learn, with search, topic filters, chapter playback and printable manuals.
- The Care Coach drawer opens relevant guides beside the current backend screen. Opening help does not navigate away from a draft form.
- Role learning paths, server-graded knowledge checks and trainer-led practice exercises. Reviewed/watched markers are personal activity, not a certification.
- Ask the coach retrieves published task instructions and links to the guide and a relevant video chapter. An optional existing AI provider can select an allowed topic key when direct retrieval is uncertain. It cannot supply procedure text or execute business actions.

## Content and releases

`addons/health_learn/data/learning_catalog.json` is the shared source for the library, coach and printable manuals. It contains functional task keys, English instructions, Vietnamese titles, role permissions, screen mappings, ordered chapters and role paths. Changes require an ordinary code review and module release. Keep recording provenance and historical testing references outside learner-facing prose.

The initial library contains 61 tasks, including 17 worked pricing examples. Actual work uses the clinic's current approved tariff. Instructions are English; navigation, task titles and video subtitles support Vietnamese. The entire manual is not a Vietnamese translation.

Media is outside the repository and outside public static attachments. The configured root is `health_learn.media_root`, default `/var/lib/odoo/carejiyo-learning`. A release maps each task to an opaque 64-character media identifier; files are `<identifier>.mp4`, `<identifier>.en.vtt` and `<identifier>.vi.vtt`. The server process must be able to read them. Upload matching media before deploying a catalog release. If a file is absent, the UI presents written instructions instead of a broken play button.

The controller authenticates every media/caption request and checks the signed-in person's role again, including direct URLs. File streaming supports byte-range requests. Responses are private and are not stored in public caches. No patient records are read to answer learning questions. Company and user are fixed on the server for progress writes. Direct progress CRUD is read-only for staff, and a global record rule prevents reading someone else's progress.

## Portable handover

Run `python tools/build_learning_pack.py OUTPUT --media PRIVATE_MEDIA_ROOT`. It builds an offline index, six manual volumes, the complete manual, quick reference and media/caption subfolders. Open `index.html` directly in Chrome. Captions are also embedded as text and loaded through blob URLs so local-file browser restrictions do not break subtitles. The portable copy has no login; distribute it only as the authorised client handover. Saved progress and Ask the coach remain inside the application.

In-app manuals are at `/carejiyo/learn/manual`, with optional `key` or `section` parameters. They apply the same role checks and can be printed or saved as PDF. Media links are `/carejiyo/learn/media/<task-key>/<kind>` where kind is `mp4`, `en.vtt` or `vi.vtt`.

## Verification and scope

Run `/health_learn` through the locked deployment wrapper. `TestTaskLibrary` covers role filtering, direct topic access, progress isolation and write denial, invalid saves, database uniqueness, server quiz grading, English/Vietnamese retrieval, clinical/current-amount refusal, unsupported questions and provider failure/unknown-key handling.

Verify the deployed backend in native Chrome: Learn navigation, search, steps, video playback and seeking, both captions, saved progress after reload, quiz attempts, coach answers/refusals, and contextual help over an unsaved form. The nurse app has a Help drawer outside its Vue work tree, preserving open visit forms. It opens role-checked mobile task instructions and videos in a same-origin frame and links to the full library. Help needs a connection; its offline message does not affect saved clinical work. The nurse app release is 1.21.7.

Deploy the combined application state to carejiox, carejiox_template and hhh; keep template cron jobs disabled. Use the existing provider configuration and central AI egress guard. This release does not grant new AI destinations or create staff accounts.
