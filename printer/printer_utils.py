from pathlib import Path
import os, json, time, unicodedata, re
from typing import Iterable

# ---------- Config ----------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config.json"

DEFAULTS = {
    "printer_device": "/dev/usb/lp0",
    "simulate": False,
    "include_quote": False,
    # columns at normal font (80mm printers are usually 42 or 48; 42 is safest)
    "cols": 42
}

def load_config():
    try:
        with open(CONFIG_PATH) as f:
            data = json.load(f)
    except Exception:
        data = {}
    merged = {**DEFAULTS, **data}
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
    Returns GS ! n where n packs width/height multipliers (1..8).
    e.g., double height/width => width_mul=2, height_mul=2
    """
    w = max(1, min(8, width_mul)) - 1
    h = max(1, min(8, height_mul)) - 1
    n = (w << 4) | h
    return GS + b"\x21" + bytes([n])

def set_codepage_cp437() -> bytes:
    """Most printers default fine; forcing CP437 avoids weird smart quotes."""
    return ESC + b"\x74\x00"  # 0 = USA, Standard Europe (CP437) on many models

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
    for para in text.splitlines() or [""]:
        words = re.findall(r"\S+|\s+", para)
        cur = ""
        for w in words:
            # if it's whitespace and fits, append; else start new line
            if w.isspace():
                if len(cur) + len(w) <= cols:
                    cur += w
                else:
                    lines.append(cur.rstrip())
                    cur = ""
                continue
            # word
            if len(cur.rstrip()) == 0:
                # start line with the word (even if it exceeds cols)
                cur = w
            elif len(cur) + len(w) <= cols:
                cur += w
            else:
                lines.append(cur.rstrip())
                cur = w
        if cur:
            lines.append(cur.rstrip())
        # paragraph break -> keep a blank line
        lines.append("")
    # remove trailing blank from last para if already blank
    if lines and lines[-1] == "":
        lines.pop()
    return lines

def date_line() -> str:
    # e.g. Sat Aug 9 2025 12:24 PM (no leading zeros on day/hour)
    tm = time.localtime()
    # %-d and %-I (Linux) drop leading zeros; fallback for systems without '-'
    try:
        return time.strftime("%a %b %-d %Y %-I:%M %p", tm)
    except Exception:
        s = time.strftime("%a %b %d %Y %I:%M %p", tm)
        # drop leading zero from day and hour manually
        s = re.sub(r"\b0(\d)\b", r"\1", s)
        return s

def encode_escpos(text: str) -> bytes:
    """
    Convert to CP437 to avoid smart-quote gibberish on most printers.
    Unknown chars become '?'.
    """
    clean = sanitize_text(text)
    return clean.encode("cp437", errors="replace")

# ---------- I/O ----------
def _write_raw(payload: bytes, device: str, simulate: bool):
    if simulate:
        print("[SIMULATE PRINT]", payload[:120], f"...({len(payload)} bytes)", flush=True)
        return
    with open(device, "wb", buffering=0) as f:
        f.write(payload)

def _header_block(title: str | None = None, big: bool = True) -> bytes:
    # Date line (centered)
    parts: list[bytes] = [INIT, set_codepage_cp437(), ALIGN_CENTER, char_size(1, 1)]
    parts.append(encode_escpos(date_line()))
    parts.append(b"\n")
    if title:
        if big:
            parts.append(BOLD_ON + char_size(2, 2))
        else:
            parts.append(BOLD_ON + char_size(1, 1))
        parts.append(encode_escpos(title))
        parts.append(BOLD_OFF + char_size(1, 1))
        parts.append(b"\n")
    # spacer
    parts.extend([b"\n", ALIGN_LEFT])
    return b"".join(parts)

def _body_block(text: str, cols: int) -> bytes:
    wrapped = wrap_text(text, cols)
    return b"".join(encode_escpos(line) + b"\n" for line in wrapped)

def _quote_block(enabled: bool) -> bytes:
    if not enabled:
        return b""
    q = '"Small steps beat grand plans."'
    return b"\n" + encode_escpos(q) + b"\n"

def _finalize() -> bytes:
    return b"\n\n" + CUT_PARTIAL

# ---------- Public API ----------
def _print_payload(chunks: Iterable[bytes]):
    cfg = load_config()
    dev = cfg["printer_device"]
    simulate = cfg.get("simulate", False)
    payload = b"".join(chunks)
    _write_raw(payload, dev, simulate)

def print_note(note: str, include_quote: bool):
    cfg = load_config()
    cols = int(cfg.get("cols", 42))
    chunks = [
        _header_block("NOTE", big=True),
        _body_block(note, cols),
        _quote_block(include_quote or cfg.get("include_quote", False)),
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
        _quote_block(include_quote or cfg.get("include_quote", False)),
        _finalize(),
    ]
    _print_payload(chunks)

def print_image(path: str):
    # Keep simple for now: just prints a header + filename; full raster later.
    cfg = load_config()
    cols = int(cfg.get("cols", 42))
    body = f"[PHOTO] {Path(path).name}\n(Preview disabled in this build)"
    chunks = [
        _header_block("PHOTO", big=True),
        _body_block(body, cols),
        _finalize(),
    ]
    _print_payload(chunks)

def print_weather_report():
    cfg = load_config()
    cols = int(cfg.get("cols", 42))
    body = "Temp: 72°F  High: 88°F  Low: 64°F\nClear skies"
    # Replace degree symbol in ASCII-safe way for CP437
    body = body.replace("°", " deg ")
    chunks = [
        _header_block("WEATHER", big=True),
        _body_block(body, cols),
        _finalize(),
    ]
    _print_payload(chunks)
