import os
import logging
import requests
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import google.generativeai as genai
import threading

# Logging
logging.basicConfig(level=logging.INFO)

# Env variables
TELEGRAM_TOKEN = os.environ['BOT_TOKEN']
GOOGLE_API_KEY = os.environ['GOOGLE_API_KEY']

# Gemini setup
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Flask app for UptimeRobot
flask_app = Flask(__name__)

@flask_app.route('/')
@flask_app.route('/health')
def health_check():
    return "Bot is running!", 200

# Download image from Telegram
def download_image(file_url, filename):
    response = requests.get(file_url)
    with open(filename, 'wb') as f:
        f.write(response.content)

# Telegram error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"Update {update} caused error {context.error}")
    if update.effective_message:
        await update.effective_message.reply_text("Sorry, something went wrong.")

# Handle image messages
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        return

    user = update.effective_user
    caption = update.message.caption or "No description provided"
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_path = f"temp_{photo.file_unique_id}.jpg"
    download_image(file.file_path, file_path)

    with open(file_path, "rb") as img:
        import base64
        image_data = base64.b64encode(img.read()).decode('utf-8')
        response = model.generate_content([{
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": image_data
            }
        }, f"""Estimate the calories in this food image. Description: {caption}.
Return:
1. Low estimate
2. High estimate
3. Medium (average)
4. Very short reasoning"""])
    os.remove(file_path)

    clean_text = response.text.replace("**", "").replace("*", "").replace("_", "").replace("`", "")
    await update.message.reply_text(f"🍽️ Estimate for @{user.username or user.first_name}:\n\n{clean_text}")

# Start Telegram bot
def start_bot():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_error_handler(error_handler)
    app.run_polling()

# Start Flask server
if __name__ == '__main__':
    # Run Telegram bot in a separate thread
    threading.Thread(target=start_bot).start()
    # Start Flask app (for UptimeRobot)
    flask_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
