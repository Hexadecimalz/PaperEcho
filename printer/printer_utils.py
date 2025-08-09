# printer/printer_utils.py
from __future__ import annotations

from pathlib import Path
import os, json, time, unicodedata, re, random
from typing import Iterable

# ---------- Config ----------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config.json"
QUOTES_PATH = PROJECT_ROOT / "quotes" / "quotes.txt"

DEFAULTS = {
    # existing keys
    "weather_api_key": "",
    "weather_location": "Denver,US",
    "weather_enabled": False,
    "weather_print_time": "07:00",
    "quote_footer_enabled": True,
    "test_mode": False,
    "printer_device": "/dev/usb/lp0",
    # new keys
    "cols": 42,
    "printer_width_px": 384,
    "max_image_height_px": 4096,
    "raster_chunk_rows": 160
}

def load_config() -> dict:
    try:
        with open(CONFIG_PATH) as f:
            data = json.load(f)
    except Exception:
        data = {}
    merged = {**DEFAULTS, **data}
    if os.getenv("PRINTER_DEVICE"):
        merged["printer_device"] = os.getenv("PRINTER_DEVICE")
    return merged

# ---------- ESC/POS ----------
ESC = b"\x1B"; GS = b"\x1D"
INIT = ESC + b"@"
ALIGN_LEFT   = ESC + b"\x61\x00"
ALIGN_CENTER = ESC + b"\x61\x01"
BOLD_ON  = ESC + b"\x45\x01"
BOLD_OFF = ESC + b"\x45\x00"
CUT_PARTIAL = GS + b"\x56\x41\x00"

def char_size(w: int = 1, h: int = 1) -> bytes:
    w = max(1, min(8, w)) - 1
    h = max(1, min(8, h)) - 1
    return GS + b"\x21" + bytes([(w << 4) | h])

def set_codepage_cp437() -> bytes:
    return ESC + b"\x74\x00"  # CP437 on most models

# ---------- Text helpers ----------
SMART_QUOTE_MAP = {
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "—": "-", "–": "-", "…": "...",
    "\u00A0": " ",
}
def sanitize_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    for k, v in SMART_QUOTE_MAP.items(): s = s.replace(k, v)
    return "".join(ch if (32 <= ord(ch) <= 126) or ch in "\n\t" else "?" for ch in s)

def wrap_text(text: str, cols: int) -> list[str]:
    lines: list[str] = []
    paras = text.splitlines() if "\n" in text else [text]
    for para in paras:
        words = re.findall(r"\S+|\s+", para)
        cur = ""
        for w in words:
            if w.isspace():
                if len(cur) + len(w) <= cols: cur += w
                else: lines.append(cur.rstrip()); cur = ""
                continue
            if not cur.strip(): cur = w
            elif len(cur) + len(w) <= cols: cur += w
            else: lines.append(cur.rstrip()); cur = w
        if cur: lines.append(cur.rstrip())
        lines.append("")
    if lines and lines[-1] == "": lines.pop()
    return lines

def date_line() -> str:
    tm = time.localtime()
    try:    return time.strftime("%a %b %-d %Y %-I:%M %p", tm)
    except: 
        s = time.strftime("%a %b %d %Y %I:%M %p", tm)
        return re.sub(r"\b0(\d)\b", r"\1", s)

def encode_escpos(text: str) -> bytes:
    return sanitize_text(text).encode("cp437", errors="replace")

# Quotes
def _load_quotes() -> list[str]:
    try:
        with open(QUOTES_PATH, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f]
        return [q for q in lines if q and not q.lstrip().startswith("#")]
    except FileNotFoundError:
        return []
def _random_quote() -> str | None:
    qs = _load_quotes()
    return random.choice(qs) if qs else None

# ---------- I/O ----------
def _write_raw(payload: bytes, device: str, simulate: bool):
    if simulate:
        print("[SIMULATE PRINT]", payload[:120], f"...({len(payload)} bytes)", flush=True); return
    with open(device, "wb", buffering=0) as f: f.write(payload)

# ---------- Layout blocks ----------
def _header_block(title: str | None = None, big_title: bool = True, show_date: bool = True) -> bytes:
    parts: list[bytes] = [INIT, set_codepage_cp437(), ALIGN_CENTER]
    # Big title first
    if title:
        parts += [BOLD_ON, char_size(2,2), encode_escpos(title), BOLD_OFF, char_size(1,1), b"\n"]
    # Smaller date UNDER the title
    if show_date:
        parts += [BOLD_ON, char_size(1,1), encode_escpos(date_line()), BOLD_OFF, b"\n"]
    # spacer + left align
    parts += [b"\n", ALIGN_LEFT]
    return b"".join(parts)

def _body_block(text: str, cols: int) -> bytes:
    return b"".join(encode_escpos(line) + b"\n" for line in wrap_text(text, cols))

def _quote_block(enabled: bool) -> bytes:
    if not enabled: return b""
    q = _random_quote() or "Small steps beat grand plans."
    q = sanitize_text(q)
    return b"\n" + encode_escpos(f"\"{q}\"") + b"\n"

def _finalize() -> bytes:
    return b"\n\n" + CUT_PARTIAL

def _print_payload(chunks: Iterable[bytes]):
    cfg = load_config()
    dev = cfg["printer_device"]
    simulate = cfg.get("test_mode", False)
    _write_raw(b"".join(chunks), dev, simulate)

# ---------- Public text APIs ----------
def print_note(note: str, include_quote: bool):
    cfg = load_config(); cols = int(cfg.get("cols", 42))
    chunks = [
        _header_block("NOTE", big_title=True, show_date=True),
        _body_block(note, cols),
        _quote_block(include_quote or cfg.get("quote_footer_enabled", False)),
        _finalize(),
    ]
    _print_payload(chunks)

def print_todo(todo: str, include_quote: bool):
    cfg = load_config(); cols = int(cfg.get("cols", 42))
    body = f"[ ] {todo}" if todo.strip() else ""  # avoid printing placeholder/empty
    chunks = [
        _header_block("TODO", big_title=True, show_date=True),
        _body_block(body, cols),
        _quote_block(include_quote or cfg.get("quote_footer_enabled", False)),
        _finalize(),
    ]
    _print_payload(chunks)

def print_achievement(text: str, include_quote: bool):
    cfg = load_config(); cols = int(cfg.get("cols", 42))
    body = f"* {text.strip()}"
    chunks = [
        _header_block("ACHIEVEMENT", big_title=True, show_date=True),
        _body_block(body, cols),
        _quote_block(include_quote or cfg.get("quote_footer_enabled", False)),
        _finalize(),
    ]
    _print_payload(chunks)

def print_weather_report():
    cfg = load_config(); cols = int(cfg.get("cols", 42))
    body = "Temp: 72 deg F  High: 88 deg F  Low: 64 deg F\nClear skies"
    chunks = [
        _header_block("WEATHER", big_title=True, show_date=True),
        _body_block(body, cols),
        _finalize(),
    ]
    _print_payload(chunks)

# ---------- Image printing ----------
def _to_mono_bitmap(path: str, target_width_px: int, max_height_px: int) -> "Image.Image":
    from PIL import Image, ImageOps
    img = Image.open(path); img = ImageOps.exif_transpose(img)
    w0, h0 = img.size
    scale = target_width_px / float(w0)
    new_w, new_h = target_width_px, max(1, int(round(h0 * scale)))
    img = img.resize((new_w, new_h))
    if max_height_px and new_h > max_height_px:
        scale2 = max_height_px / float(new_h)
        new_w2, new_h2 = max(1, int(round(new_w * scale2))), max_height_px
        img = img.resize((new_w2, new_h2)); new_w, new_h = img.size
        if new_w < target_width_px:
            canvas = Image.new("L", (target_width_px, new_h), 255)
            canvas.paste(img, ((target_width_px - new_w)//2, 0)); img = canvas
    return img.convert("1")

def _pack_bits_row(img, y: int) -> bytes:
    w, _ = img.size; out = bytearray(); byte = 0; bitpos = 7
    for x in range(w):
        if img.getpixel((x, y)) == 0: byte |= (1 << bitpos)
        bitpos -= 1
        if bitpos < 0: out.append(byte); byte = 0; bitpos = 7
    if bitpos != 7: out.append(byte)
    return bytes(out)

def _raster_chunk_cmd(img, y_start: int, rows: int) -> bytes:
    w, h = img.size
    rows = min(rows, h - y_start); row_bytes = (w + 7) // 8
    xL, xH = row_bytes & 0xFF, (row_bytes >> 8) & 0xFF
    yL, yH = rows & 0xFF, (rows >> 8) & 0xFF
    header = GS + b"v0" + b"\x00" + bytes([xL, xH, yL, yH])
    body = bytearray()
    for y in range(y_start, y_start + rows): body += _pack_bits_row(img, y)
    return header + bytes(body) + b"\n"

def print_image(path: str):
    cfg = load_config()
    dev = cfg["printer_device"]; simulate = cfg.get("test_mode", False)
    width_px = int(cfg.get("printer_width_px", 384))
    max_h = int(cfg.get("max_image_height_px", 4096))
    chunk_rows = int(cfg.get("raster_chunk_rows", 160))
    try:
        img = _to_mono_bitmap(path, target_width_px=width_px, max_height_px=max_h)
        chunks: list[bytes] = [INIT, set_codepage_cp437(), ALIGN_CENTER]
        h = img.size[1]; y = 0
        while y < h:
            rows = min(chunk_rows, h - y)
            chunks.append(_raster_chunk_cmd(img, y, rows)); y += rows
        chunks += [ALIGN_LEFT, b"\n\n", CUT_PARTIAL]
        _write_raw(b"".join(chunks), dev, simulate)
    except Exception as e:
        print(f"[print_image] ERROR: {e}", flush=True)
