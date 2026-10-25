# TaupoHealth HTTPS

Target: SSH alias `TaupoHealth`, public IP `52.63.217.105`.
Serves `thhs.org.nz` and `www.thhs.org.nz` using the existing Odoo upstream.
Both HTTP hostnames redirect to HTTPS, preserving the hostname and request URI.

This deployment scope is the Nginx TLS configuration and certificate renewal
schedule. No application module or database migration is involved. Existing
Odoo configuration already has `proxy_mode = True`.

## Certificate and renewal

The existing Let's Encrypt production account was reused. Certbot 5.8.0 from
`/snap/bin/certbot` issued and installed the certificate for both names on
2026-10-25. Its initial expiry is 2027-01-23; renewals replace it automatically.

Certificates and private keys remain only on the server under
`/etc/letsencrypt/live/thhs.org.nz/`. They must never be committed.
The renewal file uses the Nginx authenticator and installer, which handles
validation and reloads Nginx with renewed certificates.

`snap.certbot.renew.timer` is enabled. The duplicate old apt `certbot.timer`
is disabled so two Certbot versions do not manage the same certificate state.
Public inbound TCP ports 80 and 443 must remain available. Port 80 is used by
Let's Encrypt HTTP validation as well as normal HTTPS redirects.

## Deploy the latest combined configuration

Recheck the branch head and working tree before deployment. Copy this entire
directory from the latest combined repository state to a staging directory on
TaupoHealth, then run `sudo bash /path/to/stage/deploy.sh`. The script requires
the existing certificate, validates Nginx before reload, and restores its
backed-up configuration if installation or reload fails.

The original pre-HTTPS backup is root-readable only:
`/var/backups/thhs-https-20261025T113320Z/nginx-letsencrypt-before.tar.gz`.
Each deployment also creates a separate configuration rollback directory.

## Verify

- `sudo nginx -t`
- `sudo /snap/bin/certbot renew --cert-name thhs.org.nz --dry-run --no-random-sleep-on-renew`
- Check both HTTPS names with certificate verification enabled and confirm
  HTTP requests redirect to their HTTPS equivalents, preserving paths.
- Open the site and follow public navigation in Chrome without bypassing
  certificate warnings; check that images and styles load over HTTPS.
- Do not retain test screenshots or generated PNG files.
