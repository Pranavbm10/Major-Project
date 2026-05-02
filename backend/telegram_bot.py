import os
import requests
import asyncio
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Fix for Windows asyncio TLS start_tls error using httpx
if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Load environment variables from .env file
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
BACKEND_URL = "http://127.0.0.1:8000"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Request contact info to link profile
    contact_button = KeyboardButton(text="📲 Share phone to connect profile", request_contact=True)
    custom_keyboard = ReplyKeyboardMarkup([[contact_button]], resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "Welcome to AI Buddy! Please share your phone number to link your Telegram with your facial biometrics profile.", 
        reply_markup=custom_keyboard
    )

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    chat_id = update.effective_chat.id
    phone = contact.phone_number
    
    await update.message.reply_text(f"Connecting phone {phone} with our database...", reply_markup=ReplyKeyboardRemove())
    
    try:
        response = requests.post(f"{BACKEND_URL}/telegram/link", json={"phone": phone, "chat_id": str(chat_id)})
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                user = data.get("user")
                await update.message.reply_text(f"Successfully connected to profile: {user}! You can now ask me questions or send tasks.")
            else:
                await update.message.reply_text(f"Could not connect: {data.get('message')}\nPlease ensure you registered via the web Face ID portal first.")
        else:
            await update.message.reply_text("Server validation failed.")
    except Exception as e:
        await update.message.reply_text("Backend is offline. Please start it up.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id
    
    # Show typing indicator
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    
    # Pass the text to our unified Gemini Chat endpoint
    try:
        # In a fully separated prototype, we'd pass the chat_id in this payload so the backend knows *which* user to answer for.
        # But this acts as the "currently linked active user"
        response = requests.post(f"{BACKEND_URL}/chat", json={"prompt": text, "chat_id": str(chat_id)})
        
        if response.status_code == 200:
            data = response.json()
            reply = data.get("response", "Buddy had an issue generating a response.")
            
            # Send Gemini's answer back to the user on Telegram
            await update.message.reply_text(reply)
        else:
            await update.message.reply_text("Failed to reach the AI engine.")
    except Exception as e:
        await update.message.reply_text(f"Error connecting to Buddy Backend: {e}")

async def get_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        response = requests.get(f"{BACKEND_URL}/tasks?chat_id={chat_id}")
        if response.status_code == 200:
            tasks = response.json().get("tasks", [])
            if tasks:
                await update.message.reply_text("Your pending tasks:\n" + "\n".join(f"- {t}" for t in tasks))
            else:
                await update.message.reply_text("No tasks!")
        else:
            await update.message.reply_text("Failed to get tasks.")
    except Exception:
        await update.message.reply_text("Cannot connect to the backend.")

def main():
    if TELEGRAM_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        print("Please set your Telegram bot token!")
        return
        
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("tasks", get_tasks))
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Telegram bot started...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
