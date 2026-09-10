# Zalo Vietnam ingress relay

Zalo restricts delivery of user information when the receiving server is
outside Vietnam. Health19 currently runs in Australia, so its Zalo webhook must
be fronted by a small HTTPS reverse proxy with a public IPv4 address that Zalo
geolocates to Vietnam.

This relay stores no messages and performs no authentication. It forwards only
the exact Zalo webhook route to `https://carejiox.com`; Health19 still validates
the OA-specific signature before accepting an event.

## Install

1. Create a Linux host in Vietnam and point an HTTPS hostname at its public IP.
2. Install nginx and Certbot, obtain the certificate, replace every
   `RELAY_HOST` in `nginx.conf.template`, and install it as an enabled nginx
   site.
3. Confirm that every other path returns 404 and that GET/POST to
   `/care_channels/zalo/webhook` reaches Carejiox.
4. In the `carejiox` database set the system parameter
   `channel_hub.zalo_webhook_base` to the relay origin, for example
   `https://zalo-vn.example.com`.
5. Restart through `carejiox-deploy -s`, copy the webhook address shown in the
   Channel Connection Center into the Zalo developer portal, and send a new
   message to each connected OA. Each OA must independently turn the
   `webhook_verified` and `inbound_ok` checks green.

Both Hanoi and HCMC OAs use the same relay URL. Zalo includes the OA ID in each
event, and Health19 routes it to the connection and token for that exact OA.
