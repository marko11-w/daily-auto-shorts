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

# ========== إعداد الملفات ==========
BASE = Path(".")
USERS_FILE = BASE / "users.json"
STATS_FILE = BASE / "stats.json"

# ========== آيدي الأدمن ==========
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
    except Exception:
        return []

def save_users(users):
    USERS_FILE.write_text(
        json.dumps(users, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

def add_user(user_id: int):
    users = load_users()
    if user_id not in users:
        users.append(user_id)
        save_users(users)

def load_stats():
    try:
        return json.loads(STATS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"downloads": 0}

def save_stats(stats):
    STATS_FILE.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

def inc_downloads():
    stats = load_stats()
    stats["downloads"] = stats.get("downloads", 0) + 1
    save_stats(stats)

def tg_api(token: str) -> str:
    return f"https://api.telegram.org/bot{token}"

def send_message(token: str, chat_id: int, text: str, parse_mode=None):
    data = {"chat_id": chat_id, "text": text}
    if parse_mode:
        data["parse_mode"] = parse_mode
    requests.post(f"{tg_api(token)}/sendMessage", json=data)

def send_video(token: str, chat_id: int, url: str, caption=None):
    data = {"chat_id": chat_id, "video": url}
    if caption:
        data["caption"] = caption
    r = requests.post(f"{tg_api(token)}/sendVideo", json=data)
    if not r.json().get("ok"):
        log.error("sendVideo error: %s", r.text)

HEADERS = {
    "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
}

def extract_video_url(page_url: str) -> str | None:
    try:
        resp = requests.get(page_url, headers=HEADERS, timeout=15)
        html = resp.text

        patterns = [
            r'property="og:video"\s+content="([^"]+)"',
            r"property='og:video'\s+content='([^']+)'",
            r'property="og:video:url"\s+content="([^"]+)"',
            r'property="og:video:secure_url"\s+content="([^"]+)"',
        ]

        for p in patterns:
            m = re.search(p, html)
            if m:
                return m.group(1).replace("&amp;", "&")

        return None
    except Exception as e:
        log.exception("extract_video_url error: %s", e)
        return None

def detect_platform(url: str) -> str:
    u = url.lower()
    if "tiktok" in u: return "TikTok"
    if "instagram" in u: return "Instagram"
    if "facebook" in u or "fb.watch" in u: return "Facebook"
    if "youtube" in u or "youtu.be" in u: return "YouTube"
    if "pinterest" in u or "pin.it" in u: return "Pinterest"
    return "Social"

# ========= Routes =========

@app.get("/")
def home():
    return "🚀 Mark Downloader is running!"

@app.post("/webhook/<token>")
def webhook(token):
    ensure_files()
    update = request.get_json(silent=True) or {}

    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return "ok"

    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    # حفظ المستخدم
    add_user(chat_id)

    is_admin = (str(chat_id) == str(ADMIN_ID))

    # ===== أوامر الأدمن =====
    if text.startswith("/start") and is_admin:
        send_message(
            token, chat_id,
            "👑 مرحباً أدمن مارك!\n"
            "• /stats — عرض الإحصائيات\n"
            "• /broadcast نص — إرسال رسالة جماعية\n\n"
            "أرسل رابط أي فيديو للتحميل 🎬"
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
        if not msg_text:
            send_message(token, chat_id, "❗ اكتب الرسالة بعد الأمر.")
            return "ok"

        users = load_users()
        for uid in users:
            send_message(token, uid, msg_text)

        send_message(token, chat_id, "📢 تم إرسال الرسالة للجميع.")
        return "ok"

    # ===== للمستخدم العادي =====
    if text.startswith("/start"):
        send_message(
            token,
            chat_id,
            "📥 أرسل رابط فيديو من TikTok / Instagram / Facebook / YouTube / Pinterest\n"
            "وسأقوم بتحميله لك 🎬"
        )
        return "ok"

    # معالجة الروابط
    urls = re.findall(r"(https?://\S+)", text)
    if not urls:
        return "ok"

    link = urls[0]
    platform = detect_platform(link)
    send_message(token, chat_id, f"⏳ جاري المعالجة من {platform}...")

    video_url = extract_video_url(link)
    if not video_url:
        send_message(token, chat_id, "❌ لم أستطع استخراج الفيديو!")
        return "ok"

    inc_downloads()
    send_video(token, chat_id, video_url, caption=f"تم التحميل من {platform} ✔️")

    return "ok"

@app.get("/set_webhook/<token>")
def set_webhook(token):
    base = WEBHOOK_URL or f"https://{request.host}"
    target = f"{base}/webhook/{token}"

    requests.get(f"{tg_api(token)}/deleteWebhook")
    r = requests.post(f"{tg_api(token)}/setWebhook", json={"url": target})

    return jsonify({"target": target, "response": r.json()})

@app.get("/get_info/<token>")
def get_info(token):
    r = requests.get(f"{tg_api(token)}/getWebhookInfo")
    return jsonify(r.json())

if __name__ == "__main__":
    ensure_files()
    app.run(host="0.0.0.0", port=PORT)
