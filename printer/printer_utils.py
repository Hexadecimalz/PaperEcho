from pathlib import Path
import os
import json
from PIL import Image  # pip install pillow
import time

# --- config ---
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config.json"

DEFAULTS = {
    "printer_device": "/dev/usb/lp0",
    "simulate": False,
    "include_quote": False,
    "weather_time": "07:00",
}

def load_config():
    try:
        with open(CONFIG_PATH) as f:
            data = json.load(f)
    except Exception:
        data = {}
    merged = {**DEFAULTS, **data}
    # allow env override
    dev = os.getenv("PRINTER_DEVICE")
    if dev:
        merged["printer_device"] = dev
    return merged

def _write_raw(payload: bytes, device: str):
    cfg = load_config()
    if cfg.get("simulate", False):
        print("[SIMULATE PRINT] bytes:", payload[:80], f"...({len(payload)} bytes total)", flush=True)
        return
    # write raw to device
    with open(device, "wb", buffering=0) as f:
        f.write(payload)

# --- basic esc/pos helpers ---
LF = b"\n"
CUT_PARTIAL = b"\x1D\x56\x41\x00"     # GS V A 0
CENTER = b"\x1B\x61\x01"
LEFT = b"\x1B\x61\x00"
BOLD_ON = b"\x1B\x45\x01"
BOLD_OFF = b"\x1B\x45\x00"

def _text_block(lines: list[str]) -> bytes:
    return ("\n".join(lines) + "\n\n").encode("utf-8")

def _print_lines(lines: list[str]):
    cfg = load_config()
    dev = cfg["printer_device"]
    payload = _text_block(lines) + CUT_PARTIAL
    _write_raw(payload, dev)

def print_note(note: str, include_quote: bool):
    try:
        lines = []
        lines.append((CENTER + BOLD_ON + b"NOTE" + BOLD_OFF + LEFT).decode("latin1"))
        lines.append(note)
        if include_quote or load_config().get("include_quote", False):
            lines.append("")
            lines.append("“Stay focused. Ship it.”")
        _print_lines(lines)
    except Exception as e:
        print(f"[print_note] ERROR: {e}", flush=True)

def print_todo(todo: str, include_quote: bool):
    try:
        lines = []
        lines.append((CENTER + BOLD_ON + b"TODO" + BOLD_OFF + LEFT).decode("latin1"))
        lines.append(f"[ ] {todo}")
        if include_quote or load_config().get("include_quote", False):
            lines.append("")
            lines.append("“Small steps > grand plans.”")
        _print_lines(lines)
    except Exception as e:
        print(f"[print_todo] ERROR: {e}", flush=True)

def print_image(path: str):
    """
    Super-simple image print: rasterize to ~384px wide (typical 80mm head),
    convert to mono dither, and send as ASCII art blocks (quick & dirty).
    For proper graphics, wire up python-escpos' image() later if desired.
    """
    try:
        cfg = load_config()
        dev = cfg["printer_device"]

        img = Image.open(path).convert("L")
        # 80mm printers are ~576 px wide at 203dpi; many safe at 384
        target_w = 384
        w, h = img.size
        new_h = int(h * (target_w / w))
        img = img.resize((target_w, new_h)).convert("1")  # mono

        # pack bits per row to bytes
        # ESC * m nL nH d... (older) or GS v 0 (raster). Keep minimal: use rows as text art fallback.
        # Minimal: translate to blocks just to verify path works
        lines = ["[PHOTO] " + Path(path).name, ""]
        # crude preview line count (don’t spam long photos)
        preview = min(30, img.size[1])
        for y in range(preview):
            row = ""
            for x in range(img.size[0]):
                row += "@" if img.getpixel((x, y)) == 0 else " "
            lines.append(row)
        lines.append("")
        lines.append("(photo preview)")
        payload = _text_block(lines) + CUT_PARTIAL
        _write_raw(payload, dev)

        # TODO: replace with real ESC/POS raster for full image printing later.
    except Exception as e:
        print(f"[print_image] ERROR: {e}", flush=True)

def print_weather_report():
    try:
        # Stub—replace with your actual weather fetch/format
        ts = time.strftime("%Y-%m-%d %H:%M")
        lines = [
            (CENTER + BOLD_ON + b"WEATHER" + BOLD_OFF + LEFT).decode("latin1"),
            f"As of {ts}",
            "Temp: 72°F  High: 88°F  Low: 64°F",
            "Clear skies ☀️",
        ]
        _print_lines(lines)
    except Exception as e:
        print(f"[print_weather_report] ERROR: {e}", flush=True)
