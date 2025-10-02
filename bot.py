
import os
import time
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import socketserver
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from collections import defaultdict
import sys
import psutil
import requests
import threading


def keep_alive_ping():
    """Пингует себя каждые 10 минут чтобы не заснуть"""
    while True:
        try:
            # Пингуем свой же хостинг
            response = requests.get('https://your-bot-name.onrender.com/health', timeout=30)
            print(f"🔄 Keep-alive ping: {response.status_code}")
        except Exception as e:
            print(f"❌ Keep-alive failed: {e}")

        # Ждем 10 минут
        time.sleep(600)


# Запускаем в отдельном потоке после запуска бота
def start_keep_alive():
    ping_thread = threading.Thread(target=keep_alive_ping, daemon=True)
    ping_thread.start()


# Загрузка переменных окружения
load_dotenv()

cold_start = True


def handle_cold_start():
    global cold_start
    if cold_start:
        print("🔥 Cold start - bot was sleeping")
        cold_start = False
        # Можно отправить уведомление владельцу
        try:
            if OWNER_ID:
                bot.send_message(OWNER_ID, "🤖 Бот проснулся после сна")
        except:
            pass


# Простой HTTP-сервер для Render
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            if self.path == '/health' or self.path == '/':
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'OK')
                print(f"✅ Health check: {self.path}")
            else:
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Telegram Bot is running!')
                print(f"✅ Request: {self.path}")

        except Exception as e:
            print(f"❌ HTTP error: {e}")
            self.send_error(500, f"Server error: {e}")

    # Добавляем поддержку HEAD запросов
    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()

    # Добавляем поддержку OPTIONS запросов
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()

    # Упрощаем логирование
    def log_message(self, format, *args):
        print(f"🌐 HTTP: {self.address_string()} - {self.command} {self.path}")


def run_http_server():
    port = 5000
    try:
        server = HTTPServer(('0.0.0.0', port), HealthHandler)
        print(f"🌐 HTTP server running on port {port}")
        server.serve_forever()
    except Exception as e:
        print(f"❌ HTTP server crashed: {e}")
        # Пытаемся перезапуститься
        time.sleep(5)
        run_http_server()


# Инициализация бота
BOT_TOKEN = "7613324655:AAH-yS_7o96AjkSsp97W5o0kmT10geG6z6A"

bot = telebot.TeleBot(BOT_TOKEN)

# Хранение данных
moderators_chat_id = -1003005577058
moderators = set()
user_messages = {}
waiting_for_moderators_chat = False

# Защита от флуда
user_message_timestamps = defaultdict(list)
MAX_MESSAGES_PER_MINUTE = 20

# ID владельца бота
OWNER_ID = 5492264667  # Замените на ваш ID


# Функция для проверки флуда
def check_flood(user_id):
    now = time.time()
    user_message_timestamps[user_id] = [t for t in user_message_timestamps[user_id] if now - t < 60]

    if len(user_message_timestamps[user_id]) >= MAX_MESSAGES_PER_MINUTE:
        return False

    user_message_timestamps[user_id].append(now)
    return True


# Функция для создания клавиатуры ответа
def create_reply_keyboard(user_id):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("📨 Ответить", callback_data=f"reply_{user_id}"))
    return keyboard


# Функция для создания клавиатуры refresh
def refresh_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔄 Обновить модераторов", callback_data="refresh_mods"))
    return keyboard


# Функция для обновления списка модераторов из чата
def update_moderators_from_chat():
    global moderators
    if not moderators_chat_id:
        return False

    try:
        chat_admins = bot.get_chat_administrators(moderators_chat_id)
        moderators.clear()

        for admin in chat_admins:
            if not admin.user.is_bot:
                moderators.add(admin.user.id)

        print(f"Обновлен список модераторов: {moderators}")
        return True

    except Exception as e:
        print(f"Ошибка при обновлении модераторов: {e}")
        return False


# Функция для проверки является ли пользователь модератором
def is_moderator(user_id):
    return user_id in moderators or user_id == OWNER_ID


# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start_command(message):
    handle_cold_start()
    if message.from_user.id == OWNER_ID:
        bot.send_message(message.chat.id,
                         "👋 Владелец бота! Используйте команды:\n/setup - настроить чат модераторов\n/refresh - обновить список модераторов")
    elif moderators_chat_id and message.chat.id == moderators_chat_id:
        if update_moderators_from_chat():
            bot.send_message(message.chat.id, "👋 Добро пожаловать в чат модераторов! Ваши права обновлены.",
                             reply_markup=refresh_keyboard())
        else:
            bot.send_message(message.chat.id, "👋 Добро пожаловать! Для работы обратитесь к владельцу.")
    else:
        bot.send_message(message.chat.id, "👋 Привет! Отправь мне сообщение, и я передам его модераторам.")


# Обработчик команды /setup
@bot.message_handler(commands=['setup'])
def setup_command(message):
    handle_cold_start()
    if message.from_user.id == OWNER_ID:
        global waiting_for_moderators_chat
        waiting_for_moderators_chat = True
        bot.send_message(message.chat.id,
                         "Добавьте бота в чат модераторов (с правами администратора!) и перешлите любое сообщение из этого чата:")
    else:
        bot.send_message(message.chat.id, "❌ Эта команда доступна только владельцу.")


# Обработчик команды /refresh
@bot.message_handler(commands=['refresh'])
def refresh_command(message):
    handle_cold_start()
    if is_moderator(message.from_user.id):
        if update_moderators_from_chat():
            bot.send_message(message.chat.id, f"✅ Список модераторов обновлен! Всего модераторов: {len(moderators)}",
                             reply_markup=refresh_keyboard())
        else:
            bot.send_message(message.chat.id, "❌ Ошибка при обновлении модераторов. Проверьте настройки чата.")
    else:
        bot.send_message(message.chat.id, "❌ Эта команда доступна только модераторам.")


# Обработчик команды /stats (только для владельца)
@bot.message_handler(commands=['stats'])
def stats_command(message):
    handle_cold_start()
    if message.from_user.id == OWNER_ID:
        stats_text = f"📊 Статистика бота:\n"
        stats_text += f"• Чат модераторов: {moderators_chat_id or 'Не настроен'}\n"
        stats_text += f"• Модераторов: {len(moderators)}\n"
        stats_text += f"• Активных пользователей: {len(user_message_timestamps)}\n"
        bot.send_message(message.chat.id, stats_text)


# Обработчик текстовых сообщений
@bot.message_handler(content_types=['text'])
def handle_text(message):
    handle_cold_start()
    global waiting_for_moderators_chat

    # Пропускаем команды
    if message.text.startswith('/'):
        return

    if waiting_for_moderators_chat:
        setup_moderators_chat(message)
        return

    if message.from_user.id == OWNER_ID:
        handle_owner_message(message)
    elif moderators_chat_id and message.chat.id == moderators_chat_id:
        handle_moderator_chat_message(message)
    else:
        # Проверяем флуд
        if not check_flood(message.from_user.id):
            bot.send_message(message.chat.id, "❌ Слишком много сообщений! Подождите немного.")
            return
        forward_to_moderators_chat(message)


# Обработчик медиа-сообщений
@bot.message_handler(content_types=['photo', 'document', 'video', 'audio', 'voice', 'sticker'])
def handle_media(message):
    handle_cold_start()
    if moderators_chat_id and message.chat.id == moderators_chat_id:
        handle_moderator_chat_message(message)
    else:
        # Проверяем флуд
        if not check_flood(message.from_user.id):
            bot.send_message(message.chat.id, "❌ Слишком много сообщений! Подождите немного.")
            return
        forward_to_moderators_chat(message)


# Настройка чата модераторов
def setup_moderators_chat(message):
    global moderators_chat_id, waiting_for_moderators_chat

    if message.forward_from_chat:
        moderators_chat_id = message.forward_from_chat.id
        waiting_for_moderators_chat = False

        if update_moderators_from_chat():
            bot.send_message(message.chat.id,
                             f"✅ Чат модераторов установлен! ID: {moderators_chat_id}\nМодераторов: {len(moderators)}")
            bot.send_message(moderators_chat_id,
                             "✅ Этот чат теперь является чатом модераторов! Все администраторы чата могут отвечать на сообщения пользователей.",
                             reply_markup=refresh_keyboard())
        else:
            bot.send_message(message.chat.id,
                             "❌ Не удалось получить список администраторов. Убедитесь, что бот имеет права администратора в чате.")

    elif message.chat.type in ['group', 'supergroup']:
        moderators_chat_id = message.chat.id
        waiting_for_moderators_chat = False

        if update_moderators_from_chat():
            bot.send_message(message.chat.id,
                             f"✅ Этот чат установлен как чат модераторов! ID: {moderators_chat_id}\nМодераторов: {len(moderators)}",
                             reply_markup=refresh_keyboard())
        else:
            bot.send_message(message.chat.id,
                             "❌ Не удалось получить список администраторов. Убедитесь, что бот имеет права администратора в чате.")

    else:
        bot.send_message(message.chat.id,
                         "❌ Пожалуйста, перешлите сообщение из группового чата или выполните команду в нужном чате.")


# Пересылка сообщений в чат модераторов
def forward_to_moderators_chat(message):
    if not moderators_chat_id:
        bot.send_message(message.chat.id, "❌ Чат модераторов еще не настроен. Попробуйте позже.")
        return

    if not moderators and not OWNER_ID:
        bot.send_message(message.chat.id, "❌ В настоящее время нет активных модераторов. Попробуйте позже.")
        return

    user_id = message.from_user.id
    user_name = message.from_user.first_name
    if message.from_user.username:
        user_name += f" (@{message.from_user.username})"

    try:
        if message.content_type == 'text':
            sent_message = bot.send_message(
                moderators_chat_id,
                f"👤 Сообщение от {user_name} (ID: {user_id}):\n\n{message.text}",
                reply_markup=create_reply_keyboard(user_id)
            )
        else:
            caption = f"👤 Сообщение от {user_name} (ID: {user_id})"
            if message.caption:
                caption += f":\n\n{message.caption}"

            if message.content_type == 'photo':
                sent_message = bot.send_photo(
                    moderators_chat_id,
                    message.photo[-1].file_id,
                    caption=caption,
                    reply_markup=create_reply_keyboard(user_id)
                )
            elif message.content_type == 'document':
                sent_message = bot.send_document(
                    moderators_chat_id,
                    message.document.file_id,
                    caption=caption,
                    reply_markup=create_reply_keyboard(user_id)
                )
            elif message.content_type == 'video':
                sent_message = bot.send_video(
                    moderators_chat_id,
                    message.video.file_id,
                    caption=caption,
                    reply_markup=create_reply_keyboard(user_id)
                )
            elif message.content_type == 'audio':
                sent_message = bot.send_audio(
                    moderators_chat_id,
                    message.audio.file_id,
                    caption=caption,
                    reply_markup=create_reply_keyboard(user_id)
                )
            elif message.content_type == 'voice':
                sent_message = bot.send_voice(
                    moderators_chat_id,
                    message.voice.file_id,
                    caption=caption,
                    reply_markup=create_reply_keyboard(user_id)
                )
            elif message.content_type == 'sticker':
                sent_message = bot.send_sticker(
                    moderators_chat_id,
                    message.sticker.file_id
                )
                bot.send_message(
                    moderators_chat_id,
                    f"👤 Стикер от {user_name} (ID: {user_id})",
                    reply_markup=create_reply_keyboard(user_id)
                )

        user_messages[sent_message.message_id] = user_id
        bot.send_message(message.chat.id, "✅ Ваше сообщение отправлено модераторам!")

    except Exception as e:
        print(f"Ошибка при отправке в чат модераторов: {e}")
        bot.send_message(message.chat.id, "❌ Ошибка при отправке сообщения. Попробуйте позже.")


# Обработка сообщений в чате модераторов
def handle_moderator_chat_message(message):
    # Пропускаем команды и кнопки
    if message.text and (message.text.startswith('/') or message.text in ["Обновить модераторов"]):
        return

    if not is_moderator(message.from_user.id):
        bot.send_message(message.chat.id,
                         "❌ Вы не являетесь модератором. Для получения прав обратитесь к владельцу чата.")
        return

    # Если это ответ на сообщение пользователя
    if message.reply_to_message:
        reply_to_msg_id = message.reply_to_message.message_id
        if reply_to_msg_id in user_messages:
            user_id = user_messages[reply_to_msg_id]
            try:
                if message.content_type == 'text':
                    bot.send_message(user_id, f"📩 Ответ от модератора:\n\n{message.text}")
                else:
                    if message.content_type == 'photo':
                        bot.send_photo(user_id, message.photo[-1].file_id, caption=message.caption)
                    elif message.content_type == 'document':
                        bot.send_document(user_id, message.document.file_id, caption=message.caption)
                    elif message.content_type == 'video':
                        bot.send_video(user_id, message.video.file_id, caption=message.caption)
                    elif message.content_type == 'audio':
                        bot.send_audio(user_id, message.audio.file_id, caption=message.caption)
                    elif message.content_type == 'voice':
                        bot.send_voice(user_id, message.voice.file_id)
                    elif message.content_type == 'sticker':
                        bot.send_sticker(user_id, message.sticker.file_id)

                bot.send_message(moderators_chat_id, "✅ Ответ отправлен пользователю!")

            except Exception as e:
                bot.send_message(moderators_chat_id, f"❌ Не удалось отправить ответ: {e}")


# Обработка сообщений владельца
def handle_owner_message(message):
    # Пропускаем команды
    if message.text.startswith('/'):
        return

    if message.text == "Обновить модераторов":
        if update_moderators_from_chat():
            bot.send_message(message.chat.id, f"✅ Список модераторов обновлен! Всего: {len(moderators)}")
        else:
            bot.send_message(message.chat.id, "❌ Ошибка при обновлении. Проверьте права бота в чате.")


# Обработчик callback-кнопок
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data.startswith('reply_'):
        user_id = int(call.data.split('_')[1])
        bot.answer_callback_query(call.id,
                                  "Просто ответьте (reply) на это сообщение чтобы отправить ответ пользователю")

    elif call.data == "refresh_mods":
        if is_moderator(call.from_user.id):
            if update_moderators_from_chat():
                bot.answer_callback_query(call.id, "✅ Список модераторов обновлен!")
                bot.edit_message_text(f"✅ Список модераторов обновлен! Всего: {len(moderators)}",
                                      call.message.chat.id, call.message.message_id,
                                      reply_markup=refresh_keyboard())
            else:
                bot.answer_callback_query(call.id, "❌ Ошибка при обновлении")
        else:
            bot.answer_callback_query(call.id, "❌ Только для модераторов")


# Обработчик новых участников чата
@bot.message_handler(content_types=['new_chat_members'])
def handle_new_members(message):
    handle_cold_start()
    if message.chat.id == moderators_chat_id:
        for new_member in message.new_chat_members:
            if not new_member.is_bot:
                bot.send_message(moderators_chat_id,
                                 f"👋 Добро пожаловать, {new_member.first_name}! Для получения прав модератора обратитесь к владельцу.")


# Функция проверки инстансов
def check_bot_instances():
    try:
        import psutil
        current_pid = os.getpid()
        bot_processes = []

        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if (proc.info['pid'] != current_pid and
                        'python' in proc.info['name'].lower() and
                        any('bot.py' in cmd for cmd in proc.info['cmdline'] or [])):
                    bot_processes.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return bot_processes
    except ImportError:
        print("⚠️ psutil не установлен, проверка инстансов недоступна")
        return []


if __name__ == "__main__":
    # Запускаем HTTP сервер
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()
    print("🚀 Starting HTTP server on port 5000...")

    # Запускаем авто-пинг
    start_keep_alive()
    print("🔄 Keep-alive service started...")

    time.sleep(3)

    try:
        bot.remove_webhook()
        time.sleep(2)

        print("🤖 Starting Telegram bot...")
        bot.infinity_polling(
            allowed_updates=['message', 'callback_query'],
            timeout=90,
            long_polling_timeout=90,
            skip_pending=True
        )
    except Exception as e:
        print(f"❌ Bot startup failed: {e}")
        print("🔄 Restarting in 10 seconds...")
        time.sleep(10)
        os.execv(sys.executable, ['python'] + sys.argv)