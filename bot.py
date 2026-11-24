import os
import requests
import threading
import time

from flask import Flask, jsonify

app = Flask(__name__)

# === НАСТРОЙКИ ===
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

chat_history = {}

def get_groq_response(user_message, chat_id):
    if chat_id not in chat_history:
        chat_history[chat_id] = [
            {"role": "system", "content": "Ты — личный помощник Сани. Отвечай по делу, помогай с настройками, ищи информацию. Отвечай на русском языке."}
        ]

    chat_history[chat_id].append({"role": "user", "content": user_message})

    if len(chat_history[chat_id]) > 11:
        chat_history[chat_id] = [chat_history[chat_id][0]] + chat_history[chat_id][-10:]

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": chat_history[chat_id],
        "temperature": 0.7,
        "max_tokens": 1024
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(GROQ_URL, json=payload, headers=headers)

    if response.status_code == 200:
        answer = response.json()["choices"][0]["message"]["content"]
        chat_history[chat_id].append({"role": "assistant", "content": answer})
        return answer
    else:
        return f"Ошибка Groq: {response.status_code}"

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    max_len = 4096
    for i in range(0, len(text), max_len):
        chunk = text[i:i+max_len]
        requests.post(url, json={
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "Markdown"
        })

def poll_telegram():
    last_update_id = 0

    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=30"
            response = requests.get(url, timeout=35)

            if response.status_code == 200:
                updates = response.json().get("result", [])

                for update in updates:
                    last_update_id = update["update_id"]

                    if "message" in update and "text" in update["message"]:
                        chat_id = update["message"]["chat"]["id"]
                        user_text = update["message"]["text"]

                        if user_text == "/start":
                            send_telegram_message(chat_id, "👋 Привет, Саня! Я твой личный помощник. Задай любой вопрос — я помогу!")
                            continue

                        answer = get_groq_response(user_text, chat_id)
                        send_telegram_message(chat_id, answer)

        except Exception as e:
            print(f"Ошибка polling: {e}")
            time.sleep(5)

threading.Thread(target=poll_telegram, daemon=True).start()

@app.route("/")
def home():
    return "🤖 Бот Сани работает!"

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
