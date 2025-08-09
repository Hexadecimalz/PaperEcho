# 🖨️ PaperEcho

A lightweight, mobile-first web interface for printing todo lists, notes, and photos on a thermal receipt printer. Designed for Raspberry Pi or any Linux-based system using [Flask](https://flask.palletsprojects.com/) and [python-escpos](https://python-escpos.readthedocs.io/).

---

## ✨ Features

- 📝 Write and print notes  
- ✅ Submit markdown-formatted todo lists  
- 📷 Upload and print photos  
- 📅 Auto print daily weather forecast (7am by default)  
- 💡 Optional motivational quote footer  
- 🔄 Test mode for printer-less development  
- 📱 Touch-friendly UI using Alpine.js  
- 🔧 No login, local network ready  

---

## 📁 Folder Structure

```
thermal_printer_web/
├── app.py
├── config.json
├── printer/
│   └── print_utils.py
├── scripts/
│   └── install.sh
├── systemd/
│   └── thermal_printer_web.service
├── static/uploads/
├── templates/
│   └── index.html
└── print_output/           # (Created if test_mode=true)
```

---

## ⚙️ Setup Instructions

### 1. Clone & Install

```bash
git clone https://github.com/YOURNAME/thermal_printer_web.git
cd thermal_printer_web
bash scripts/install.sh
```

### 2. Configure

Edit `config.json`:

```json
{
  "weather_api_key": "YOUR_API_KEY",
  "weather_location": "Salt Lake City,US",
  "weather_enabled": true,
  "weather_print_time": "07:00",
  "quote_footer_enabled": true,
  "test_mode": true
}
```

> Set `"test_mode": false` when your printer is connected.

### 3. Start the Service

```bash
sudo systemctl start thermal_printer_web
```

App runs at: [http://localhost:5000](http://localhost:5000)

---

## 🕗 Daily Weather Auto-Print

Schedule with `cron`:

```bash
crontab -e
```

```cron
0 7 * * * curl -s http://localhost:5000/trigger/weather > /dev/null
```

Or use `weather_print_time` for a custom Python scheduler (not enabled by default).

---

## 💡 Example Markdown Todo

```
- [ ] Walk the dog
- [x] Drink water
- [ ] Write something inspiring
```

---

## 🔌 Printer Setup Notes

- The USB vendor/product ID should be configured in `print_utils.py`
- Test mode logs to `print_output/test_output.txt`

---

## 📷 Screenshots

(Insert mobile UI screenshots here)

---

## 📄 License

MIT
