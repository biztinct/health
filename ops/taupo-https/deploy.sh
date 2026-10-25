#!/usr/bin/env bash
# Run with sudo on TaupoHealth after copying this entire directory there.
set -euo pipefail

source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
site=/etc/nginx/sites-available/thhs.org.nz
tls_options=/etc/letsencrypt/options-ssl-nginx.conf
backup_dir=$(mktemp -d /var/backups/thhs-https-deploy.XXXXXX)

test "$(id -u)" -eq 0
test -s /etc/letsencrypt/live/thhs.org.nz/fullchain.pem
test -s /etc/letsencrypt/live/thhs.org.nz/privkey.pem
test -s /etc/letsencrypt/ssl-dhparams.pem
test -x /snap/bin/certbot
cp -a "$site" "$backup_dir/site.conf"
cp -a "$tls_options" "$backup_dir/tls-options.conf"

rollback() {
    cp -a "$backup_dir/site.conf" "$site"
    cp -a "$backup_dir/tls-options.conf" "$tls_options"
    nginx -t && systemctl reload nginx
}
trap rollback ERR
install -m 644 "$source_dir/thhs.org.nz.conf" "$site"
install -m 644 "$source_dir/options-ssl-nginx.conf" "$tls_options"
nginx -t
systemctl reload nginx
trap - ERR

# Use the current snap Certbot, not the old apt client against the same state.
systemctl enable --now snap.certbot.renew.timer
systemctl disable --now certbot.timer
systemctl is-active nginx snap.certbot.renew.timer
printf 'Configuration deployed; rollback copies: %s\n' "$backup_dir"
