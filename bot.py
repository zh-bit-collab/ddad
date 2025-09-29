import telebot
import os
import sqlite3
import google.generativeai as genai
from datetime import datetime, timedelta

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")  # Get token from environment variable
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")  # Get API key from environment variable
DATABASE_NAME = "telegram_bot.db"
PERSONALITY = "You are a helpful and friendly assistant specializing in technology and coding. You are concise and informative."
ALLOWED_TOPICS = ["technology", "coding", "python", "ai", "programming", "data science"]
MAX_MESSAGES_PER_DAY = 50

# --- DATABASE SETUP ---
def create_database():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            last_message_timestamp DATETIME
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            chat_id INTEGER PRIMARY KEY,
            user_id INTEGER,
            last_message_timestamp DATETIME,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    conn.commit()
    conn.close()

# --- GOOGLE AI STUDIO SETUP ---
def setup_google_ai():
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-pro')  # Or another suitable model
        return model
    except Exception as e:
        print(f"Error setting up Google AI: {e}")
        return None

# --- BOT INITIALIZATION ---
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
model = setup_google_ai()

# --- HELPER FUNCTIONS ---
def get_user_data(telegram_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_chat_data(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chats WHERE user_id = ?", (user_id,))
    chat = cursor.fetchone()
    conn.close()
    return chat

def add_message_to_chat(user_id, chat_id, message):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO chats (chat_id, user_id, last_message_timestamp)
        VALUES (?, ?, ?)
    """, (chat_id, user_id, datetime.now()))
    conn.commit()
    conn.close()

def check_message_limit(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE telegram_id = ?", (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def update_last_message_timestamp(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET last_message_timestamp = ? WHERE telegram_id = ?", (datetime.now(), user_id))
    conn.commit()
    conn.close()

# --- BOT HANDLERS ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    if user_data is None:
        add_message_to_chat(user_id, message.chat.id, "Welcome! I'm your AI assistant.")
        update_last_message_timestamp(user_id)
    else:
        add_message_to_chat(user_id, message.chat.id, f"Welcome back! I'm your AI assistant.")
    bot.reply_to(message, "How can I help you today?")

@bot.message_handler(func=lambda message: True)
def echo_message(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    last_message_timestamp = get_user_data(user_id)['last_message_timestamp']
    current_messages = datetime.now() - timedelta(days=MAX_MESSAGES_PER_DAY)
    count = 0

    # Check if the user has exceeded the message limit
    if datetime.now() > current_messages:
        bot.reply_to(message, "Sorry, you have exceeded the daily message limit.")
        return

    user_data = get_user_data(user_id)
    if user_data is None:
        user_data = {'telegram_id': user_id, 'username': message.from_user.username, 'last_message_timestamp': datetime.now()}
        add_message_to_chat(user_id, chat_id, message.text)
        update_last_message_timestamp(user_id)
        user_data = get_user_data(user_id)
    else:
        add_message_to_chat(user_id, chat_id, message.text)
        update_last_message_timestamp(user_id)

    prompt = f"""
    You are a helpful AI assistant named {PERSONALITY}.
    The user's previous messages are:
    {message.text}

    Based on the allowed topics: {', '.join(ALLOWED_TOPICS)}.
    Respond to the user's message in a concise and informative way.
    """

    try:
        response = model.generate_content(prompt)
        bot.reply_to(message, response.text)
    except Exception as e:
        print(f"Error generating response: {e}")
        bot.reply_to(message, "Sorry, I encountered an error while processing your request.")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN or not GOOGLE_API_KEY:
        print("Please set the TELEGRAM_BOT_TOKEN and GOOGLE_API_KEY as environment variables.")
    else:
        create_database()
        bot.polling(none_stop=True)
