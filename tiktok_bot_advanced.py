import telebot
import requests
import os
import time
from typing import Optional, Dict, List
import logging
from pathlib import Path
from datetime import datetime
from functools import wraps
import re

# Загрузка переменных окружения из .env файла
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv не установлен, используем системные переменные
    pass

# Настройка логирования
log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Проверка наличия токена
if not TOKEN or TOKEN == "your_bot_token_here":
    logger.error("ОШИБКА: Не установлен токен бота!")
    logger.error("Установите переменную окружения TELEGRAM_BOT_TOKEN или создайте .env файл")
    exit(1)
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
TEMP_DIR = Path("temp_videos")
TEMP_DIR.mkdir(exist_ok=True)

# Инициализация бота
bot = telebot.TeleBot(TOKEN)

# Словарь для отслеживания запросов пользователей (простая защита от спама)
user_requests = {}

def rate_limit(max_calls: int = 5, time_window: int = 60):
    """Декоратор для ограничения частоты запросов от пользователей"""
    def decorator(func):
        @wraps(func)
        def wrapper(message):
            user_id = message.from_user.id
            current_time = time.time()
            
            if user_id not in user_requests:
                user_requests[user_id] = []
            
            # Удаляем старые запросы
            user_requests[user_id] = [
                req_time for req_time in user_requests[user_id]
                if current_time - req_time < time_window
            ]
            
            # Проверяем лимит
            if len(user_requests[user_id]) >= max_calls:
                bot.reply_to(
                    message,
                    f"⏳ Превышен лимит запросов. Попробуйте через {time_window} секунд."
                )
                return
            
            user_requests[user_id].append(current_time)
            return func(message)
        return wrapper
    return decorator


def validate_tiktok_url(url: str) -> bool:
    """Проверка корректности TikTok URL"""
    patterns = [
        r'https?://(?:www\.)?tiktok\.com/@[\w.-]+/video/\d+',
        r'https?://(?:vm|vt)\.tiktok\.com/[\w-]+',
        r'https?://(?:m\.)?tiktok\.com/v/\d+',
    ]
    return any(re.match(pattern, url) for pattern in patterns)


class TikTokDownloader:
    """Класс для работы с TikTok API с поддержкой множественных источников"""
    
    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries
        self.apis = [
            self._api_tiklydown,
            self._api_tikwm,
            self._api_snaptik
        ]
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def _api_tiklydown(self, url: str) -> Optional[Dict]:
        """API 1: tiklydown.eu.org"""
        try:
            response = self.session.get(
                "https://api.tiklydown.eu.org/api/download",
                params={"url": url},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("videoUrl"):
                return {
                    "video_url": data["videoUrl"],
                    "author": data.get("author", {}).get("nickname", "Unknown"),
                    "description": data.get("desc", "")
                }
        except requests.exceptions.RequestException as e:
            logger.warning(f"API tiklydown failed: {e}")
        except (KeyError, ValueError) as e:
            logger.warning(f"API tiklydown parsing error: {e}")
        return None
    
    def _api_tikwm(self, url: str) -> Optional[Dict]:
        """API 2: tikwm.com"""
        try:
            response = self.session.get(
                "https://www.tikwm.com/api/",
                params={"url": url, "hd": 1},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("data", {}).get("play"):
                return {
                    "video_url": data["data"]["play"],
                    "author": data["data"].get("author", {}).get("unique_id", "Unknown"),
                    "description": data["data"].get("title", "")
                }
        except requests.exceptions.RequestException as e:
            logger.warning(f"API tikwm failed: {e}")
        except (KeyError, ValueError) as e:
            logger.warning(f"API tikwm parsing error: {e}")
        return None
    
    def _api_snaptik(self, url: str) -> Optional[Dict]:
        """API 3: snaptik.app (заглушка для будущей реализации)"""
        try:
            response = self.session.post(
                "https://snaptik.app/abc2.php",
                data={"url": url},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15
            )
            # TODO: Реализовать парсинг HTML ответа
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"API snaptik failed: {e}")
            return None
    
    def get_video(self, url: str) -> Optional[Dict]:
        """
        Пытаемся получить видео через все доступные API
        
        Args:
            url: Ссылка на TikTok видео
            
        Returns:
            Словарь с информацией о видео или None
        """
        for api_method in self.apis:
            for attempt in range(self.max_retries):
                try:
                    result = api_method(url)
                    if result:
                        logger.info(f"Успешно получено видео через {api_method.__name__}")
                        return result
                except Exception as e:
                    logger.error(f"Ошибка в {api_method.__name__} (попытка {attempt + 1}): {e}")
                
                if attempt < self.max_retries - 1:
                    time.sleep(1)
            
            time.sleep(0.5)  # Небольшая задержка между API
        
        logger.error(f"Не удалось получить видео через все API для URL: {url}")
        return None
    
    def close(self):
        """Закрываем сессию"""
        self.session.close()

# Инициализация
downloader = TikTokDownloader()

@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("📱 Пример ссылки", callback_data="example"),
        telebot.types.InlineKeyboardButton("⚙️ Помощь", callback_data="help")
    )
    
    bot.send_message(
        message.chat.id,
        "👋 *Привет! Я бот для скачивания видео из TikTok*\n\n"
        "Просто отправь мне ссылку на видео, и я скачаю его для тебя.\n\n"
        "⚠️ *Важно:*\n"
        "• Поддерживаются только публичные видео\n"
        "• Максимальный размер: 50MB\n"
        "• Только для личного использования",
        parse_mode='Markdown',
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "example":
        bot.answer_callback_query(call.id)
        examples = """
*Примеры ссылок:*
• https://vm.tiktok.com/ZMJxw5p3D/
• https://www.tiktok.com/@username/video/1234567890123456789
• https://vt.tiktok.com/ZSdjx4HkR/
        """
        bot.send_message(call.message.chat.id, examples, parse_mode='Markdown')
    elif call.data == "help":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, 
                        "💡 *Советы:*\n"
                        "1. Копируйте ссылку через 'Поделиться'\n"
                        "2. Убедитесь, что видео публичное\n"
                        "3. Если не работает, попробуйте другую ссылку",
                        parse_mode='Markdown')

@bot.message_handler(func=lambda m: True)
@rate_limit(max_calls=5, time_window=60)
def handle_video_request(message):
    """Обработчик запросов на скачивание видео"""
    url = message.text.strip()
    
    # Валидация URL
    if not validate_tiktok_url(url):
        bot.reply_to(
            message, 
            "❌ Это не похоже на корректную ссылку TikTok.\n\n"
            "Примеры корректных ссылок:\n"
            "• https://www.tiktok.com/@user/video/123456789\n"
            "• https://vm.tiktok.com/ZMJxw5p3D/"
        )
        return
    
    status_msg = bot.reply_to(message, "🔄 *Обработка запроса...*", parse_mode='Markdown')
    video_path = None
    
    try:
        # Получаем информацию о видео
        logger.info(f"Запрос от пользователя {message.from_user.id}: {url}")
        video_info = downloader.get_video(url)
        
        if not video_info:
            bot.edit_message_text(
                "❌ Не удалось получить видео.\n\n"
                "Возможные причины:\n"
                "• Видео недоступно или удалено\n"
                "• Видео приватное\n"
                "• Временные проблемы с сервисом",
                message.chat.id, 
                status_msg.message_id
            )
            return
        
        bot.edit_message_text(
            "⬇️ *Загружаю видео...*",
            message.chat.id, 
            status_msg.message_id,
            parse_mode='Markdown'
        )
        
        # Скачиваем видео с проверкой размера
        video_response = requests.get(
            video_info["video_url"], 
            stream=True, 
            timeout=30
        )
        video_response.raise_for_status()
        
        # Проверяем размер файла
        content_length = video_response.headers.get('content-length')
        if content_length and int(content_length) > MAX_FILE_SIZE:
            bot.edit_message_text(
                f"❌ Видео слишком большое ({int(content_length) // (1024*1024)}MB). "
                f"Максимальный размер: {MAX_FILE_SIZE // (1024*1024)}MB",
                message.chat.id, 
                status_msg.message_id
            )
            return
        
        # Сохраняем во временную директорию
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_path = TEMP_DIR / f"video_{message.from_user.id}_{timestamp}.mp4"
        
        downloaded_size = 0
        with open(video_path, 'wb') as f:
            for chunk in video_response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    
                    # Проверяем размер во время загрузки
                    if downloaded_size > MAX_FILE_SIZE:
                        f.close()
                        video_path.unlink(missing_ok=True)
                        bot.edit_message_text(
                            f"❌ Видео превышает максимальный размер {MAX_FILE_SIZE // (1024*1024)}MB",
                            message.chat.id, 
                            status_msg.message_id
                        )
                        return
        
        bot.edit_message_text(
            "📤 *Отправляю видео...*",
            message.chat.id, 
            status_msg.message_id,
            parse_mode='Markdown'
        )
        
        # Отправляем видео
        with open(video_path, 'rb') as video_file:
            description = video_info.get('description', '')
            caption = f"🎬 Автор: @{video_info['author']}\n"
            
            if description:
                # Обрезаем описание, если оно слишком длинное
                max_desc_length = 150
                if len(description) > max_desc_length:
                    description = description[:max_desc_length] + "..."
                caption += f"📝 {description}\n"
            
            caption += "\n✅ Скачано через TikTok Downloader Bot"
            
            bot.send_video(
                message.chat.id,
                video_file,
                caption=caption,
                supports_streaming=True,
                timeout=60
            )
        
        # Удаляем сообщение о статусе
        try:
            bot.delete_message(message.chat.id, status_msg.message_id)
        except Exception:
            pass
        
        logger.info(f"Видео успешно отправлено пользователю {message.from_user.id}")
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout при загрузке видео: {url}")
        bot.edit_message_text(
            "❌ Превышено время ожидания. Попробуйте позже.",
            message.chat.id, 
            status_msg.message_id
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка загрузки видео: {e}")
        bot.edit_message_text(
            "❌ Ошибка при загрузке видео. Попробуйте другую ссылку.",
            message.chat.id, 
            status_msg.message_id
        )
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"Telegram API error: {e}")
        bot.edit_message_text(
            "❌ Ошибка отправки видео. Возможно, файл слишком большой.",
            message.chat.id, 
            status_msg.message_id
        )
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}", exc_info=True)
        try:
            bot.edit_message_text(
                "❌ Произошла ошибка при обработке запроса.",
                message.chat.id, 
                status_msg.message_id
            )
        except Exception:
            pass
    finally:
        # Удаляем временный файл
        if video_path and video_path.exists():
            try:
                video_path.unlink()
            except Exception as e:
                logger.error(f"Ошибка удаления файла {video_path}: {e}")
        
        # Очистка старых файлов
        cleanup_old_files()

def cleanup_old_files(max_age_minutes: int = 5):
    """
    Удаляем временные файлы старше указанного времени
    
    Args:
        max_age_minutes: Максимальный возраст файлов в минутах
    """
    try:
        current_time = time.time()
        max_age_seconds = max_age_minutes * 60
        deleted_count = 0
        
        for file_path in TEMP_DIR.glob("video_*.mp4"):
            try:
                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    file_path.unlink()
                    deleted_count += 1
                    logger.debug(f"Удален старый файл: {file_path.name}")
            except Exception as e:
                logger.error(f"Ошибка удаления файла {file_path}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Очищено {deleted_count} старых файлов")
            
    except Exception as e:
        logger.error(f"Ошибка при очистке файлов: {e}")


def main():
    """Главная функция запуска бота"""
    logger.info("=" * 50)
    logger.info("Запуск TikTok Downloader Bot...")
    logger.info(f"Директория для временных файлов: {TEMP_DIR.absolute()}")
    logger.info(f"Максимальный размер файла: {MAX_FILE_SIZE // (1024*1024)}MB")
    logger.info("=" * 50)
    
    # Очищаем старые файлы при запуске
    cleanup_old_files(max_age_minutes=1)
    
    try:
        # Запускаем бота
        logger.info("Бот успешно запущен и готов к работе!")
        bot.infinity_polling(timeout=60, long_polling_timeout=30)
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки...")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
    finally:
        logger.info("Завершение работы бота...")
        downloader.close()
        cleanup_old_files(max_age_minutes=0)  # Удаляем все временные файлы
        logger.info("Бот остановлен")


if __name__ == '__main__':
    main()