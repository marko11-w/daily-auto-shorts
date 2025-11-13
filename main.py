from flask import Flask, request, jsonify
import requests
import re
import json
import logging
from pathlib import Path
import os

app = Flask(__name__)

# ---------------------------------------
# إعدادات
# ---------------------------------------
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))
PORT = int(os.getenv("PORT", "8080"))

BASE = Path(".")
USERS_FILE = BASE / "users.json"
STATS_FILE = BASE / "stats.json"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("downloader")

# ---------------------------------------
# ملفات التخزين
# ---------------------------------------
def ensure_files():
    if not USERS_FILE.exists():
        USERS_FILE.write_text("[]", encoding="utf-8")
    if not STATS_FILE.exists():
        STATS_FILE.write_text(json.dumps({"downloads": 0}, indent=2), encoding="utf-8")

def load_users():
    try:
        return json.loads(USERS_FILE.read_text())
    except:
        return []

def save_users(users):
    USERS_FILE.write_text(json.dumps(users, indent=2))

def add_user(uid):
    users = load_users()
    if uid not in users:
        users.append(uid)
        save_users(users)

def load_stats():
    try:
        return json.loads(STATS_FILE.read_text())
    except:
        return {"downloads": 0}

def inc_downloads():
    st = load_stats()
    st["downloads"] += 1
    STATS_FILE.write_text(json.dumps(st, indent=2))


# ---------------------------------------
# Telegram API
# ---------------------------------------
def tg_api(token):
    return f"https://api.telegram.org/bot{token}"

def send_msg(token, chat_id, text):
    requests.post(f"{tg_api(token)}/sendMessage",
                  json={"chat_id": chat_id, "text": text})

def send_video(token, chat_id, url):
    requests.post(f"{tg_api(token)}/sendVideo",
                  json={"chat_id": chat_id, "video": url})


# ---------------------------------------
# استخراج الفيديو بأي طريقة
# ---------------------------------------
HEADERS = {"User-Agent": "Mozilla/5.0"}

def og_extract(url):
    """استخراج og:video لأي منصة."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if not r.ok:
            return None

        html = r.text

        patterns = [
            r'property="og:video"\s+content="([^"]+)"',
            r"property='og:video'\s+content='([^']+)'",
            r'"contentUrl":"([^"]+)"'
        ]

        for p in patterns:
            m = re.search(p, html)
            if m:
                return m.group(1).replace("&amp;", "&")

    except Exception as e:
        log.error("OG Extract error: %s", e)

    return None


def insta_api(url):
    """مصدر بديل لإنستغرام"""
    try:
        api = "https://snapinsta.io/wp-json/aio-dl/video-data/"
        r = requests.post(api, data={"url": url}, timeout=10)
        js = r.json()
        if "medias" in js:
            return js["medias"][0]["src"]
    except:
        return None


# ---------------------------------------
# تحديد المنصة
# ---------------------------------------
def detect(url):
    u = url.lower()
    if "instagram" in u or "ig.me" in u:
        return "instagram"
    if "tiktok" in u or "tt." in u:
        return "tiktok"
    if "facebook" in u or "fb.watch" in u:
        return "facebook"
    if "youtube" in u or "youtu.be" in u:
        return "youtube"
    if "pinterest" in u or "pin.it" in u:
        return "pinterest"
    if "twitter" in u or "x.com" in u:
        return "twitter"
    if "threads.net" in u:
        return "threads"
    return "other"


# ---------------------------------------
# Webhook
# ---------------------------------------
@app.post("/webhook/<token>")
def webhook(token):
    ensure_files()
    update = request.json or {}

    msg = update.get("message")
    if not msg:
        return "ok"
    
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")
    add_user(chat_id)

    # أمر البدء
    if text.startswith("/start"):
        send_msg(token, chat_id,
                 "🎬 أرسل أي رابط فيديو من:\n"
                 "Instagram / TikTok / Facebook / YouTube / Pinterest / Twitter / Threads\n"
                 "وسأحمّله لك مباشرة 👌")
        return "ok"

    # استخراج رابط
    links = re.findall(r"(https?://\S+)", text)
    if not links:
        return "ok"

    url = links[0].rstrip(").,!?;")

    platform = detect(url)
    send_msg(token, chat_id, f"⏳ جاري المعالجة ({platform})...")

    # Instagram
    if platform == "instagram":
        vid = insta_api(url) or og_extract(url)
        if vid:
            inc_downloads()
            send_video(token, chat_id, vid)
        else:
            send_msg(token, chat_id, "❌ فشل التحميل من Instagram")
        return "ok"

    # All other platforms
    vid = og_extract(url)
    if vid:
        inc_downloads()
        send_video(token, chat_id, vid)
    else:
        send_msg(token, chat_id, "❌ لم أستطع استخراج الفيديو!")

    return "ok"


# ---------------------------------------
# ضبط Webhook
# ---------------------------------------
@app.get("/set/<token>")
def set_hook(token):
    me = request.host_url.strip("/")
    target = f"{me}/webhook/{token}"
    r = requests.get(f"https://api.telegram.org/bot{token}/setWebhook",
                     params={"url": target})
    return jsonify({"webhook": target, "telegram_reply": r.json()})


@app.get("/")
def home():
    return "🔥 Video Downloader Bot Is Running!"


if __name__ == "__main__":
    ensure_files()
    app.run(host="0.0.0.0", port=PORT)
