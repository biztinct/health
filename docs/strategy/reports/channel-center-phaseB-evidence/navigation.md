# CC-B browser evidence — web chat end to end on vietuat

**Date:** 2026-07-25 · **Host:** https://care.biztinct.com ·
**Driver:** chrome-devtools MCP · **Modules:** health_care_command_channels
19.0.2.0.0, health_care_command 19.0.4.1.0

## The path a real visitor takes (no deep link, no shortcut)

1. `GET https://care.biztinct.com/care_channels/webchat/demo` — the standalone
   demo host page (public, anonymous, no login). It embeds the widget exactly
   the way a tenant site would, with the copy-paste snippet printed on the page.
2. Click the **Chat** launcher (bottom right). The widget calls
   `POST /care_channels/webchat/start`; the server mints the uuid4 session
   (never the client) and returns the greeting configured on the connection —
   rendered as the grey note *“Xin chao! Chung toi co the giup gi cho ban?”*.
3. Type and **Send**:
   `Chào anh chị, mẹ tôi cần điều dưỡng tại nhà 3 buổi/tuần. Chi phí thế nào ạ?`
   → `POST /care_channels/webchat/message` → the message appears in the widget
   **via the poll** (`GET /care_channels/webchat/poll?session&after_id`), i.e.
   it round-tripped through the server rather than being echoed locally.
4. Ops side, driven as the real `crm` user through the exact RPCs the composer
   calls (`get_workspace_data` → `get_conversation_detail` →
   `action_send_channel`) — see `server-state.txt` and the transcript below.
5. The agent's reply lands back in the widget on the next poll (screenshot
   `02-webchat-end-to-end.png`), with no page reload.

## Ops-side transcript (real CRM user, not superuser)

```
ACTING AS: crm | companies: ['VIET UC']
IN OPS WALL: True
ROW: {'id': 5276, 'name': 'Web visitor 87ace8c5', 'channel': 'webchat',
      'channel_live': True, 'status': 'needs_reply', 'unread': 1,
      'urgency': 55, 'tier': 'medium', 'reason': {'text': 'Needs reply', 'hot': True},
      'snippet': 'Chào anh chị, mẹ tôi cần điều dưỡng tại nhà 3 buổi/tuần…'}
ACTIVE CHANNELS: ['zalo', 'call', 'email', 'zns', 'webchat']
CHANNEL COUNTS: {'webchat': {'total': 2, 'needs': 2}, 'all': {'total': 169, 'needs': 169}}
CAPABILITIES: {'can_reply_zalo': False, 'can_reply_email': False,
               'ext_reply_channel': 'webchat'}
TIMELINE: [('webchat', 'in', 'Chào anh chị, mẹ tôi cần điều …')]
REPLY BUBBLE: {'kind': 'webchat', 'direction': 'out', 'delivery': 'sent', …}
CONV AFTER: waiting 0
```

`ACTIVE CHANNELS` is the dock-honesty proof: with one **ready** web-chat
connection the dock gains `webchat` and nothing else — WhatsApp, Messenger and
Telegram stay dark because no connection exists for them. After the QA fixture
was removed the same call returns the base four only (`server-state.txt`).

## Console

- `02-webchat-end-to-end.png` run: **no console messages at all** (clean).
- `01-webchat-widget-visitor.png` is the FIRST run, kept deliberately: it is the
  evidence for two defects this pass found and fixed —
  1. `[error] Refused to apply style … widget.css` — the demo page's embed
     snippet, written as XML-escaped `&lt;script…&gt;`, was served as a REAL
     `<script>` element, so the widget loaded twice and the second copy read
     `data-origin="…"` and built a broken stylesheet URL. Fixed by rendering the
     snippet through `t-out` (escaped at render time) plus a `__h19WebchatLoaded`
     guard and a strict `data-origin` validator in the widget.
  2. `[issue] Page layout may be unexpected due to Quirks Mode` — a QWeb
     template rooted at `<html>` is served with no doctype. Fixed by rendering
     via `ir.qweb._render` and prepending `Markup('<!DOCTYPE html>')`
     (`Markup + Markup`, never `str + Markup` — the latter escapes the doctype;
     ledger §5.20, hit live here).

## Not covered by this pack

The Care Command **backend** screenshots (dock icons, composer, AI-module
patch) are absent: no login credential for care.biztinct.com is available in
this session, and creating or resetting a privileged account purely to take a
screenshot was not an acceptable trade. The same facts are proven server-side
in `server-state.txt` (`_channel_keys()`, `active_channels`, capabilities) and
in the ops transcript above, which runs as the real `crm` user through the same
RPCs the OWL composer calls.
