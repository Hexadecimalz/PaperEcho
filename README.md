# 🖨️ PaperEcho

This project was definitely inspired by [ProjectScribe](https://github.com/UrbanCircles/scribe/tree/main). I was taken with the idea and presentation of the project. However, for me the project seemed way too complicated to just print something out. The wiring diagrams didn't inspire confidence in what I've done before. I liked the 3D printed design for the printer, but ultimately I wasn't going to do that. I just wanted to mimic the setup in my own way. I already had a Raspberry Pi, which I knew I could connect via USB to a thermal printer. 

I also wanted something simple but with some additional functionality that Project Scribe's author hasn't provided. I used AI to generate all of the code and create something I really like for minimal effort. The idea of printing certain things and having this available via localhost on my phone works great for me. 

I ended up using my Pi 3 and this [Nucoun VCP-8370 printer](https://www.amazon.com/dp/B0CSDKHKT7). I think the total cost would likely be significantly more than Project Scribe's if I had to buy everything new, but I also like the flexibility of a lot more storage space and flexibility. There are trade offs to the minimalist design but I'm pretty happy with the final result.

## About 

A lightweight, mobile-first web interface for printing todo lists, notes, and photos on a thermal receipt printer. Designed for Raspberry Pi or any Linux-based system using [Flask](https://flask.palletsprojects.com/) and [python-escpos](https://python-escpos.readthedocs.io/).

---

## ✨ Features

- 📝 Write and print notes / achievements / todo lists
- 📷 Upload and print photos  
- 📅 Auto print daily weather forecast (7am by default)  
- 💡 Optional motivational quote footer  
- 🔄 Test mode for printer-less development  
- 📱 Touch-friendly UI using Alpine.js  
- 🔧 No login, local network ready  

---

## 📁 Folder Structure

```
paperecho/
├── app.py
├── install.sh
├── favicon.ico
├── config.json
├── printer/
│   └── print_utils.py
├── static/uploads/
├── static/images/favicon.ico # favicon for webpage
├── templates/
│   └── index.html
└── print_output/           # (Created if test_mode=true)
```

---

## ⚙️ Setup Instructions

### 1. Clone & Install

```bash
git clone https://github.com/YOURNAME/paperecho.git
cd paperecho
bash scripts/install.sh
```

### 2. Configure

Edit `config.json`:

```json
{
  "weather_api_key": "YOUR_API_KEY",
  "weather_location": "Denver,US",
  "weather_enabled": false,
  "weather_print_time": "07:00",
  "quote_footer_enabled": true,
  "test_mode": false,
  "printer_device": "/dev/usb/lp0",
  "cols": 42,
  "printer_width_px": 384,
  "max_image_height_px": 4096,
  "raster_chunk_rows": 160
}
```

> Set `"test_mode": false` when your printer is connected.

### 3. Start the Service

```bash
sudo systemctl start paperecho
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

## 🔌 Printer Setup Notes

- The USB vendor/product ID should be configured in `print_utils.py`
- Test mode logs to `print_output/test_output.txt`

---

## Credit 

- Favicon emoji is from [favicon.io](https://favicon.io/emoji-favicons/ballot-box-with-ballot/) via Twemoji, which appears to no longer be in service. 