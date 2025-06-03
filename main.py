import os
import logging
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import requests
from flask import Flask
import threading

# Logging setup
logging.basicConfig(level=logging.INFO)

# Flask app for health checks
flask_app = Flask(__name__)

@flask_app.route('/')
@flask_app.route('/health')
def health_check():
    return "Bot is running!", 200

# Get your API keys
TELEGRAM_TOKEN = os.environ['BOT_TOKEN']
GOOGLE_API_KEY = os.environ['GOOGLE_API_KEY']

# Gemini setup
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')


# Download the image from Telegram
def download_image(file_url, filename):
    response = requests.get(file_url)
    with open(filename, 'wb') as f:
        f.write(response.content)


# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"Update {update} caused error {context.error}")
    if update.effective_message:
        await update.effective_message.reply_text(
            "Sorry, something went wrong while processing your request. Please try again."
        )


# Handler for images
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        return

    user = update.effective_user
    caption = update.message.caption or "No description provided"

    # Get the highest resolution photo
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_path = f"temp_{photo.file_unique_id}.jpg"

    # Download the image
    download_image(file.file_path, file_path)

    # Send to Gemini
    with open(file_path, "rb") as img:
        import base64
        image_data = base64.b64encode(img.read()).decode('utf-8')

        response = model.generate_content([{
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": image_data
            }
        }, f"""Estimate the calories in this food image. 
Here is the user description: {caption}.
Return the following:
1. Low estimate
2. High estimate
3. Medium (average)
4. A extremely short explanation of your reasoning."""])

    os.remove(file_path)

    # Reply with results
    clean_text = response.text.replace("**", "").replace("*", "").replace(
        "_", "").replace("", "")
    await update.message.reply_text(
        f"🍽️ Estimate for @{user.username or user.first_name}:\n\n{clean_text}"
    )


# Start Flask server in background
def run_flask():
    flask_app.run(host='0.0.0.0', port=5000, debug=False)

# Start the bot
def main():
    # Start Flask server in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Start Telegram bot
    telegram_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    telegram_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    telegram_app.add_error_handler(error_handler)
    telegram_app.run_polling()


if __name__ == '__main__':
    main()
