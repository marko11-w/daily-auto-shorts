from flask import Flask, request, jsonify
import requests
import re
import json
from pathlib import Path
import os

app = Flask(__name__)

# ---------------------------------------
# إعدادات عامة
# ---------------------------------------
TOKEN = "8116602303:AAHuS7IZt5jivjG68XL3AIVAasCpUcZRLic"
PORT = int(os.getenv("PORT", "8080"))

BASE = Path(".")
USERS_FILE = BASE / "users.json"
STATS_FILE = BASE / "stats.json"

HEADERS = {"User-Agent": "Mozilla/5.0"}

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
def tg(method, data=None):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    requests.post(url, json=data)

def send_msg(chat_id, text):
    tg("sendMessage", {"chat_id": chat_id, "text": text})

def send_video(chat_id, video_url):
    tg("sendVideo", {"chat_id": chat_id, "video": video_url})


# ---------------------------------------
# استخراج الفيديو بأي طريقة
# ---------------------------------------
def og_extract(url):
    """استخراج og:video لأي منصة"""
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

    except:
        return None

    return None


# Instagram API fallback
def insta_api(url):
    try:
        api = "https://snapinsta.io/wp-json/aio-dl/video-data/"
        r = requests.post(api, data={"url": url}, timeout=10)
        js = r.json()
        if "medias" in js:
            return js["medias"][0]["src"]
    except:
        return None


# ---------------------------------------
# Webhook
# ---------------------------------------
@app.post("/webhook")
def webhook():
    ensure_files()
    update = request.json or {}

    msg = update.get("message")
    if not msg:
        return "ok"

    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    add_user(chat_id)

    if text.startswith("/start"):
        send_msg(chat_id,
                 "🎬 أرسل أي رابط فيديو من:\n"
                 "Instagram / TikTok / Facebook / YouTube / Pinterest / Twitter / Threads\n"
                 "وسأقوم بتحميله لك 🔥")
        return "ok"

    links = re.findall(r"(https?://\S+)", text)
    if not links:
        return "ok"

    url = links[0].rstrip(").,!?;")

    send_msg(chat_id, "⏳ جاري استخراج الفيديو...")

    # Instagram
    if "instagram" in url or "ig.me" in url:
        vid = insta_api(url) or og_extract(url)
        if vid:
            inc_downloads()
            send_video(chat_id, vid)
        else:
            send_msg(chat_id, "❌ تعذر تحميل فيديو Instagram")
        return "ok"

    # باقي المنصات
    vid = og_extract(url)
    if vid:
        inc_downloads()
        send_video(chat_id, vid)
    else:
        send_msg(chat_id, "❌ لم أستطع استخراج الفيديو!")

    return "ok"


# ---------------------------------------
# ضبط Webhook (نسخة Railway)
# ---------------------------------------
@app.get("/set")
def set_hook():
    domain = "https://" + request.host
    webhook_url = f"{domain}/webhook"

    r = requests.get(
        f"https://api.telegram.org/bot{TOKEN}/setWebhook",
        params={"url": webhook_url}
    )

    return jsonify({"webhook": webhook_url, "telegram_reply": r.json()})


@app.get("/")
def home():
    return "🔥 Video Downloader Bot Running!"


if __name__ == "__main__":
    ensure_files()
    app.run(host="0.0.0.0", port=PORT)
