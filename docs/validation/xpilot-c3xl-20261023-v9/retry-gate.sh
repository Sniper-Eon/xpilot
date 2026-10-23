ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=10 -o ConnectionAttempts=1 comma@172.16.1.202 'hostname
cat /data/hardware_profile
readlink -f /data/openpilot
git -C /data/openpilot rev-parse HEAD
systemctl is-active comma.service'
