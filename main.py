#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import logging
from pathlib import Path

import requests
from flask import Flask, request, jsonify

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
log = logging.getLogger("mark_downloader")

app = Flask(__name__)

# ========= الإعدادات =========
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
PORT = int(os.getenv("PORT") or "8080")
ADMIN_ID = 7758666677   # ← آيدي الأدمن الحقيقي

# ========= ملفات التخزين =========
BASE = Path(".")
USERS_FILE = BASE / "users.json"
STATS_FILE = BASE / "stats.json"

def ensure_files():
    if not USERS_FILE.exists():
        USERS_FILE.write_text("[]", encoding="utf-8")
    if not STATS_FILE.exists():
        STATS_FILE.write_text(
            json.dumps({"downloads": 0}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

def load_users():
    try:
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except:
        return []

def save_users(users):
    USERS_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")

def add_user(uid):
    users = load_users()
    if uid not in users:
        users.append(uid)
        save_users(users)

def load_stats():
    try:
        return json.loads(STATS_FILE.read_text(encoding="utf-8"))
    except:
        return {"downloads": 0}

def save_stats(stats):
    STATS_FILE.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

def inc_downloads():
    stats = load_stats()
    stats["downloads"] += 1
    save_stats(stats)

# ========= دوال تلجرام =========
def tg_api(token):
    return f"https://api.telegram.org/bot{token}"

def send_message(token, chat_id, text):
    requests.post(
        f"{tg_api(token)}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=10
    )

def send_video(token, chat_id, url, caption=None):
    data = {"chat_id": chat_id, "video": url}
    if caption:
        data["caption"] = caption
    requests.post(f"{tg_api(token)}/sendVideo", json=data, timeout=20)

# ========= API Instagram =========
def download_instagram(url):
    try:
        api = "https://snapinsta.io/wp-json/aio-dl/video-data/"
        res = requests.post(api, data={"url": url}, timeout=20).json()

        if "medias" in res and res["medias"]:
            return res["medias"][0]["src"]
    except Exception as e:
        log.error("Instagram API error: %s", e)

    return None

# ========= محاولة استخراج og:video لأي منصة =========
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 12_0 like Mac OS X)"
}

def extract_video_url(url):
    try:
        html = requests.get(url, headers=HEADERS, timeout=15).text

        patterns = [
            r'property="og:video"\s+content="([^"]+)"',
            r"property='og:video'\s+content='([^']+)'",
            r'property="og:video:secure_url"\s+content="([^"]+)"'
        ]

        for p in patterns:
            match = re.search(p, html)
            if match:
                return match.group(1).replace("&amp;", "&")
    except:
        return None

    return None

# ========= تحديد المنصة =========
def detect_platform(url):
    lower = url.lower()

    if "instagram.com" in lower:
        return "Instagram"
    if "tiktok" in lower or "tt." in lower:
        return "TikTok"
    if "facebook" in lower or "fb.watch" in lower:
        return "Facebook"
    if "youtube" in lower or "youtu.be" in lower:
        return "YouTube"
    if "pinterest" in lower or "pin.it" in lower:
        return "Pinterest"

    return "Social"

# ========= Webhook =========
@app.post("/webhook/<token>")
def webhook(token):
    ensure_files()
    update = request.get_json(silent=True) or {}

    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return "ok"

    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    add_user(chat_id)

    is_admin = (chat_id == ADMIN_ID)

    # ===== أوامر الأدمن =====
    if text.startswith("/start") and is_admin:
        send_message(token, chat_id,
            "👑 مرحباً أدمن مارك!\n"
            "/stats — عرض الإحصائيات\n"
            "/broadcast — إرسال جماعي\n\n"
            "أرسل أي رابط فيديو للتحميل 🎬"
        )
        return "ok"

    if text.startswith("/stats") and is_admin:
        u = len(load_users())
        d = load_stats()["downloads"]
        send_message(token, chat_id, f"📊 الإحصائيات:\nالمستخدمون: {u}\nالتحميلات: {d}")
        return "ok"

    if text.startswith("/broadcast") and is_admin:
        msg_text = text.replace("/broadcast", "").strip()
        for uid in load_users():
            send_message(token, uid, msg_text)
        send_message(token, chat_id, "📢 تم الإرسال.")
        return "ok"

    # ===== المستخدم العادي =====
    if text.startswith("/start"):
        send_message(
            token, chat_id,
            "📥 أرسل رابط فيديو من:\nInstagram / TikTok / Facebook / YouTube / Pinterest\nوسأقوم بتحميله لك 🎬"
        )
        return "ok"

    urls = re.findall(r"(https?://\S+)", text)
    if not urls:
        return "ok"

    link = urls[0]
    platform = detect_platform(link)

    send_message(token, chat_id, f"⏳ جاري المعالجة من {platform}...")

    # Instagram
    if platform == "Instagram":
        url = download_instagram(link)
        if url:
            inc_downloads()
            send_video(token, chat_id, url, caption="✔️ Instagram Video")
        else:
            send_message(token, chat_id, "❌ فشل تحميل إنستغرام")
        return "ok"

    # Other platforms
    url = extract_video_url(link)
    if url:
        inc_downloads()
        send_video(token, chat_id, url, caption=f"✔️ Downloaded from {platform}")
    else:
        send_message(token, chat_id, "❌ لم أستطع استخراج الفيديو!")

    return "ok"

# ========= Set Webhook =========
@app.get("/set_webhook/<token>")
def set_webhook(token):
    base = WEBHOOK_URL or f"https://{request.host}"
    target = f"{base}/webhook/{token}"

    requests.get(f"{tg_api(token)}/deleteWebhook")
    r = requests.post(f"{tg_api(token)}/setWebhook", json={"url": target})

    return jsonify({"target": target, "response": r.json()})

@app.get("/")
def home():
    return "🔥 Mark Downloader is running!"

if __name__ == "__main__":
    ensure_files()
    app.run(host="0.0.0.0", port=PORT)
