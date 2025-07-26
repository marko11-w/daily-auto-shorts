import telebot
import openai
import json
import os
from flask import Flask, request
from config import BOT_TOKEN, OPENAI_API_KEY

bot = telebot.TeleBot(BOT_TOKEN)
openai.api_key = OPENAI_API_KEY

app = Flask(__name__)
print(f"🤖 BOT ACTIVE: {bot.get_me().username}")

USER_FILE = "user_progress.json"
if not os.path.exists(USER_FILE):
    with open(USER_FILE, "w") as f:
        json.dump({}, f)

def load_progress():
    with open(USER_FILE, "r") as f:
        return json.load(f)

def save_progress(data):
    with open(USER_FILE, "w") as f:
        json.dump(data, f)

def generate_lesson(n):
    prompt = f"اكتب الدرس رقم {n} من كورس تعلم الأمن السيبراني باللغة العربية، ويكون شاملاً ومفصلاً للطلاب المبتدئين، مع أمثلة واضحة."
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    data = load_progress()

    if user_id not in data:
        data[user_id] = 1
    else:
        data[user_id] += 1

    lesson_number = data[user_id]
    bot.send_message(message.chat.id, f"⏳ جاري إنشاء الدرس {lesson_number}، الرجاء الانتظار...")

    try:
        lesson = generate_lesson(lesson_number)
        bot.send_message(message.chat.id, f"📘 الدرس {lesson_number}:\n\n{lesson}")
        save_progress(data)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ حدث خطأ أثناء توليد الدرس:\n{str(e)}")

@app.route("/", methods=["GET"])
def index():
    return "✅ Bot is running.", 200

@app.route("/", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "ok", 200

WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
if WEBHOOK_URL:
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
