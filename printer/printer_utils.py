# printer/printer_utils.py
from __future__ import annotations

from pathlib import Path
import os, json, time, unicodedata, re, random
from typing import Iterable
import requests  # <-- for OpenWeatherMap

# ---------- Paths / Config ----------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH  = PROJECT_ROOT / "config.json"
QUOTES_DIR   = PROJECT_ROOT / "quotes"
QUOTES_PATH  = QUOTES_DIR / "quotes.tsv"     # TSV: text \t author \t source(optional)
STATE_PATH   = QUOTES_DIR  / ".state.json"   # rotation state

DEFAULTS = {
    # existing keys you already use
    "weather_api_key": "",
    "weather_location": "Denver,US",
    "quote_footer_enabled": True,
    "test_mode": False,
    "printer_device": "/dev/usb/lp0",
    # new keys (safe defaults)
    "cols": 42,                  # body columns at normal size (common: 42 or 48)
    "printer_width_px": 384,     # image raster width; try 576 if supported
    "max_image_height_px": 4096, # cap super-tall images (0 = no cap)
    "raster_chunk_rows": 160,    # rows per chunk to avoid buffer overruns
    # optional units for weather: "imperial" or "metric"
    "weather_units": "imperial"
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

# ---------- ESC/POS Primitives ----------
ESC = b"\x1B"; GS = b"\x1D"

INIT = ESC + b"@"
ALIGN_LEFT   = ESC + b"\x61\x00"
ALIGN_CENTER = ESC + b"\x61\x01"
BOLD_ON      = ESC + b"\x45\x01"
BOLD_OFF     = ESC + b"\x45\x00"
CUT_PARTIAL  = GS  + b"\x56\x41\x00"  # GS V A 0 (partial cut)

def char_size(w: int = 1, h: int = 1) -> bytes:
    """GS ! n   (w,h in 1..8)"""
    w = max(1, min(8, w)) - 1
    h = max(1, min(8, h)) - 1
    return GS + b"\x21" + bytes([(w << 4) | h])

def set_codepage_cp437() -> bytes:
    """ESC t 0  (CP437 on most models)"""
    return ESC + b"\x74\x00"

# ---------- Text helpers ----------
SMART_MAP = {
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "—": "-", "–": "-", "…": "...",
    "\u00A0": " ",
}

def sanitize_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    for k, v in SMART_MAP.items():
        s = s.replace(k, v)
    # filter non-printables except \n and \t
    return "".join(ch if (32 <= ord(ch) <= 126) or ch in "\n\t" else "?" for ch in s)

def wrap_text(text: str, cols: int) -> list[str]:
    """Word-wrap without breaking words. Preserves paragraph breaks."""
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
    try:
        return time.strftime("%a %b %-d %Y %-I:%M %p", tm)
    except Exception:
        s = time.strftime("%a %b %d %Y %I:%M %p", tm)
        return re.sub(r"\b0(\d)\b", r"\1", s)  # drop leading zeros

def encode_escpos(text: str) -> bytes:
    return sanitize_text(text).encode("cp437", errors="replace")

# ---------- Quotes (rotation without repeats) ----------
def _ensure_quotes_dir():
    QUOTES_DIR.mkdir(parents=True, exist_ok=True)

def _load_quotes_tsv() -> list[dict]:
    """
    Read quotes.tsv as: text<TAB>author<TAB>source?
    Returns [{"text": str, "author": str|None, "source": str|None}, ...]
    """
    _ensure_quotes_dir()
    quotes = []
    try:
        with open(QUOTES_PATH, "r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln or ln.lstrip().startswith("#"):  # skip blanks/comments
                    continue
                parts = ln.split("\t")
                text   = parts[0].strip() if len(parts) > 0 else ""
                author = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
                source = parts[2].strip() if len(parts) > 2 and parts[2].strip() else None
                if text:
                    quotes.append({"text": text, "author": author, "source": source})
    except FileNotFoundError:
        pass
    return quotes

def _load_state() -> dict:
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_state(state: dict):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass

def _next_quote() -> dict | None:
    """
    Persistent shuffled rotation. No repeats until the cycle ends.
    Reshuffles automatically if the quotes file changes length.
    """
    quotes = _load_quotes_tsv()
    if not quotes:
        return None

    state = _load_state()
    if "order" not in state or "idx" not in state or state.get("n") != len(quotes):
        order = list(range(len(quotes)))
        random.shuffle(order)
        state = {"order": order, "idx": 0, "n": len(quotes)}
        _save_state(state)

    order = state["order"]; idx = state["idx"]; n = state["n"]
    if idx >= n:
        order = list(range(n))
        random.shuffle(order)
        idx = 0
    sel = quotes[order[idx]]
    state.update({"order": order, "idx": idx + 1})
    _save_state(state)
    return sel

# ---------- I/O ----------
def _write_raw(payload: bytes, device: str, simulate: bool):
    if simulate:
        print("[SIMULATE PRINT]", payload[:120], f"...({len(payload)} bytes)", flush=True)
        return
    with open(device, "wb", buffering=0) as f:
        f.write(payload)

# ---------- Layout blocks ----------
def _header_block(title: str | None = None, show_date: bool = True) -> bytes:
    """
    Big bold title (double size), then smaller bold date underneath.
    """
    chunks: list[bytes] = [INIT, set_codepage_cp437(), ALIGN_CENTER]
    if title:
        chunks += [BOLD_ON, char_size(2,2), encode_escpos(title), BOLD_OFF, char_size(1,1), b"\n"]
    if show_date:
        chunks += [BOLD_ON, encode_escpos(date_line()), BOLD_OFF, b"\n"]
    chunks += [b"\n", ALIGN_LEFT]
    return b"".join(chunks)

def _body_block(text: str, cols: int) -> bytes:
    return b"".join(encode_escpos(line) + b"\n" for line in wrap_text(text, cols))

def _quote_block(enabled: bool, footer_text: str = None) -> bytes:
    if not enabled:
        return b""
    q = _next_quote()
    if not q:
        return b""
    cfg = load_config()
    cols = int(cfg.get("cols", 42))

    text = f"\"{q['text']}\""
    by = []
    if q.get("author"):
        by.append(q["author"])
    if q.get("source"):
        by.append(q["source"])
    byline = (" — " + ", ".join(by)) if by else ""

    separator = ("- " * (cols // 2)).rstrip()

    wrapped = wrap_text(text, cols)
    if byline:
        wrapped += [""] + wrap_text(byline, cols)

    output_lines = ["", "", separator, ""] + wrapped
    result = b"".join(encode_escpos(line) + b"\n" for line in output_lines)
    return result

def _finalize() -> bytes:
    return b"\n\n" + CUT_PARTIAL

def _print_payload(chunks: Iterable[bytes]):
    cfg = load_config()
    dev = cfg["printer_device"]
    simulate = cfg.get("test_mode", False)  # map your key
    _write_raw(b"".join(chunks), dev, simulate)

# ---------- Weather (OpenWeatherMap) ----------
def _looks_like_coords(loc: str) -> bool:
    """Return True if string looks like 'lat,lon' numbers."""
    try:
        parts = [p.strip() for p in loc.split(",", 1)]
        if len(parts) != 2: return False
        float(parts[0]); float(parts[1])
        return True
    except Exception:
        return False

def fetch_weather_json() -> dict:
    cfg = load_config()
    key = (cfg.get("weather_api_key") or "").strip()
    loc = (cfg.get("weather_location") or "").strip()
    units = (cfg.get("weather_units") or "imperial").strip()  # "imperial" or "metric"

    if not key:
        raise RuntimeError("weather_api_key missing")
    if not loc:
        raise RuntimeError("weather_location missing")

    params = {"appid": key, "units": units}
    if _looks_like_coords(loc):
        lat, lon = [p.strip() for p in loc.split(",", 1)]
        params.update({"lat": lat, "lon": lon})
    else:
        params["q"] = loc

    r = requests.get("https://api.openweathermap.org/data/2.5/weather", params=params, timeout=8)
    r.raise_for_status()
    return r.json()

def print_weather_report():
    cfg = load_config()
    cols = int(cfg.get("cols", 42))
    units = (cfg.get("weather_units") or "imperial").strip()
    deg_label = "deg F" if units == "imperial" else "deg C"

    try:
        j = fetch_weather_json()
        name = j.get("name") or cfg.get("weather_location")
        main = j.get("main", {})
        wx   = (j.get("weather") or [{}])[0]
        temp = main.get("temp")
        tmin = main.get("temp_min")
        tmax = main.get("temp_max")
        desc = (wx.get("description") or "").title()

        # Round temps if numeric
        def _rnd(x): 
            try: return str(int(round(float(x))))
            except Exception: return str(x)

        # Build lines: Location, Condition, Temp, High, Low (each on its own line)
        lines = [
            f"{name}",
            f"{desc}" if desc else "",
            f"Temp: {_rnd(temp)} {deg_label}",
            f"High: {_rnd(tmax)} {deg_label}",
            f"Low:  {_rnd(tmin)} {deg_label}",
        ]
        body = "\n".join([ln for ln in lines if ln.strip()])

    except Exception as e:
        body = f"Weather error: {e}"

    chunks = [
        _header_block("WEATHER", show_date=True),
        _body_block(body, cols),
        _finalize(),
    ]
    _print_payload(chunks)

# ---------- Public text APIs ----------
def print_note(note: str, include_quote: bool, footer_text: str = None):
    cfg = load_config(); cols = int(cfg.get("cols", 42))
    chunks = [
        _header_block("NOTE", show_date=True),
        _body_block(note, cols),
        _quote_block(include_quote or cfg.get("quote_footer_enabled", False)),
    ]
    if (include_quote or cfg.get("quote_footer_enabled", False)) and footer_text:
        chunks.append(separator_and_footer_bytes(footer_text))
    chunks.append(_finalize())
    _print_payload(chunks)

def print_todo(todo: str, include_quote: bool, footer_text: str = None):
    cfg = load_config(); cols = int(cfg.get("cols", 42))
    body = f"{todo.strip()}" if todo and todo.strip() else ""
    chunks = [
        _header_block("TODO", show_date=True),
        _body_block(body, cols),
        _quote_block(include_quote or cfg.get("quote_footer_enabled", False)),
    ]
    if (include_quote or cfg.get("quote_footer_enabled", False)) and footer_text:
        chunks.append(separator_and_footer_bytes(footer_text))
    chunks.append(_finalize())
    _print_payload(chunks)

def print_achievement(text: str, include_quote: bool, footer_text: str = None):
    cfg = load_config(); cols = int(cfg.get("cols", 42))
    body = f"* {text.strip()}"
    chunks = [
        _header_block("New Achievement", show_date=True),
        _body_block(body, cols),
        _quote_block(include_quote or cfg.get("quote_footer_enabled", False)),
    ]
    if (include_quote or cfg.get("quote_footer_enabled", False)) and footer_text:
        chunks.append(separator_and_footer_bytes(footer_text))
    chunks.append(_finalize())
    _print_payload(chunks)

def separator_and_footer_bytes(footer_text: str) -> bytes:
    # Return bytes for separator image and centered footer text
    return print_image_centered_bytes('./static/images/separator.png') + print_centered_bytes(footer_text)

def print_image_centered_bytes(image_path: str) -> bytes:
    cfg = load_config()
    width_px = int(cfg.get("printer_width_px", 384))
    max_h = 200  # Separator image should be short
    chunk = int(cfg.get("raster_chunk_rows", 160))
    try:
        from PIL import Image, ImageOps
        img = _to_mono_bitmap(image_path, target_width_px=width_px, max_height_px=max_h)
        h = img.size[1]
        chunks: list[bytes] = [INIT, set_codepage_cp437(), ALIGN_CENTER]
        y = 0
        while y < h:
            rows = min(chunk, h - y)
            chunks.append(_raster_chunk_cmd(img, y, rows))
            y += rows
        chunks += [ALIGN_LEFT, b"\n"]
        return b"".join(chunks)
    except Exception as e:
        print(f"[print_image_centered_bytes] ERROR: {e}", flush=True)
        return b""

def print_centered_bytes(text: str) -> bytes:
    cfg = load_config()
    cols = int(cfg.get("cols", 42))
    # Use wrap_text to wrap and center each line
    lines = wrap_text(text, cols)
    centered_lines = []
    for line in lines:
        pad = max(0, (cols - len(line)) // 2)
        centered_lines.append(" " * pad + line)
    payload = b"".join(encode_escpos(line) + b"\n" for line in centered_lines) + b"\n"
    return INIT + set_codepage_cp437() + ALIGN_CENTER + payload + ALIGN_LEFT

# ---------- Image printing (ESC/POS raster, chunked) ----------
def _to_mono_bitmap(path: str, target_width_px: int, max_height_px: int) -> "Image.Image":
    """Open, EXIF-rotate, scale to width, cap height, dither to 1-bit."""
    from PIL import Image, ImageOps
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    w0, h0 = img.size
    scale = target_width_px / float(w0)
    new_w = target_width_px
    new_h = max(1, int(round(h0 * scale)))
    img = img.resize((new_w, new_h))
    if max_height_px and new_h > max_height_px:
        scale2 = max_height_px / float(new_h)
        new_w2 = max(1, int(round(new_w * scale2)))
        new_h2 = max_height_px
        img = img.resize((new_w2, new_h2))
        new_w, new_h = img.size
        if new_w < target_width_px:
            canvas = Image.new("L", (target_width_px, new_h), 255)
            canvas.paste(img, ((target_width_px - new_w)//2, 0))
            img = canvas
    return img.convert("1")  # 1-bit dither

def _pack_bits_row(img, y: int) -> bytes:
    w, _ = img.size
    out = bytearray()
    byte = 0; bitpos = 7
    for x in range(w):
        if img.getpixel((x, y)) == 0:
            byte |= (1 << bitpos)  # black dot on
        bitpos -= 1
        if bitpos < 0:
            out.append(byte); byte = 0; bitpos = 7
    if bitpos != 7:
        out.append(byte)
    return bytes(out)

def _raster_chunk_cmd(img, y_start: int, rows: int) -> bytes:
    """GS v 0 m xL xH yL yH + data for a band of rows (m=0)."""
    w, h = img.size
    rows = min(rows, h - y_start)
    row_bytes = (w + 7) // 8
    xL, xH = row_bytes & 0xFF, (row_bytes >> 8) & 0xFF
    yL, yH = rows & 0xFF, (rows >> 8) & 0xFF
    header = GS + b"v0" + b"\x00" + bytes([xL, xH, yL, yH])
    body = bytearray()
    for y in range(y_start, y_start + rows):
        body += _pack_bits_row(img, y)
    return header + bytes(body) + b"\n"  # LF after chunk helps some models

def print_image(path: str):
    cfg = load_config()
    dev     = cfg["printer_device"]
    simulate= cfg.get("test_mode", False)
    width_px= int(cfg.get("printer_width_px", 384))
    max_h   = int(cfg.get("max_image_height_px", 4096))
    chunk   = int(cfg.get("raster_chunk_rows", 160))
    try:
        img = _to_mono_bitmap(path, target_width_px=width_px, max_height_px=max_h)
        h = img.size[1]
        chunks: list[bytes] = [INIT, set_codepage_cp437(), ALIGN_CENTER]
        y = 0
        while y < h:
            rows = min(chunk, h - y)
            chunks.append(_raster_chunk_cmd(img, y, rows))
            y += rows
        chunks += [ALIGN_LEFT, b"\n\n", CUT_PARTIAL]
        _write_raw(b"".join(chunks), dev, simulate)
    except Exception as e:
        print(f"[print_image] ERROR: {e}", flush=True)
        _write_raw(b"".join(chunks), dev, simulate)
    except Exception as e:
        print(f"[print_image] ERROR: {e}", flush=True)
        print(f"[print_image] ERROR: {e}", flush=True)
        print(f"[print_image] ERROR: {e}", flush=True)
        print(f"[print_image] ERROR: {e}", flush=True)
