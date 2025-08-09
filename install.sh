#!/usr/bin/env bash
#
# PaperEcho installer (Linux: Debian/Ubuntu/Raspbian)
# - Creates venv
# - Installs requirements
# - Generates a systemd service with dynamic paths
# - Enables & starts the service
#
# Run from the project root:
#   bash scripts/install.sh
#
set -euo pipefail

# --- Resolve project info ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"   # this script is in ./scripts/, project root is one level up
PROJECT_NAME="PaperEcho"
SERVICE_NAME="paperecho.service"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"
PYTHON_BIN="python3"
VENV_DIR="${PROJECT_DIR}/venv"
VENV_PY="${VENV_DIR}/bin/python3"
REQUIREMENTS_FILE="${PROJECT_DIR}/requirements.txt"

# Use the invoking user for systemd User= (if run with sudo, prefer SUDO_USER)
RUN_USER="${SUDO_USER:-$USER}"

echo "📦 Project:        ${PROJECT_NAME}"
echo "📂 Project dir:    ${PROJECT_DIR}"
echo "👤 Service user:   ${RUN_USER}"
echo "⚙️  Service name:  ${SERVICE_NAME}"
echo

# --- Install system dependencies (Debian/Ubuntu/Raspbian) ---
echo "🧰 Installing system packages (sudo apt)…"
sudo apt update
sudo apt install -y \
  python3 python3-venv python3-pip \
  libjpeg-dev libopenjp2-7-dev \
  cups curl

# --- Python venv & dependencies ---
if [[ ! -d "$VENV_DIR" ]]; then
  echo "🐍 Creating virtual environment at ${VENV_DIR}…"
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

echo "📥 Installing Python requirements…"
"${VENV_PY}" -m pip install --upgrade pip
if [[ -f "${REQUIREMENTS_FILE}" ]]; then
  "${VENV_PY}" -m pip install -r "${REQUIREMENTS_FILE}"
else
  # Fallback in case requirements.txt is missing
  "${VENV_PY}" -m pip install flask escpos requests pillow
fi

# --- Ensure runtime folders exist ---
mkdir -p "${PROJECT_DIR}/static/uploads"
mkdir -p "${PROJECT_DIR}/print_output"

# --- Generate systemd unit with dynamic paths ---
echo "🧾 Writing systemd unit: ${SERVICE_PATH}"
TMP_UNIT="$(mktemp)"
cat > "${TMP_UNIT}" <<UNIT
[Unit]
Description=${PROJECT_NAME} Web Service
After=network.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${PROJECT_DIR}
ExecStart=${VENV_PY} ${PROJECT_DIR}/app.py
Restart=always
RestartSec=3
Environment=FLASK_ENV=production
# Optionally set PORT via env if you change it in app.py
# Environment=PORT=5000

[Install]
WantedBy=multi-user.target
UNIT

sudo mv "${TMP_UNIT}" "${SERVICE_PATH}"
sudo chmod 644 "${SERVICE_PATH}"

# --- Reload & enable service ---
echo "🔁 Reloading systemd and enabling service…"
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"

# --- Optional: add user to printer groups (non-fatal if groups absent) ---
if getent group lp >/dev/null 2>&1; then
  echo "👤 Adding ${RUN_USER} to 'lp' group (if not already)…"
  sudo usermod -aG lp "${RUN_USER}" || true
fi
if getent group lpadmin >/dev/null 2>&1; then
  echo "👤 Adding ${RUN_USER} to 'lpadmin' group (if not already)…"
  sudo usermod -aG lpadmin "${RUN_USER}" || true
fi

# --- Start service ---
echo "🚀 Starting ${SERVICE_NAME}…"
sudo systemctl restart "${SERVICE_NAME}"
sleep 1
sudo systemctl status --no-pager "${SERVICE_NAME}" || true

cat <<DONE

✅ ${PROJECT_NAME} installed.

Service:
  sudo systemctl status ${SERVICE_NAME}
  sudo systemctl restart ${SERVICE_NAME}
  sudo systemctl stop ${SERVICE_NAME}
  sudo systemctl disable ${SERVICE_NAME}

App URL (default):
  http://localhost:5000

Notes:
- The service uses the exact path you ran this script from:
    WorkingDirectory=${PROJECT_DIR}
    ExecStart=${VENV_PY} ${PROJECT_DIR}/app.py
- Update USB Vendor/Product IDs in your printer utils when you connect the printer.
- For testing without hardware, ensure "test_mode": true in config.json.
DONE
