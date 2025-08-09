# printer/printer_utils.py
from __future__ import annotations

from pathlib import Path
import os, json, time, unicodedata, re
from typing import Iterable

# ---------- Config ----------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config.json"

DEFAULTS = {
    # — existing keys you already have —
    "weather_api_key": "",
    "weather_location": "Denver,US",
    "weather_enabled": False,
    "weather_print_time": "07:00",
    "quote_footer_enabled": True,
    "test_mode": False,
    "printer_device": "/dev/usb/lp0",

    # — new keys (safe defaults) —
    "cols": 42,                   # body text columns at normal size (common: 42 or 48)
    "printer_width_px": 384,      # image raster width; try 576 if your printer supports it
    "max_image_height_px": 4096,  # cap super-tall images (0 = no cap)
    "raster_chunk_rows": 160      # rows per raster chunk to avoid buffer overruns
}

def load_config() -> dict:
    try:
        with open(CONFIG_PATH) as f:
            data = json.load(f)
    except Exception:
        data = {}
    # merge without renaming old keys
    merged = {**DEFAULTS, **data}
    # env override for device if set
    if os.getenv("PRINTER_DEVICE"):
        merged["printer_device"] = os.getenv("PRINTER_DEVICE")
    return merged

# ---------- ESC/POS Primitives ----------
ESC = b"\x1B"
GS  = b"\x1D"

INIT = ESC + b"@"
ALIGN_LEFT   = ESC + b"\x61\x00"
ALIGN_CENTER = ESC + b"\x61\x01"
ALIGN_RIGHT  = ESC + b"\x61\x02"
BOLD_ON  = ESC + b"\x45\x01"
BOLD_OFF = ESC + b"\x45\x00"
CUT_PARTIAL = GS + b"\x56\x41\x00"  # GS V A 0

def char_size(width_mul: int = 1, height_mul: int = 1) -> bytes:
    """
    GS ! n  (n packs width/height multipliers; each is 1..8)
    """
    w = max(1, min(8, width_mul)) - 1
    h = max(1, min(8, height_mul)) - 1
    n = (w << 4) | h
    return GS + b"\x21" + bytes([n])

def set_codepage_cp437() -> bytes:
    # ESC t n; 0 is CP437 on most models
    return ESC + b"\x74\x00"

# ---------- Text helpers ----------
SMART_QUOTE_MAP = {
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "—": "-", "–": "-", "…": "...",
    "\u00A0": " ",
}

def sanitize_text(s: str) -> str:
    # normalize + replace smart punctuation with ASCII equivalents
    s = unicodedata.normalize("NFKC", s)
    for k, v in SMART_QUOTE_MAP.items():
        s = s.replace(k, v)
    # strip other non-printables
    s = "".join(ch if (32 <= ord(ch) <= 126) or ch in "\n\t" else "?" for ch in s)
    return s

def wrap_text(text: str, cols: int) -> list[str]:
    """
    Word-wrap without breaking words. Preserves newlines as paragraph breaks.
    """
    lines: list[str] = []
    paras = text.splitlines() if "\n" in text else [text]
    for para in paras:
        words = re.findall(r"\S+|\s+", para)
        cur = ""
        for w in words:
            if w.isspace():
                if len(cur) + len(w) <= cols:
                    cur += w
                else:
                    lines.append(cur.rstrip())
                    cur = ""
                continue
            # word
            wlen = len(w)
            if not cur.strip():
                cur = w if wlen <= cols else w  # long words overflow gracefully (no hyphenation)
            elif len(cur) + wlen <= cols:
                cur += w
            else:
                lines.append(cur.rstrip())
                cur = w
        if cur:
            lines.append(cur.rstrip())
        # paragraph break -> keep a blank line
        lines.append("")
    if lines and lines[-1] == "":
        lines.pop()
    return lines

def date_line() -> str:
    # e.g. Sat Aug 9 2025 12:24 PM (no leading zeros on day/hour if platform supports %-)
    tm = time.localtime()
    try:
        return time.strftime("%a %b %-d %Y %-I:%M %p", tm)
    except Exception:
        s = time.strftime("%a %b %d %Y %I:%M %p", tm)
        # drop leading zeros from day/hour
        s = re.sub(r"\b0(\d)\b", r"\1", s)
        return s

def encode_escpos(text: str) -> bytes:
    clean = sanitize_text(text)
    return clean.encode("cp437", errors="replace")

# ---------- I/O ----------
def _write_raw(payload: bytes, device: str, simulate: bool):
    if simulate:
        print("[SIMULATE PRINT]", payload[:120], f"...({len(payload)} bytes)", flush=True)
        return
    with open(device, "wb", buffering=0) as f:
        f.write(payload)

# ---------- Layout blocks ----------
def _header_block(title: str | None = None, big: bool = True) -> bytes:
    parts: list[bytes] = [INIT, set_codepage_cp437(), ALIGN_CENTER]

    # Big, bold date
    parts.append(BOLD_ON + char_size(2, 2))
    parts.append(encode_escpos(date_line()))
    parts.append(BOLD_OFF + char_size(1, 1) + b"\n")

    # Optional big title
    if title:
        parts.append(BOLD_ON + (char_size(2, 2) if big else char_size(1, 1)))
        parts.append(encode_escpos(title))
        parts.append(BOLD_OFF + char_size(1, 1))
        parts.append(b"\n")

    # Spacer and left align for body
    parts.extend([b"\n", ALIGN_LEFT])
    return b"".join(parts)

def _body_block(text: str, cols: int) -> bytes:
    wrapped = wrap_text(text, cols)
    return b"".join(encode_escpos(line) + b"\n" for line in wrapped)

def _quote_block(enabled: bool, quote_text: str | None = None) -> bytes:
    if not enabled:
        return b""
    q = quote_text or '"Small steps beat grand plans."'
    q = sanitize_text(q)
    return b"\n" + encode_escpos(q) + b"\n"

def _finalize() -> bytes:
    return b"\n\n" + CUT_PARTIAL

def _print_payload(chunks: Iterable[bytes]):
    cfg = load_config()
    dev = cfg["printer_device"]
    simulate = cfg.get("test_mode", False)  # map your existing key
    payload = b"".join(chunks)
    _write_raw(payload, dev, simulate)

# ---------- Public text APIs ----------
def print_note(note: str, include_quote: bool):
    cfg = load_config()
    cols = int(cfg.get("cols", 42))
    chunks = [
        _header_block("NOTE", big=True),
        _body_block(note, cols),
        _quote_block(include_quote or cfg.get("quote_footer_enabled", False)),
        _finalize(),
    ]
    _print_payload(chunks)

def print_todo(todo: str, include_quote: bool):
    cfg = load_config()
    cols = int(cfg.get("cols", 42))
    body = f"[ ] {todo}"
    chunks = [
        _header_block("TODO", big=True),
        _body_block(body, cols),
        _quote_block(include_quote or cfg.get("quote_footer_enabled", False)),
        _finalize(),
    ]
    _print_payload(chunks)

def print_weather_report():
    # Stub formatting (ties into your future weather fetch)
    cfg = load_config()
    cols = int(cfg.get("cols", 42))
    body = "Temp: 72 deg F  High: 88 deg F  Low: 64 deg F\nClear skies"
    chunks = [
        _header_block("WEATHER", big=True),
        _body_block(body, cols),
        _finalize(),
    ]
    _print_payload(chunks)

# ---------- Image printing ----------
def _to_mono_bitmap(path: str, target_width_px: int, max_height_px: int) -> "Image.Image":
    """
    Open image, auto-rotate using EXIF, scale to target width, cap max height,
    convert to 1-bit with Floyd–Steinberg dithering.
    """
    from PIL import Image, ImageOps

    img = Image.open(path)
    img = ImageOps.exif_transpose(img)  # respect EXIF orientation

    # Scale to target width (maintain aspect)
    w0, h0 = img.size
    scale = target_width_px / float(w0)
    new_w = target_width_px
    new_h = max(1, int(round(h0 * scale)))
    img = img.resize((new_w, new_h))

    # Cap height if configured
    if max_height_px and new_h > max_height_px:
        scale2 = max_height_px / float(new_h)
        new_w2 = max(1, int(round(new_w * scale2)))
        new_h2 = max_height_px
        img = img.resize((new_w2, new_h2))
        new_w, new_h = img.size
        # If width changed due to height cap, letterbox to printer width
        if new_w < target_width_px:
            canvas = Image.new("L", (target_width_px, new_h), 255)
            xoff = (target_width_px - new_w) // 2
            canvas.paste(img, (xoff, 0))
            img = canvas

    # Grayscale -> 1-bit (dither)
    img = img.convert("1")  # Pillow uses Floyd–Steinberg dithering here
    return img

def _pack_bits_row(img, y: int) -> bytes:
    """
    Pack one row of a 1-bit PIL image into bytes, MSB-first in each byte.
    """
    w, _ = img.size
    out = bytearray()
    byte = 0
    bitpos = 7
    for x in range(w):
        # In mode '1', pixel values are 0 or 255; treat 0 (black) as 'dot on'
        pixel_on = (img.getpixel((x, y)) == 0)
        if pixel_on:
            byte |= (1 << bitpos)
        bitpos -= 1
        if bitpos < 0:
            out.append(byte)
            byte = 0
            bitpos = 7
    if bitpos != 7:
        out.append(byte)
    return bytes(out)

def _raster_chunk_cmd(img, y_start: int, rows: int) -> bytes:
    """
    GS v 0 m xL xH yL yH + data for a band of rows, where:
      row_bytes = ceil(width / 8)
      xL/xH = row_bytes (little-endian)
      yL/yH = rows in this chunk
      m = 0 (normal)
    """
    w, h = img.size
    rows = min(rows, h - y_start)
    row_bytes = (w + 7) // 8

    xL = row_bytes & 0xFF
    xH = (row_bytes >> 8) & 0xFF
    yL = rows & 0xFF
    yH = (rows >> 8) & 0xFF

    header = GS + b"v0" + b"\x00" + bytes([xL, xH, yL, yH])

    body = bytearray()
    for y in range(y_start, y_start + rows):
        body += _pack_bits_row(img, y)

    # Some printers like a LF after each chunk
    return header + bytes(body) + b"\n"

def print_image(path: str):
    """
    Proper ESC/POS raster print using GS v 0, chunked to avoid buffer issues.
    Scales to printer_width_px and optionally caps height.
    """
    cfg = load_config()
    dev = cfg["printer_device"]
    simulate = cfg.get("test_mode", False)
    width_px = int(cfg.get("printer_width_px", 384))
    max_h = int(cfg.get("max_image_height_px", 4096))
    chunk_rows = int(cfg.get("raster_chunk_rows", 160))

    try:
        img = _to_mono_bitmap(path, target_width_px=width_px, max_height_px=max_h)

        # Build payload: center image, emit in chunks, then cut
        chunks: list[bytes] = [INIT, set_codepage_cp437(), ALIGN_CENTER]
        h = img.size[1]
        y = 0
        while y < h:
            rows = min(chunk_rows, h - y)
            chunks.append(_raster_chunk_cmd(img, y, rows))
            y += rows
        chunks.extend([ALIGN_LEFT, b"\n\n", CUT_PARTIAL])

        _write_raw(b"".join(chunks), dev, simulate)
    except Exception as e:
        print(f"[print_image] ERROR: {e}", flush=True)
