# printer/print_utils.py

import os
import textwrap
from datetime import datetime
import requests
from escpos.printer import Usb
from pathlib import Path
import json

# Load config from project root
CONFIG_PATH = Path(__file__).resolve().parent.parent / 'config.json'
with open(CONFIG_PATH) as f:
    config = json.load(f)

TEST_OUTPUT_DIR = Path("print_output")
TEST_OUTPUT_DIR.mkdir(exist_ok=True)

QUOTES = [
    "You are capable of amazing things.",
    "Start where you are. Use what you have. Do what you can.",
    "Progress, not perfection.",
    "Dream big. Start small. Act now.",
    "Small steps every day."
]

def get_timestamp():
    return datetime.now().strftime("%a %b %-d %-I:%M %p")

def get_printer():
    if config.get("test_mode", False):
        return DummyPrinter()
    else:
        # Replace with your printer's actual Vendor/Product ID
        return Usb(0x04b8, 0x0e15, 0, 0x81, 0x03)

class DummyPrinter:
    def text(self, msg):
        with open(TEST_OUTPUT_DIR / "test_output.txt", "a") as f:
            f.write(msg + "\n")

    def image(self, image_path):
        with open(TEST_OUTPUT_DIR / "test_output.txt", "a") as f:
            f.write(f"[IMAGE PRINTED: {image_path}]\n")

    def cut(self):
        with open(TEST_OUTPUT_DIR / "test_output.txt", "a") as f:
            f.write("--- CUT ---\n\n")

def print_note(text, include_quote=False):
    print(">>> print_note() called")
    p = get_printer()
    p.text(get_timestamp() + "\n\n")
    p.text(textwrap.fill(text, width=32) + "\n\n")
    if include_quote and config.get("quote_footer_enabled", False):
        p.text("💡 " + random_quote() + "\n\n")
    p.cut()

def print_todo(markdown_text, include_quote=False):
    p = get_printer()
    p.text(get_timestamp() + "\n\n")
    for line in markdown_text.splitlines():
        if line.strip().startswith("- [ ]"):
            task = line.replace("- [ ]", "").strip()
            p.text(f"☐ {task}\n")
        elif line.strip().startswith("- [x]"):
            task = line.replace("- [x]", "").strip()
            p.text(f"✅ {task}\n")
    if include_quote and config.get("quote_footer_enabled", False):
        p.text("\n💡 " + random_quote())
    p.cut()

def print_image(image_path):
    p = get_printer()
    p.text(get_timestamp() + "\n\n")
    p.image(image_path)
    p.cut()

def print_weather_report():
    if not config.get("weather_enabled", False):
        return

    api_key = config.get("weather_api_key")
    location = config.get("weather_location")
    if not api_key or not location:
        return

    r = requests.get(
        "https://api.openweathermap.org/data/2.5/weather",
        params={"q": location, "units": "imperial", "appid": api_key},
        timeout=10
    )
    data = r.json()

    name = data["name"]
    temp = round(data["main"]["temp"])
    high = round(data["main"]["temp_max"])
    low = round(data["main"]["temp_min"])
    condition = data["weather"][0]["description"].capitalize()

    p = get_printer()
    p.text(get_timestamp() + "\n\n")
    p.text(f"📍 Weather for {name}\n")
    p.text(f"🌡️ {temp}°F (H:{high}° / L:{low}°)\n")
    p.text(f"☁️ {condition}\n\n")
    if config.get("quote_footer_enabled", False):
        p.text("💡 " + random_quote())
    p.cut()

def random_quote():
    import random
    return random.choice(QUOTES)
