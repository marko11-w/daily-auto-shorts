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

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
PORT = int(os.getenv("PORT") or "8080")

# ===== ملفات التخزين =====
BASE = Path(".")
USERS_FILE = BASE / "users.json"
STATS_FILE = BASE / "stats.json"

# ===== آيدي الأدمن =====
ADMIN_ID = 7758666677  # ← آيدي الأدمن الحقيقي

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
    stats["downloads"] = stats.get("downloads", 0) + 1
    save_stats(stats)

def tg_api(token):
    return f"https://api.telegram.org/bot{token}"

def send_message(token, chat_id, text, parse_mode=None):
    data = {"chat_id": chat_id, "text": text}
    if parse_mode:
        data["parse_mode"] = parse_mode
    requests.post(f"{tg_api(token)}/sendMessage", json=data)

def send_video(token, chat_id, url, caption=None):
    data = {"chat_id": chat_id, "video": url}
    if caption:
        data["caption"] = caption
    requests.post(f"{tg_api(token)}/sendVideo", json=data)

# =============================
#   تحميل إنستغرام API جديد
# =============================
def download_instagram(url):
    try:
        api = "https://snapinsta.io/wp-json/aio-dl/video-data/"
        r = requests.post(api, data={"url": url}, timeout=20).json()

        if "medias" in r and r["medias"]:
            return r["medias"][0]["src"]
    except Exception as e:
        log.error("Instagram error: %s", e)

    return None

# =============================
#   استخراج og:video لأي منصة
# =============================
HEADERS = {
    "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
}

def extract_video_url(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        html = r.text

        patterns = [
            r'property="og:video"\s+content="([^"]+)"',
            r"property='og:video'\s+content='([^']+)'",
            r'property="og:video:url"\s+content="([^"]+)"',
            r'property="og:video:secure_url"\s+content="([^"]+)"'
        ]

        for p in patterns:
            m = re.search(p, html)
            if m:
                return m.group(1).replace("&amp;", "&")

        return None
    except:
        return None

# =============================
#   تحديد المنصة
# =============================
def detect_platform(url):
    u = url.lower()

    # Instagram – أي رابط فيه كلمة instagram
    if "instagram.com" in u:
        return "Instagram"

    if "tiktok" in u or "tt." in u:
        return "TikTok"

    if "facebook" in u or "fb.watch" in u:
        return "Facebook"

    if "youtube" in u or "youtu.be" in u:
        return "YouTube"

    if "pinterest" in u or "pin.it" in u:
        return "Pinterest"

    return "Social"

# =============================
#   Webhook الأساسي
# =============================
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

    is_admin = (str(chat_id) == str(ADMIN_ID))

    # ======= أوامر الأدمن =======
    if text.startswith("/start") and is_admin:
        send_message(
            token, chat_id,
            "👑 مرحباً أدمن مارك!\n"
            "• /stats - الإحصائيات\n"
            "• /broadcast نص - إرسال جماعي\n\n"
            "أرسل أي رابط فيديو للتحميل 🎬"
        )
        return "ok"

    if text.startswith("/stats") and is_admin:
        users = load_users()
        stats = load_stats()
        send_message(
            token, chat_id,
            f"📊 إحصائيات البوت:\n"
            f"• المستخدمين: {len(users)}\n"
            f"• التحميلات: {stats['downloads']}"
        )
        return "ok"

    if text.startswith("/broadcast") and is_admin:
        msg_text = text.replace("/broadcast", "").strip()
        users = load_users()
        for uid in users:
            send_message(token, uid, msg_text)
        send_message(token, chat_id, "📢 تم إرسال الرسالة للجميع.")
        return "ok"

    # ======= للمستخدم العادي =======
    if text.startswith("/start"):
        send_message(
            token, chat_id,
            "📥 أرسل رابط فيديو من:\nTikTok / Instagram / Facebook / YouTube / Pinterest\nوسأقوم بتحميله لك 🎬"
        )
        return "ok"

    urls = re.findall(r"(https?://\S+)", text)
    if not urls:
        return "ok"

    link = urls[0]
    platform = detect_platform(link)

    send_message(token, chat_id, f"⏳ جاري المعالجة من {platform}...")

    # ===== Instagram =====
    if platform == "Instagram":
        url = download_instagram(link)
        if url:
            inc_downloads()
            send_video(token, chat_id, url, caption="تم تحميل فيديو Instagram ✔️")
        else:
            send_message(token, chat_id, "❌ لم أستطع تحميل فيديو Instagram")
        return "ok"

    # ===== مواقع أخرى =====
    dl = extract_video_url(link)
    if dl:
        inc_downloads()
        send_video(token, chat_id, dl, caption=f"تم التحميل من {platform} ✔️")
    else:
        send_message(token, chat_id, "❌ لم أستطع استخراج الفيديو!")

    return "ok"

# =============================
#   Webhook Setup
# =============================
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
