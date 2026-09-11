# Zalo message delivery checks

Both Hanoi and HCMC OAs can use the same CarejioxApp webhook. Authorize each OA separately in Channel Center and retain its own credentials.

In Zalo Developers → CarejioxApp → Webhook, enable the incoming message events and these outbound message events:

- `oa_send_text`
- `oa_send_image`
- `oa_send_gif`
- `oa_send_file`
- `oa_send_sticker`

On 2026-09-11 all five outbound switches were found disabled. They were enabled and their checked state verified in the developer console. The webhook URL remains `https://carejiox.com/care_channels/zalo/webhook`; no signing secret was changed.

A client message proving inbound delivery does not prove delivery of OA-admin replies. Verify separately with an OA-inbox reply to a test conversation. An OA reply should appear on the right with an OA source label, and stickers should have image previews. Personal-account chats are outside the OA integration.

The receiving code deduplicates provider message IDs per OA, so the webhook echo of a Care Command send must not produce a second bubble. Old events not delivered by Zalo cannot be recovered from local records. Existing saved sticker events are rendered without rewriting their historical file classification.
