import signal
from datetime import datetime

import requests
import telebot

import src
from src.config import (
    ADMIN_USER_ID,
    DOWNLOAD_TIMEOUT,
    MAX_FILE_SIZE,
    MAX_FILE_SIZE_MB,
    TEMP_DIR,
    TOKEN,
    logger,
)
from src.downloaders import close_all, get_downloader
from src.utils import (
    check_access,
    cleanup_old_files,
    grant_access,
    is_admin,
    is_safe_video_url,
    is_valid_mp4,
    list_allowed_users,
    rate_limit,
    revoke_access,
)

bot = telebot.TeleBot(TOKEN)

SUPPORTED_SERVICES = [
    "TikTok", "Instagram (Reels, посты)", "YouTube / YouTube Shorts",
    "Twitter / X", "Reddit", "Facebook", "Pinterest", "Vimeo",
]

HELP_TEXT = (
    "*Советы:*\n"
    "1. Скопируйте ссылку через 'Поделиться'\n"
    "2. Убедитесь, что видео публичное\n"
    "3. Отправьте ссылку боту\n"
    "4. Если не работает — попробуйте другую ссылку"
)


def safe_edit(chat_id, message_id, text, **kwargs):
    """Редактирование статус-сообщения без падения, если оно уже удалено/не изменилось."""
    try:
        bot.edit_message_text(text, chat_id, message_id, **kwargs)
    except telebot.apihelper.ApiTelegramException as e:
        logger.debug(f"edit_message_text ignored: {e}")


@bot.message_handler(commands=['start'])
def start(message):
    if not check_access(message.from_user.id):
        bot.reply_to(message, "У вас нет доступа к этому боту.")
        return

    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("Список сервисов", callback_data="services"),
        telebot.types.InlineKeyboardButton("Помощь", callback_data="help"),
    )
    services_list = "\n".join(f"• {s}" for s in SUPPORTED_SERVICES)
    bot.send_message(
        message.chat.id,
        "*Привет! Я бот для скачивания видео*\n\n"
        "Просто отправь ссылку на видео — я скачаю его для тебя.\n\n"
        "*Поддерживаемые платформы:*\n"
        f"{services_list}\n\n"
        f"*Максимальный размер:* {MAX_FILE_SIZE_MB}MB\n"
        "*Только для личного использования*",
        parse_mode='Markdown',
        reply_markup=markup,
    )


@bot.message_handler(commands=['help'])
def help_command(message):
    if not check_access(message.from_user.id):
        bot.reply_to(message, "У вас нет доступа к этому боту.")
        return
    bot.send_message(message.chat.id, HELP_TEXT, parse_mode='Markdown')


def format_whitelist_user(user_id: int) -> str:
    """Форматирует запись whitelist с данными, доступными боту в Telegram."""
    try:
        chat = bot.get_chat(user_id)
    except Exception as e:
        logger.debug(f"Unable to resolve Telegram profile for {user_id}: {e}")
        return str(user_id)

    username = getattr(chat, "username", None)
    if username:
        return f"{user_id} — @{username}"

    display_name = " ".join(
        part for part in (getattr(chat, "first_name", None), getattr(chat, "last_name", None)) if part
    )
    return f"{user_id} — {display_name}" if display_name else str(user_id)


@bot.message_handler(commands=['access'])
def access_command(message):
    """Управление whitelist: /access add|remove <telegram_user_id>, /access list."""
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "Эта команда доступна только администратору.")
        return

    parts = (message.text or "").split()
    if len(parts) == 2 and parts[1].lower() == "list":
        allowed_users = list_allowed_users()
        users = "\n".join(format_whitelist_user(user_id) for user_id in allowed_users)
        bot.reply_to(message, f"Whitelist ({len(allowed_users)}):\n{users}")
        return

    if len(parts) != 3 or parts[1].lower() not in {"add", "remove"}:
        bot.reply_to(
            message,
            "Использование:\n"
            "/access add <telegram_user_id>\n"
            "/access remove <telegram_user_id>\n"
            "/access list",
        )
        return

    action, user_id_raw = parts[1].lower(), parts[2]
    try:
        user_id = int(user_id_raw)
    except ValueError:
        bot.reply_to(message, "Telegram user ID должен быть числом.")
        return
    if user_id <= 0:
        bot.reply_to(message, "Telegram user ID должен быть положительным числом.")
        return

    if action == "add":
        if grant_access(user_id):
            bot.reply_to(message, f"Доступ для {user_id} добавлен.")
        else:
            bot.reply_to(message, f"У {user_id} уже есть доступ.")
        return

    if user_id == ADMIN_USER_ID:
        bot.reply_to(message, "Нельзя удалить администратора из whitelist.")
    elif revoke_access(user_id):
        bot.reply_to(message, f"Доступ для {user_id} удалён.")
    else:
        bot.reply_to(message, f"У {user_id} нет доступа.")


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if not check_access(call.from_user.id):
        bot.answer_callback_query(call.id, "У вас нет доступа к этому боту.", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    if call.data == "services":
        services_list = "\n".join(f"• {s}" for s in SUPPORTED_SERVICES)
        bot.send_message(
            call.message.chat.id,
            "*Поддерживаемые платформы:*\n"
            f"{services_list}",
            parse_mode='Markdown',
        )
    elif call.data == "help":
        bot.send_message(call.message.chat.id, HELP_TEXT, parse_mode='Markdown')


@bot.message_handler(func=lambda m: True)
@rate_limit(bot)
def handle_video_request(message):
    if not check_access(message.from_user.id):
        bot.reply_to(message, "У вас нет доступа к этому боту.")
        return

    if not message.text:
        return

    url = message.text.strip()

    downloader, service_name = get_downloader(url)
    if not downloader:
        bot.reply_to(
            message,
            "Эта платформа пока не поддерживается.\n\n"
            "Поддерживаемые платформы:\n" +
            "\n".join(f"• {s}" for s in SUPPORTED_SERVICES),
        )
        return

    status_msg = bot.reply_to(message, "*Обрабатываю запрос...*", parse_mode='Markdown')
    video_path = None

    try:
        logger.info(f"Request from {message.from_user.id} [{service_name}]: {url}")
        video_info = downloader.get_video(url)

        if not video_info or not is_safe_video_url(video_info.get("video_url")):
            safe_edit(
                message.chat.id, status_msg.message_id,
                "Не удалось получить видео.\n\n"
                "Возможные причины:\n"
                "• Видео недоступно или удалено\n"
                "• Видео приватное\n"
                "• Временные проблемы с сервисом",
            )
            return

        safe_edit(
            message.chat.id, status_msg.message_id,
            "*Загружаю видео...*", parse_mode='Markdown',
        )

        vr = requests.get(
            video_info["video_url"],
            headers=video_info.get("http_headers"),
            cookies=video_info.get("cookies"),
            stream=True,
            timeout=DOWNLOAD_TIMEOUT,
        )
        vr.raise_for_status()

        cl = vr.headers.get('content-length')
        if cl and int(cl) > MAX_FILE_SIZE:
            safe_edit(
                message.chat.id, status_msg.message_id,
                f"Видео слишком большое ({int(cl) // (1024 * 1024)}MB). "
                f"Максимум: {MAX_FILE_SIZE_MB}MB",
            )
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_path = TEMP_DIR / f"video_{message.from_user.id}_{timestamp}.mp4"

        downloaded = 0
        with open(video_path, 'wb') as f:
            for chunk in vr.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if downloaded > MAX_FILE_SIZE:
                        video_path.unlink(missing_ok=True)
                        video_path = None
                        safe_edit(
                            message.chat.id, status_msg.message_id,
                            f"Видео превышает {MAX_FILE_SIZE_MB}MB",
                        )
                        return

        if not is_valid_mp4(video_path):
            video_path.unlink(missing_ok=True)
            video_path = None
            safe_edit(
                message.chat.id, status_msg.message_id,
                "Получен некорректный файл. Попробуйте другую ссылку.",
            )
            return

        safe_edit(
            message.chat.id, status_msg.message_id,
            "*Отправляю видео...*", parse_mode='Markdown',
        )

        with open(video_path, 'rb') as vf:
            desc = video_info.get('description', '')
            cap = f"Автор: @{video_info['author']}\n"
            if desc:
                if len(desc) > 150:
                    desc = desc[:150] + "..."
                cap += f"{desc}\n"
            cap += "\nСкачано через Downloader Bot"
            bot.send_video(
                message.chat.id, vf,
                caption=cap,
                supports_streaming=True,
                timeout=60,
            )

        try:
            bot.delete_message(message.chat.id, status_msg.message_id)
        except Exception:
            pass

        logger.info(f"Video sent to {message.from_user.id}")

    except requests.exceptions.Timeout:
        logger.error(f"Timeout: {url}")
        safe_edit(message.chat.id, status_msg.message_id, "Превышено время ожидания.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Download error: {e}")
        safe_edit(message.chat.id, status_msg.message_id, "Ошибка загрузки. Попробуйте другую ссылку.")
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Telegram API error: {e}")
        safe_edit(
            message.chat.id, status_msg.message_id,
            "Ошибка отправки. Возможно, файл слишком большой.",
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        safe_edit(message.chat.id, status_msg.message_id, "Произошла ошибка.")
    finally:
        if video_path and video_path.exists():
            try:
                video_path.unlink()
            except Exception as e:
                logger.error(f"Error deleting {video_path}: {e}")
        cleanup_old_files()


def _request_shutdown(signum, frame):
    logger.info(f"Received signal {signum}, shutting down...")
    raise KeyboardInterrupt


def main():
    logger.info("=" * 50)
    logger.info(f"Starting Downloader Bot v{src.__version__}")
    logger.info(f"Temp dir: {TEMP_DIR.absolute()}")
    logger.info(f"Max file size: {MAX_FILE_SIZE_MB}MB")
    logger.info(f"Access whitelist enabled; administrator: {ADMIN_USER_ID}")
    logger.info(f"Services: {', '.join(SUPPORTED_SERVICES)}")
    logger.info("=" * 50)

    try:
        me = bot.get_me()
        logger.info(f"Bot authorized as @{me.username} (ID: {me.id})")
    except Exception as e:
        logger.error(f"Bot authorization failed: {e}")
        return

    signal.signal(signal.SIGTERM, _request_shutdown)

    cleanup_old_files(max_age_minutes=1)

    try:
        logger.info("Bot is polling...")
        bot.infinity_polling(timeout=60, long_polling_timeout=30)
    except KeyboardInterrupt:
        logger.info("Shutdown signal received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        logger.info("Shutting down...")
        close_all()
        cleanup_old_files(max_age_minutes=0)
        logger.info("Bot stopped")


if __name__ == '__main__':
    main()
