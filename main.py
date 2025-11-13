from flask import Flask, request, jsonify
import requests
import re
import json
from pathlib import Path
import os

app = Flask(__name__)

TOKEN = "8116602303:AAHuS7IZt5jivjG68XL3AIVAasCpUcZRLic"
PORT = int(os.getenv("PORT", "8080"))

BASE = Path(".")
USERS_FILE = BASE / "users.json"
STATS_FILE = BASE / "stats.json"

HEADERS = {"User-Agent": "Mozilla/5.0"}

# --------------------------
# ملفات التخزين
# --------------------------
def ensure_files():
    if not USERS_FILE.exists():
        USERS_FILE.write_text("[]")
    if not STATS_FILE.exists():
        STATS_FILE.write_text(json.dumps({"downloads": 0}, indent=2))

def load_users():
    try:
        return json.loads(USERS_FILE.read_text())
    except:
        return []

def add_user(uid):
    u = load_users()
    if uid not in u:
        u.append(uid)
        USERS_FILE.write_text(json.dumps(u, indent=2))

def load_stats():
    try:
        return json.loads(STATS_FILE.read_text())
    except:
        return {"downloads": 0}

def inc_download():
    s = load_stats()
    s["downloads"] += 1
    STATS_FILE.write_text(json.dumps(s, indent=2))


# --------------------------
# Telegram API
# --------------------------
def send_msg(chat, text):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": chat, "text": text}
    )

def send_video(chat, url):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendVideo",
        json={"chat_id": chat, "video": url}
    )


# --------------------------
# Instagram API NEW (Strong)
# --------------------------
def instagram_download(url):
    try:
        api = "https://api.sssinstagram.com/api/instagram/media"
        r = requests.post(api, json={"url": url}, timeout=10)
        js = r.json()

        # مسار الفيديو
        if "media" in js and len(js["media"]) > 0:
            return js["media"][0]["src"]

    except Exception as e:
        print("Instagram error:", e)

    return None


# --------------------------
# OG extractor fallback
# --------------------------
def og_extract(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        html = r.text

        patterns = [
            r'property="og:video" content="([^"]+)"',
            r"'og:video' content='([^']+)'",
            r'"contentUrl":"([^"]+)"'
        ]

        for p in patterns:
            m = re.search(p, html)
            if m:
                return m.group(1).replace("&amp;", "&")
    except:
        return None
    return None


# --------------------------
# Webhook Handler
# --------------------------
@app.post("/webhook")
def webhook():
    ensure_files()
    update = request.json or {}

    msg = update.get("message")
    if not msg:
        return "ok"

    chat = msg["chat"]["id"]
    text = msg.get("text", "")

    add_user(chat)

    if text.startswith("/start"):
        send_msg(chat,
            "🎬 أرسل أي رابط فيديو من:\n"
            "Instagram / TikTok / Facebook / YouTube / Pinterest / Twitter / Threads\n"
            "وسأقوم بتحميله لك 🔥"
        )
        return "ok"

    # استخراج رابط
    links = re.findall(r"(https?://\S+)", text)
    if not links:
        return "ok"

    link = links[0].rstrip(").,!?:;")

    send_msg(chat, "⏳ جاري استخراج الفيديو...")

    # Instagram
    if "instagram" in link or "ig.me" in link:
        vid = instagram_download(link) or og_extract(link)
        if vid:
            inc_download()
            send_video(chat, vid)
        else:
            send_msg(chat, "❌ تعذر تحميل فيديو Instagram")
        return "ok"

    # Other sites
    vid = og_extract(link)
    if vid:
        inc_download()
        send_video(chat, vid)
    else:
        send_msg(chat, "❌ لم أستطع استخراج الفيديو!")

    return "ok"


# --------------------------
# Set webhook (Railway)
# --------------------------
@app.get("/set")
def set_webhook():
    domain = "https://" + request.host
    webhook_url = f"{domain}/webhook"

    r = requests.get(
        f"https://api.telegram.org/bot{TOKEN}/setWebhook",
        params={"url": webhook_url}
    )

    return jsonify({"webhook": webhook_url, "telegram_reply": r.json()})


@app.get("/")
def home():
    return "🔥 Bot Running!"


if __name__ == "__main__":
    ensure_files()
    app.run(host="0.0.0.0", port=PORT)
