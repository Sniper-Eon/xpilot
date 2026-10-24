set -eu
ssh -o StrictHostKeyChecking=yes -o UpdateHostKeys=no -o BatchMode=yes -o ConnectTimeout=10 -o ConnectionAttempts=1 comma@172.16.1.202 'set -eu
test "$(hostname)" = comma-9c13c9f5
test -s /data/xpilot-X-20261023-16-evidence/final.jsonl
tar -czf - --exclude=xpilot-X-20261023-16-evidence/xpilot-plugins -C /data xpilot-X-20261023-16-evidence xpilot-ui-check-v9' > /private/tmp/X-20261023-16/device-evidence.tar.gz
mkdir -p /private/tmp/X-20261023-16/extracted
tar -xzf /private/tmp/X-20261023-16/device-evidence.tar.gz -C /private/tmp/X-20261023-16/extracted
