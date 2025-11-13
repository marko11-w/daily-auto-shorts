from flask import Flask, request, jsonify
import requests
import json
import re
import os
from pathlib import Path

app = Flask(__name__)

TOKEN = "8116602303:AAHuS7IZt5jivjG68XL3AIVAasCpUcZRLic"
PORT = int(os.getenv("PORT", "8080"))

BASE = Path(".")
USERS_FILE = BASE / "users.json"
STATS_FILE = BASE / "stats.json"

HEADERS = {"User-Agent": "Mozilla/5.0"}

# =============================
# تخزين بسيط
# =============================
def ensure_files():
    if not USERS_FILE.exists():
        USERS_FILE.write_text("[]")
    if not STATS_FILE.exists():
        STATS_FILE.write_text(json.dumps({"downloads": 0}, indent=2))

def add_user(uid):
    users = json.loads(USERS_FILE.read_text())
    if uid not in users:
        users.append(uid)
        USERS_FILE.write_text(json.dumps(users, indent=2))

def inc_download():
    st = json.loads(STATS_FILE.read_text())
    st["downloads"] += 1
    STATS_FILE.write_text(json.dumps(st, indent=2))


# =============================
# Telegram API
# =============================
def send_msg(chat_id, text):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": text}
    )

def send_video(chat_id, video_url):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendVideo",
        json={"chat_id": chat_id, "video": video_url}
    )


# =============================
# Instagram API (النهائية — شغالة 100%)
# =============================
def insta_download(url):
    try:
        api = "https://saveinsta.io/core/scrape"
        r = requests.post(api, data={"q": url}, timeout=10)
        js = r.json()

        # متعدد الوسائط
        if "medias" in js:
            for media in js["medias"]:
                if media.get("type") == "video" and media.get("url"):
                    return media["url"]

    except Exception as e:
        print("SaveInsta error:", e)

    return None


# =============================
# OG fallback (للتطبيقات الأخرى)
# =============================
def og_extract(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        html = r.text

        patterns = [
            r'property="og:video" content="([^"]+)"',
            r"property='og:video' content='([^']+)'",
            r'"contentUrl":"([^"]+)"'
        ]

        for p in patterns:
            m = re.search(p, html)
            if m:
                return m.group(1).replace("&amp;", "&")
    except:
        return None

    return None


# =============================
# Webhook
# =============================
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

    links = re.findall(r"(https?://\S+)", text)
    if not links:
        return "ok"

    link = links[0].rstrip(").,!?:;")

    send_msg(chat, "⏳ جاري استخراج الفيديو...")

    # ===== Instagram =====
    if "instagram" in link:
        vid = insta_download(link)
        if vid:
            inc_download()
            send_video(chat, vid)
        else:
            send_msg(chat, "❌ تعذر تحميل فيديو Instagram")
        return "ok"

    # ===== أي موقع آخر =====
    vid = og_extract(link)
    if vid:
        inc_download()
        send_video(chat, vid)
    else:
        send_msg(chat, "❌ لم أستطع استخراج الفيديو!")

    return "ok"


# =============================
# ضبط الويب هوك
# =============================
@app.get("/set")
def set_webhook():
    url = "https://" + request.host + "/webhook"
    r = requests.get(
        f"https://api.telegram.org/bot{TOKEN}/setWebhook",
        params={"url": url}
    )
    return jsonify({"webhook": url, "telegram_reply": r.json()})


@app.get("/")
def home():
    return "🔥 Bot Running!"


if __name__ == "__main__":
    ensure_files()
    app.run("0.0.0.0", PORT)
