#!/bin/sh
# Pull the post-migration counts off the live system into verified_counts.json,
# which gen_audit_report_v3.py renders into the workbook's Summary sheet.
# Usage: sh Migration/collect_verified_counts.sh
set -e
DIR=$(dirname "$0")
ssh VietUcUAT "sudo -u odoo psql vietuat -t -A -F'|' -f /tmp/final_verify.sql" \
  | python3 -c '
import sys, json
out = {}
for line in sys.stdin:
    line = line.strip()
    if not line or "|" not in line:
        continue
    key, val = line.split("|", 1)
    out[key.strip()] = val.strip()
json.dump(out, open("'"$DIR"'/verified_counts.json", "w"), indent=2)
print("wrote %d counts" % len(out))
'
