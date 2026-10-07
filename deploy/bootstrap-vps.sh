#!/usr/bin/env bash
# ==============================================================================
# Ketrika Agri Market Intelligence - VPS Bootstrap Script
# Target OS: Ubuntu 24.04 LTS (Noble Numbat)
# ==============================================================================
set -euo pipefail

DEPLOY_USER="deploy"
APP_DIR="/opt/ketrika"

echo "=== [1/6] System updates and essential packages ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y
apt-get install -y --no-install-recommends \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    ufw \
    fail2ban \
    unattended-upgrades \
    git \
    jq \
    htop

echo "=== [2/6] Setup deploy user ==="
if id "${DEPLOY_USER}" &>/dev/null; then
    echo "User '${DEPLOY_USER}' already exists."
else
    adduser --disabled-password --gecos "" "${DEPLOY_USER}"
    echo "User '${DEPLOY_USER}' created."
fi

usermod -aG sudo "${DEPLOY_USER}"
echo "${DEPLOY_USER} ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/99-${DEPLOY_USER}"
chmod 0440 "/etc/sudoers.d/99-${DEPLOY_USER}"

# Copy root authorized_keys to deploy user if present
if [ -f /root/.ssh/authorized_keys ]; then
    mkdir -p "/home/${DEPLOY_USER}/.ssh"
    cp /root/.ssh/authorized_keys "/home/${DEPLOY_USER}/.ssh/authorized_keys"
    chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "/home/${DEPLOY_USER}/.ssh"
    chmod 700 "/home/${DEPLOY_USER}/.ssh"
    chmod 600 "/home/${DEPLOY_USER}/.ssh/authorized_keys"
fi

echo "=== [3/6] Install Docker Engine & Docker Compose ==="
install -m 0755 -d /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
fi

# shellcheck disable=SC1091
source /etc/os-release
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  ${VERSION_CODENAME} stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update -y
apt-get install -y --no-install-recommends \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin

usermod -aG docker "${DEPLOY_USER}"

echo "=== [4/6] Configure UFW Firewall ==="
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP Caddy'
ufw allow 443/tcp comment 'HTTPS Caddy'
ufw --force enable
ufw status verbose

echo "=== [5/6] Configure Fail2ban & Unattended Upgrades ==="
systemctl enable fail2ban
systemctl restart fail2ban

echo 'APT::Periodic::Update-Package-Lists "1";' > /etc/apt/apt.conf.d/20auto-upgrades
echo 'APT::Periodic::Unattended-Upgrade "1";' >> /etc/apt/apt.conf.d/20auto-upgrades
systemctl restart unattended-upgrades

echo "=== [6/6] Prepare application directory ==="
mkdir -p "${APP_DIR}"
chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "${APP_DIR}"
chmod 755 "${APP_DIR}"

echo "=============================================================================="
echo "VPS Bootstrap complete!"
echo "Target directory: ${APP_DIR} (owned by ${DEPLOY_USER})"
echo "Next steps: see docs/runbooks/deploy.md to configure .env and deploy the stack."
echo "=============================================================================="
