# PaperEcho

A simple but flexible thermal printer web service for quick printing of notes, todos, achievements, photos, and more — straight from your browser. Inspired by the charm of physical printouts, PaperEcho makes your printer a little creativity companion.

## About 

This project was inspired by [ProjectScribe](https://github.com/UrbanCircles/scribe/tree/main). I was taken with the idea and presentation of the project. However, for me the project seemed way too complicated to just print something out. I liked the 3D printed design for the printer, but ultimately I wasn't going to do that. I just wanted to mimic the setup in my own way. I already had a Raspberry Pi, which I knew I could connect via USB to a thermal printer. 

I also wanted something simple but with additional functionality that Project Scribe's author hasn't provided. I used AI to generate all of the code and create something I really like for minimal effort. The idea of printing certain things and having this available via localhost on my phone works great for me. 

I ended up using my Pi 3 and this [Nucoun VCP-8370 printer](https://www.amazon.com/dp/B0CSDKHKT7). I think the total cost would likely be significantly more than Project Scribe's if I had to buy everything new. If I had to do it again I'd look for a quieter printer.

## 📦 Features

- **Web-based UI** (single-page) for submitting print jobs
  - Notes, todos, achievements, and photo uploads
  - Optional random quote footer (Tao Te Ching, Stoics, Fernando Pessoa, etc.)
  - Word-wrapped output for clean formatting
- **Automatic Weather Printing**
  - Configurable location, API key, and print time
  - Temperature, high, low, and condition text, each on its own line
- **Photo Printing**
  - Auto-resizes and dithers to printer width
  - Large images are capped in height to avoid buffer issues
- **Test Mode**
  - Simulates print output to console without sending to printer
- **Persistent Quote Rotation**
  - Prevents repeats until all quotes have been used
- **Systemd Service Ready**
  - Install and run on Linux-based systems (Raspbian, Ubuntu, etc.)
- **Portable**
  - No database — all config and data are file-based

---

## ⚙️ Installation

You must create a config.json from the example file in the source directory and modify with your settings. Generally the defaults should work for you.

```bash
# Clone the repo
git clone https://github.com/yourusername/PaperEcho.git
cd PaperEcho

# (Optional) Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install systemd service
sudo ./install.sh
```

**Uninstall:**
```bash
sudo ./install.sh --uninstall
```

---

## 🛠 Configuration

All settings are stored in `config.json` in the project root.

Example:

```json
{
  "weather_api_key": "YOUR_API_KEY",
  "weather_location": "Denver,US",
  "quote_footer_enabled": true,
  "test_mode": false,
  "printer_device": "/dev/usb/lp0",
  "cols": 42,
  "printer_width_px": 384,
  "max_image_height_px": 4096,
  "raster_chunk_rows": 160,
  "footer": "Printed on BPA Free Paper"
}
```

The footer option prints an optional footer message. This really just makes the receipts a little longer for me, since they were a little smalle in some cases. It prints an image located at `./static/images/separator.png` and then the footer message. If the footer option is not in the `config.json`, then no message will be printed. I also wanted to indicate that the receipted was BPA free, as I see some instances where I would give these attached to gift cards or something like that. 

---

## 🌤 Testing the Weather Feature

PaperEcho uses the [OpenWeatherMap API](https://openweathermap.org/api).

**Automatically print your weather via a crontab like this:** 

`0 7 * * * curl -s http://localhost:5000/trigger/weather > /dev/null`

**Manual weather check via `curl`:**
```bash
curl "https://api.openweathermap.org/data/2.5/weather?q=Denver,US&appid=YOUR_API_KEY&units=imperial"
```

**Trigger a print from the command line (local server must be running):**
```bash
# Trigger note print
curl -X POST -F "formType=note" -F "note_text=Hello world" -F "include_quote=false" http://localhost:5000/submit

# Trigger weather print
curl -X POST http://localhost:5000/print-weather
```

---

## 📂 Directory Structure

```
PaperEcho/
├── config.json
├── install.sh
├── printer/
│   ├── printer_utils.py
│   └── ...
├── quotes/
│   ├── quotes.tsv
│   └── .state.json  # ignored in git
├── static/
│   └── images/
│       └── favicon.ico
├── templates/
│   └── index.html
└── app.py
```

---

## Credits

- **[ProjectScribe](https://github.com/UrbanCircles/scribe/tree/main)** – inspiration for a minimal, beautiful thermal printer interface.
- Favicon emoji is from [favicon.io](https://favicon.io/emoji-favicons/ballot-box-with-ballot/) via Twemoji, which appears to no longer be in service. 
- ESC/POS printing powered by the [`python-escpos`](https://github.com/python-escpos/python-escpos) library.
- Quotes sourced from public domain works including:
  - *Tao Te Ching* (Laozi)
  - Stoic philosophers (Marcus Aurelius, Seneca, Epictetus)
  - Fernando Pessoa
- Word-wrap and image rasterization tuned for common 80mm thermal printers.


## TODO

 - Weather feature is lacking accuracy. Current temp seems fine, but high and low seems drastically incorrect. 
 - I want a custom title option. 
 - I want a better separator image.
 - Photo + Note 