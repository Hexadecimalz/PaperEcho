from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
import os
from printer import printer_utils as print_utils
from pathlib import Path
import json
from datetime import datetime
from flask import jsonify


UPLOAD_FOLDER = "static/uploads"
CONFIG_PATH = Path("config.json")

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

with open(CONFIG_PATH) as f:
    config = json.load(f)

def _read_cfg():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def _write_cfg(data):
    tmp = CONFIG_PATH.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, CONFIG_PATH)

@app.get("/settings/quote")
def get_quote_setting():
    cfg = _read_cfg()
    return jsonify({"quote_footer_enabled": bool(cfg.get("quote_footer_enabled", False))})

@app.post("/settings/quote")
def set_quote_setting():
    body = request.get_json(force=True) or {}
    val = bool(body.get("quote_footer_enabled", False))
    cfg = _read_cfg()
    cfg["quote_footer_enabled"] = val
    _write_cfg(cfg)
    return jsonify({"ok": True, "quote_footer_enabled": val})    


@app.route("/", methods=["GET"])
def index():
    success = request.args.get("success") == "true"
    return render_template("index.html", success=success)


@app.route("/submit", methods=["POST"])
def submit():
    form_type = request.form.get("formType")
    include_quote = request.form.get("include_quote") == "on"

    print(">>> Form submitted!")
    print("Form type:", form_type)
    print("Include quote:", include_quote)
    print("Full form data:", request.form)

    if form_type == "note":
        note = request.form.get("note_text", "").strip()
        print("Note content:", note)
        if note:
            print_utils.print_note(note, include_quote)

    elif form_type == "todo":
        todo = request.form.get("todo_text", "").strip()
        print("Todo content:", todo)
        if todo:
            print_utils.print_todo(todo, include_quote)

    elif form_type == "achievement":
        ach = request.form.get("achievement_text", "").strip()
        if ach:
            print_utils.print_achievement(ach, include_quote)

    elif form_type == "photo":
        photo = request.files.get("photo_file")
        if photo and photo.filename:
            filename = secure_filename(photo.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            photo.save(filepath)
            print_utils.print_image(filepath)

    return redirect(url_for("index", success="true"))


@app.route("/trigger/weather")
def trigger_weather():
    print_utils.print_weather_report()
    return "Weather printed!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
