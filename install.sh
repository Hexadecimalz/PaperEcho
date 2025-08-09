#!/usr/bin/env bash

set -e

# sudo usermod -aG lp,lpadmin $USER

echo "🧰 Installing system dependencies..."
sudo apt update
sudo apt install -y python3 python3-pip python3-venv libjpeg-dev libopenjp2-7-dev cups


echo "🐍 Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "📦 Installing Python packages..."
pip install flask escpos requests pillow

echo "📂 Ensuring upload and print_output folders..."
mkdir -p static/uploads
mkdir -p print_output

echo "🖨️ If using USB thermal printer, ensure correct Vendor/Product ID in print_utils.py"
echo "🛠️ Setting up systemd service..."
sudo cp systemd/thermal_printer_web.service /etc/systemd/system/
sudo systemctl daemon-reexec
sudo systemctl daemon-reload
sudo systemctl enable thermal_printer_web.service
echo "✅ Done. You can now run: sudo systemctl start thermal_printer_web"
