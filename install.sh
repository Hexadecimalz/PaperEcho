#!/usr/bin/env bash
#
# PaperEcho Installer / Uninstaller (Debian/Ubuntu/Raspbian)
# Place this file in the project root (alongside app.py, config.json).
#
# Usage:
#   bash install.sh               # install/upgrade service
#   bash install.sh --uninstall   # stop/disable/remove service
#
set -euo pipefail

PROJECT_NAME="PaperEcho"
SERVICE_NAME="paperecho.service"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"

# Resolve project directory as the directory containing this script
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${PROJECT_DIR}/venv"
VENV_PY="${VENV_DIR}/bin/python3"
REQ_FILE="${PROJECT_DIR}/requirements.txt"
RUN_USER="${SUDO_USER:-$USER}"

# ---- Helpers ---------------------------------------------------------------

usage() {
  cat <<USAGE
${PROJECT_NAME} installer

Usage:
  $(basename "$0")            Install or upgrade the service
  $(basename "$0") --uninstall  Stop, disable, and remove the service

This script must live in the project root. Detected project dir:
  ${PROJECT_DIR}
USAGE
}

require_root_ops() {
  if ! command -v sudo >/dev/null 2>&1; then
    echo "This script requires 'sudo' for systemd operations." >&2
    exit 1
  fi
}

write_unit() {
  local tmp
  tmp="$(mktemp)"
  cat > "${tmp}" <<UNIT
[Unit]
Description=${PROJECT_NAME} Web Service
After=network.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_USER}
SupplementaryGroups=lp
WorkingDirectory=${PROJECT_DIR}
ExecStart=${VENV_PY} ${PROJECT_DIR}/app.py
Environment=FLASK_ENV=production
Environment=PYTHONUNBUFFERED=1
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
  sudo mv "${tmp}" "${SERVICE_PATH}"
  sudo chmod 0644 "${SERVICE_PATH}"
}

stop_disable_remove_unit() {
  require_root_ops
  sudo gpasswd -d "$USER" lp
  sudo gpasswd -d "$USER" dialout
  if systemctl list-unit-files | grep -q "^${SERVICE_NAME}\b"; then
    sudo systemctl stop "${SERVICE_NAME}" || true
    sudo systemctl disable "${SERVICE_NAME}" || true
  fi
  if [[ -f "${SERVICE_PATH}" ]]; then
    sudo rm -f "${SERVICE_PATH}"
  fi
  sudo systemctl daemon-reload
}

install_system_packages() {
  echo "🧰 Installing system packages (apt)…"
  sudo apt update
  sudo apt install -y \
    python3 python3-venv python3-pip \
    libjpeg-dev libopenjp2-7-dev \
    cups curl
}

create_venv_and_install_python_reqs() {
  if [[ ! -d "${VENV_DIR}" ]]; then
    echo "🐍 Creating virtual environment at: ${VENV_DIR}"
    python3 -m venv "${VENV_DIR}"
  fi

  echo "📥 Installing Python requirements…"
  "${VENV_PY}" -m pip install --upgrade pip

  if [[ -f "${REQ_FILE}" ]]; then
    "${VENV_PY}" -m pip install -r "${REQ_FILE}"
  else
    # Fallback if requirements.txt is missing
    "${VENV_PY}" -m pip install flask escpos requests pillow
  fi
}

prepare_runtime_dirs() {
  mkdir -p "${PROJECT_DIR}/static/uploads"
  mkdir -p "${PROJECT_DIR}/print_output"
}

enable_and_start() {
  sudo usermod -aG lp,dialout $USER
  sudo systemctl daemon-reload
  sudo systemctl enable "${SERVICE_NAME}"
  sudo systemctl restart "${SERVICE_NAME}"
  sleep 1
  sudo systemctl status --no-pager "${SERVICE_NAME}" || true
}

# ---- Uninstall Mode --------------------------------------------------------

if [[ "${1:-}" == "--uninstall" ]]; then
  echo "🧹 Uninstalling ${PROJECT_NAME} service…"
  stop_disable_remove_unit
  echo "✅ Uninstalled. (Virtualenv and project files left intact at ${PROJECT_DIR})"
  exit 0
fi

# ---- Install / Upgrade -----------------------------------------------------

# Basic sanity check
if [[ ! -f "${PROJECT_DIR}/app.py" ]]; then
  echo "❌ app.py not found in ${PROJECT_DIR}."
  echo "Make sure you are running this script from the project root."
  usage
  exit 1
fi

echo "📦 Project:        ${PROJECT_NAME}"
echo "📂 Project dir:    ${PROJECT_DIR}"
echo "👤 Service user:   ${RUN_USER}"
echo "⚙️  Service name:  ${SERVICE_NAME}"
echo

install_system_packages
create_venv_and_install_python_reqs
prepare_runtime_dirs

echo "🧾 Writing systemd unit with dynamic paths:"
echo "    WorkingDirectory=${PROJECT_DIR}"
echo "    ExecStart=${VENV_PY} ${PROJECT_DIR}/app.py"
write_unit

# Optional: add user to printing groups if present (non-fatal)
if getent group lp >/dev/null 2>&1; then
  echo "👥 Adding ${RUN_USER} to 'lp' group (if needed)…"
  sudo usermod -aG lp "${RUN_USER}" || true
fi
if getent group lpadmin >/dev/null 2>&1; then
  echo "👥 Adding ${RUN_USER} to 'lpadmin' group (if needed)…"
  sudo usermod -aG lpadmin "${RUN_USER}" || true
fi

echo "🚀 Enabling and starting ${SERVICE_NAME}…"
enable_and_start

cat <<POST
✅ ${PROJECT_NAME} installed.

Service commands:
  sudo systemctl status ${SERVICE_NAME}
  sudo systemctl restart ${SERVICE_NAME}
  sudo systemctl stop ${SERVICE_NAME}
  sudo systemctl disable ${SERVICE_NAME}

Uninstall:
  bash $(basename "$0") --uninstall

Notes:
- Service uses the exact path of this project directory.
- Ensure config.json exists in ${PROJECT_DIR}.
- For testing without hardware, set "test_mode": true in config.json.
- Default URL: http://localhost:5000
POST
