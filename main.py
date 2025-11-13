from flask import Flask, request, jsonify
import requests
import os
import re

app = Flask(__name__)

TOKEN = "8116602303:AAHuS7IZt5jivjG68XL3AIVAasCpUcZRLic"
PORT = int(os.getenv("PORT", "8080"))

# ========== Telegram ==========
def send_msg(chat, text):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                  json={"chat_id": chat, "text": text})

def send_video(chat, url):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendVideo",
                  json={"chat_id": chat, "video": url})

# ========== Universal Downloader API ==========
def universal_download(url):
    try:
        api = "https://api.ryzendesu.com/dlinsta"
        r = requests.post(api, json={"url": url}, timeout=15)
        js = r.json()

        if js.get("success") and "video" in js:
            return js["video"]

    except Exception as e:
        print("Downloader Error:", e)

    return None

# ========== Webhook ==========
@app.post("/webhook")
def webhook():
    update = request.json or {}
    msg = update.get("message")
    if not msg:
        return "ok"

    chat = msg["chat"]["id"]
    text = msg.get("text", "")

    if text.startswith("/start"):
        send_msg(chat,
            "🎬 أرسل أي رابط فيديو من:\n"
            "Instagram / TikTok / Facebook / YouTube / Pinterest / Twitter\n"
            "وسأقوم بتحميله لك 🔥")
        return "ok"

    links = re.findall(r"(https?://\S+)", text)
    if not links:
        return "ok"

    link = links[0]
    send_msg(chat, "⏳ جاري استخراج الفيديو...")

    video = universal_download(link)
    if video:
        send_video(chat, video)
    else:
        send_msg(chat, "❌ فشل التحميل!")

    return "ok"

# ========== Set Webhook ==========
@app.get("/set")
def set_hook():
    me = "https://" + request.host + "/webhook"
    r = requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook",
                     params={"url": me})
    return jsonify({"webhook": me, "reply": r.json()})

@app.get("/")
def home():
    return "🔥 Bot Running (Railway Optimized)"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
