import telebot
import requests
from datetime import datetime

from src.config import TOKEN, TEMP_DIR, MAX_FILE_SIZE, MAX_FILE_SIZE_MB, ALLOWED_USERS, logger
from src.downloader import TikTokDownloader
from src.utils import rate_limit, validate_tiktok_url, check_access, is_valid_mp4, cleanup_old_files

bot = telebot.TeleBot(TOKEN)
downloader = TikTokDownloader()


@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("Пример ссылки", callback_data="example"),
        telebot.types.InlineKeyboardButton("Помощь", callback_data="help"),
    )
    bot.send_message(
        message.chat.id,
        "*Привет! Я бот для скачивания видео из TikTok*\n\n"
        "Просто отправь мне ссылку на видео, и я скачаю его для тебя.\n\n"
        "*Важно:*\n"
        "• Поддерживаются только публичные видео\n"
        f"• Максимальный размер: {MAX_FILE_SIZE_MB}MB\n"
        "• Только для личного использования",
        parse_mode='Markdown',
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    bot.answer_callback_query(call.id)
    if call.data == "example":
        bot.send_message(
            call.message.chat.id,
            "*Примеры ссылок:*\n"
            "• https://vm.tiktok.com/ZMJxw5p3D/\n"
            "• https://www.tiktok.com/@username/video/1234567890123456789\n"
            "• https://vt.tiktok.com/ZSdjx4HkR/",
            parse_mode='Markdown',
        )
    elif call.data == "help":
        bot.send_message(
            call.message.chat.id,
            "*Советы:*\n"
            "1. Копируйте ссылку через 'Поделиться'\n"
            "2. Убедитесь, что видео публичное\n"
            "3. Если не работает, попробуйте другую ссылку",
            parse_mode='Markdown',
        )


@bot.message_handler(func=lambda m: True)
@rate_limit(bot)
def handle_video_request(message):
    if not check_access(message.from_user.id):
        bot.reply_to(message, "У вас нет доступа к этому боту.")
        return

    url = message.text.strip()

    if not validate_tiktok_url(url):
        bot.reply_to(
            message,
            "Это не похоже на корректную ссылку TikTok.\n\n"
            "Примеры корректных ссылок:\n"
            "• https://www.tiktok.com/@user/video/123456789\n"
            "• https://vm.tiktok.com/ZMJxw5p3D/",
        )
        return

    status_msg = bot.reply_to(message, "*Обработка запроса...*", parse_mode='Markdown')
    video_path = None

    try:
        logger.info(f"Request from {message.from_user.id}: {url}")
        video_info = downloader.get_video(url)

        if not video_info:
            bot.edit_message_text(
                "Не удалось получить видео.\n\n"
                "Возможные причины:\n"
                "• Видео недоступно или удалено\n"
                "• Видео приватное\n"
                "• Временные проблемы с сервисом",
                message.chat.id, status_msg.message_id,
            )
            return

        bot.edit_message_text(
            "*Загружаю видео...*",
            message.chat.id, status_msg.message_id,
            parse_mode='Markdown',
        )

        vr = requests.get(video_info["video_url"], stream=True, timeout=30)
        vr.raise_for_status()

        cl = vr.headers.get('content-length')
        if cl and int(cl) > MAX_FILE_SIZE:
            bot.edit_message_text(
                f"Видео слишком большое ({int(cl) // (1024 * 1024)}MB). "
                f"Максимум: {MAX_FILE_SIZE_MB}MB",
                message.chat.id, status_msg.message_id,
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
                        f.close()
                        video_path.unlink(missing_ok=True)
                        video_path = None
                        bot.edit_message_text(
                            f"Видео превышает {MAX_FILE_SIZE_MB}MB",
                            message.chat.id, status_msg.message_id,
                        )
                        return

        if not is_valid_mp4(video_path):
            video_path.unlink(missing_ok=True)
            video_path = None
            bot.edit_message_text(
                "Получен некорректный файл. Попробуйте другую ссылку.",
                message.chat.id, status_msg.message_id,
            )
            return

        bot.edit_message_text(
            "*Отправляю видео...*",
            message.chat.id, status_msg.message_id,
            parse_mode='Markdown',
        )

        with open(video_path, 'rb') as vf:
            desc = video_info.get('description', '')
            cap = f"Автор: @{video_info['author']}\n"
            if desc:
                if len(desc) > 150:
                    desc = desc[:150] + "..."
                cap += f"{desc}\n"
            cap += "\nСкачано через TikTok Downloader Bot"
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
        bot.edit_message_text("Превышено время ожидания.", message.chat.id, status_msg.message_id)
    except requests.exceptions.RequestException as e:
        logger.error(f"Download error: {e}")
        bot.edit_message_text("Ошибка загрузки. Попробуйте другую ссылку.", message.chat.id, status_msg.message_id)
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Telegram API error: {e}")
        bot.edit_message_text("Ошибка отправки. Возможно, файл слишком большой.", message.chat.id, status_msg.message_id)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        try:
            bot.edit_message_text("Произошла ошибка.", message.chat.id, status_msg.message_id)
        except Exception:
            pass
    finally:
        if video_path and video_path.exists():
            try:
                video_path.unlink()
            except Exception as e:
                logger.error(f"Error deleting {video_path}: {e}")
        cleanup_old_files()


def main():
    logger.info("=" * 50)
    logger.info("Starting TikTok Downloader Bot")
    logger.info(f"Temp dir: {TEMP_DIR.absolute()}")
    logger.info(f"Max file size: {MAX_FILE_SIZE_MB}MB")
    if ALLOWED_USERS:
        logger.info(f"Access restricted to users: {ALLOWED_USERS}")
    logger.info("=" * 50)

    try:
        me = bot.get_me()
        logger.info(f"Bot authorized as @{me.username} (ID: {me.id})")
    except Exception as e:
        logger.error(f"Bot authorization failed: {e}")
        return

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
        downloader.close()
        cleanup_old_files(max_age_minutes=0)
        logger.info("Bot stopped")


if __name__ == '__main__':
    main()
