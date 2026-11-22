"""Telegram-бот: время и погода в Астане, курс биткоина, курсы валют, цитаты.

Управление: команды (/start, /help, /weather, /crypto, /rates, /quote, /time),
кнопки под строкой ввода (Reply-клавиатура) и кнопка «Обновить» под ответами
(Inline-клавиатура). Любое другое сообщение — полная сводка.

Получение обновлений — long polling (getUpdates).
Источники данных: Open-Meteo (погода), CoinGecko (биткоин),
open.er-api.com (курсы валют). Ключи не нужны.
Токен берётся из .env (BOT_TOKEN).
"""
import html
import logging
import os
import random
import time
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise SystemExit("BOT_TOKEN не найден. Добавьте его в файл .env")

API = f"https://api.telegram.org/bot{TOKEN}"
POLL_TIMEOUT = 30  # секунд long polling

# Астана
LAT, LON = 51.1694, 71.4491
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
# Курс биткоина — CoinGecko
BTC_URL = "https://api.coingecko.com/api/v3/simple/price"
# Курсы валют (база USD, обновляется раз в сутки)
RATES_URL = "https://open.er-api.com/v6/latest/USD"

# Казахстан живёт по единому времени UTC+5 без перехода на летнее
ASTANA_TZ = timezone(timedelta(hours=5))
WEEKDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
MONTHS = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]

# Коды погоды WMO -> описание
WMO = {
    0: "☀️ Ясно",
    1: "🌤 Преимущественно ясно",
    2: "⛅️ Переменная облачность",
    3: "☁️ Пасмурно",
    45: "🌫 Туман",
    48: "🌫 Изморозь",
    51: "🌦 Лёгкая морось",
    53: "🌦 Морось",
    55: "🌦 Сильная морось",
    56: "🌧 Ледяная морось",
    57: "🌧 Сильная ледяная морось",
    61: "🌧 Небольшой дождь",
    63: "🌧 Дождь",
    65: "🌧 Сильный дождь",
    66: "🌧 Ледяной дождь",
    67: "🌧 Сильный ледяной дождь",
    71: "🌨 Небольшой снег",
    73: "🌨 Снег",
    75: "❄️ Сильный снег",
    77: "🌨 Снежные зёрна",
    80: "🌦 Небольшой ливень",
    81: "🌧 Ливень",
    82: "⛈ Сильный ливень",
    85: "🌨 Снегопад",
    86: "❄️ Сильный снегопад",
    95: "⛈ Гроза",
    96: "⛈ Гроза с градом",
    99: "⛈ Сильная гроза с градом",
}

# Цитаты: (текст, автор)
QUOTES = [
    ("Чтобы дойти до цели, надо прежде всего идти.", "Оноре де Бальзак"),
    ("Единственный способ делать великие дела — любить то, что ты делаешь.", "Стив Джобс"),
    ("Знание — сила.", "Фрэнсис Бэкон"),
    ("Я знаю, что ничего не знаю.", "Сократ"),
    ("Воображение важнее знания.", "Альберт Эйнштейн"),
    ("Образование — самое мощное оружие, которым можно изменить мир.", "Нельсон Мандела"),
    ("Дорогу осилит идущий.", "народная мудрость"),
    ("Терпение и труд всё перетрут.", "народная мудрость"),
    ("Век живи — век учись.", "народная мудрость"),
    ("Семь раз отмерь — один раз отрежь.", "народная мудрость"),
    ("Что посеешь, то и пожнёшь.", "народная мудрость"),
    ("Кто не рискует, тот не пьёт шампанского.", "народная мудрость"),
]

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger("weather-bot")
session = requests.Session()
keyboard_shown: set[int] = set()  # чаты, где уже показана Reply-клавиатура


# --------------------------------------------------------------------------
# Блоки ответа
# --------------------------------------------------------------------------
def get_time_text() -> str:
    now = datetime.now(ASTANA_TZ)
    return (
        f"🕐 <b>{now:%H:%M}</b>, {WEEKDAYS[now.weekday()]}, "
        f"{now.day} {MONTHS[now.month - 1]} {now.year} (Астана)"
    )


def get_weather_text() -> str:
    r = session.get(
        WEATHER_URL,
        params={
            "latitude": LAT,
            "longitude": LON,
            "current": (
                "temperature_2m,apparent_temperature,relative_humidity_2m,"
                "pressure_msl,wind_speed_10m,precipitation,weather_code"
            ),
            "wind_speed_unit": "ms",
            "timezone": "auto",
        },
        timeout=10,
    )
    r.raise_for_status()
    c = r.json()["current"]
    desc = WMO.get(c["weather_code"], "🌡 Погода")
    pressure_mmhg = round(c["pressure_msl"] * 0.750062)
    return (
        "<b>Погода в Астане</b>\n"
        f"{desc}\n\n"
        f"🌡 Температура: <b>{c['temperature_2m']:+.0f}°C</b> "
        f"(ощущается как {c['apparent_temperature']:+.0f}°C)\n"
        f"💧 Влажность: {c['relative_humidity_2m']}%\n"
        f"💨 Ветер: {c['wind_speed_10m']} м/с\n"
        f"🧭 Давление: {pressure_mmhg} мм рт. ст.\n"
        f"☔️ Осадки: {c['precipitation']} мм"
    )


def get_btc_text() -> str:
    r = session.get(
        BTC_URL,
        params={
            "ids": "bitcoin",
            "vs_currencies": "usd,kzt",
            "include_24hr_change": "true",
        },
        timeout=10,
    )
    r.raise_for_status()
    b = r.json()["bitcoin"]
    change = b.get("usd_24h_change")
    arrow = "" if change is None else ("📈" if change >= 0 else "📉")
    change_txt = "" if change is None else f" {arrow} {change:+.2f}% за 24 ч"
    return (
        "<b>Курс биткоина</b>\n"
        f"₿ <b>${b['usd']:,.0f}</b>{change_txt}\n"
        f"≈ {b['kzt']:,.0f} ₸".replace(",", " ")
    )


def get_rates_text() -> str:
    r = session.get(RATES_URL, timeout=10)
    r.raise_for_status()
    data = r.json()
    if data.get("result") != "success":
        raise RuntimeError(f"rates API: {data.get('error-type')}")
    rates = data["rates"]
    kzt = rates["KZT"]  # сколько тенге в 1 USD
    usd = kzt
    eur = kzt / rates["EUR"]
    rub100 = kzt / rates["RUB"] * 100
    cny = kzt / rates["CNY"]
    updated = datetime.fromtimestamp(data["time_last_update_unix"], ASTANA_TZ)

    def fmt(x: float) -> str:  # 1 234,56 -> «1 234.56» с пробелом-разделителем
        return f"{x:,.2f}".replace(",", " ")

    return (
        "<b>Курсы валют к тенге</b>\n"
        f"💵 1 USD = <b>{fmt(usd)} ₸</b>\n"
        f"💶 1 EUR = <b>{fmt(eur)} ₸</b>\n"
        f"🇷🇺 100 RUB = <b>{fmt(rub100)} ₸</b>\n"
        f"🇨🇳 1 CNY = <b>{fmt(cny)} ₸</b>\n"
        f"<i>Рыночный курс, обновлён {updated:%d.%m %H:%M}. "
        "Банки и обменники могут отличаться.</i>"
    )


def get_quote_text() -> str:
    text, author = random.choice(QUOTES)
    return f"💬 <i>«{html.escape(text)}»</i>\n— {html.escape(author)}"


# Разделы: ключ -> (функция, текст при сбое)
SECTIONS = {
    "time": (get_time_text, "Не удалось определить время."),
    "weather": (get_weather_text, "Не удалось получить погоду, попробуйте позже."),
    "crypto": (get_btc_text, "Не удалось получить курс биткоина."),
    "rates": (get_rates_text, "Не удалось получить курсы валют."),
    "quote": (get_quote_text, "Не удалось подобрать цитату."),
}
# Полная сводка: любое сообщение, не являющееся командой или кнопкой
SUMMARY = ("time", "weather", "crypto", "rates")


def build(key: str) -> str:
    """Собирает текст раздела или полной сводки ('all').
    Каждый блок строится независимо: сбой одного не ломает остальные."""
    keys = SUMMARY if key == "all" else (key,)
    parts = []
    for k in keys:
        func, fail_text = SECTIONS[k]
        try:
            parts.append(func())
        except Exception:
            log.exception("Сбой блока %s", k)
            parts.append(fail_text)
    return "\n\n".join(parts)


# --------------------------------------------------------------------------
# Клавиатуры и команды
# --------------------------------------------------------------------------
# Кнопки под строкой ввода: текст кнопки -> раздел
BUTTONS = {
    "🌤 Погода": "weather",
    "₿ Крипто": "crypto",
    "💵 Курсы валют": "rates",
    "💬 Цитата": "quote",
    "📋 Сводка": "all",
    "ℹ️ Помощь": "help",
}
MAIN_KEYBOARD = {
    "keyboard": [
        ["🌤 Погода", "₿ Крипто"],
        ["💵 Курсы валют", "💬 Цитата"],
        ["📋 Сводка", "ℹ️ Помощь"],
    ],
    "resize_keyboard": True,
    "is_persistent": True,
    "input_field_placeholder": "Выберите кнопку или напишите что угодно",
}

# Меню команд (кнопка «Меню» в чате с ботом)
COMMANDS = [
    ("start", "Начать и показать кнопки"),
    ("weather", "Погода в Астане"),
    ("crypto", "Курс биткоина"),
    ("rates", "Курсы валют к тенге"),
    ("quote", "Случайная цитата"),
    ("time", "Время в Астане"),
    ("summary", "Полная сводка"),
    ("help", "Список команд"),
]
# Команда -> раздел
COMMAND_KEYS = {
    "weather": "weather",
    "crypto": "crypto",
    "btc": "crypto",
    "rates": "rates",
    "quote": "quote",
    "time": "time",
    "summary": "all",
}

HELP_TEXT = (
    "<b>Что умеет бот</b>\n"
    "/weather — погода в Астане\n"
    "/crypto — курс биткоина\n"
    "/rates — курсы валют к тенге\n"
    "/quote — случайная цитата\n"
    "/time — время в Астане\n"
    "/summary — всё сразу\n"
    "/help — этот список\n\n"
    "Те же действия доступны кнопками под строкой ввода. "
    "Под ответами есть кнопка «Обновить». Любое другое сообщение — полная сводка."
)


def refresh_keyboard(key: str) -> dict:
    label = "🔄 Другая цитата" if key == "quote" else "🔄 Обновить"
    return {"inline_keyboard": [[{"text": label, "callback_data": f"r:{key}"}]]}


def resolve(text: str) -> str:
    """Определяет, что запросил пользователь: start/help/раздел/all."""
    text = (text or "").strip()
    if text in BUTTONS:
        return BUTTONS[text]
    if text.startswith("/"):
        # '/weather@bot_name arg' -> 'weather'
        cmd = text[1:].split()[0].split("@")[0].lower()
        if cmd in ("start", "help"):
            return cmd
        if cmd in COMMAND_KEYS:
            return COMMAND_KEYS[cmd]
    return "all"


# --------------------------------------------------------------------------
# Bot API
# --------------------------------------------------------------------------
def tg(method: str, **params):
    """Вызов метода Bot API; возвращает result или бросает исключение."""
    r = session.post(f"{API}/{method}", json=params, timeout=POLL_TIMEOUT + 10)
    data = r.json()
    if not data.get("ok"):
        retry = (data.get("parameters") or {}).get("retry_after")
        if retry:
            log.warning("Flood control, ждём %s с", retry)
            time.sleep(retry)
        raise RuntimeError(f"{method}: {data.get('error_code')} {data.get('description')}")
    return data["result"]


def handle_message(msg: dict) -> None:
    chat_id = msg["chat"]["id"]
    key = resolve(msg.get("text"))
    if key in ("start", "help"):  # эти ответы сами несут клавиатуру
        keyboard_shown.add(chat_id)

    if key == "start":
        name = html.escape((msg.get("from") or {}).get("first_name") or "")
        greeting = f"Привет, {name}! " if name else "Привет! "
        tg(
            "sendMessage",
            chat_id=chat_id,
            text=greeting
            + "Я показываю время и погоду в Астане, курс биткоина, курсы валют "
            "и цитаты. Выберите кнопку под строкой ввода или команду из меню.",
            parse_mode="HTML",
            reply_markup=MAIN_KEYBOARD,
        )
        return
    if key == "help":
        tg(
            "sendMessage",
            chat_id=chat_id,
            text=HELP_TEXT,
            parse_mode="HTML",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    # Кнопки под строкой ввода показываются только после сообщения с
    # reply_markup. Чтобы не требовать /start, шлём их при первом сообщении
    # из личного чата (после перезапуска бота — ещё раз, это безвредно).
    if msg["chat"].get("type") == "private" and chat_id not in keyboard_shown:
        keyboard_shown.add(chat_id)
        try:
            tg(
                "sendMessage",
                chat_id=chat_id,
                text="Кнопки меню — под строкой ввода 👇",
                reply_markup=MAIN_KEYBOARD,
            )
        except Exception:
            keyboard_shown.discard(chat_id)
            log.warning("Не удалось показать клавиатуру")

    try:
        tg("sendChatAction", chat_id=chat_id, action="typing")
    except Exception:
        log.warning("sendChatAction не удался")
    tg(
        "sendMessage",
        chat_id=chat_id,
        text=build(key),
        parse_mode="HTML",
        reply_markup=refresh_keyboard(key),
    )


def handle_callback(cq: dict) -> None:
    """Нажатие inline-кнопки «Обновить»: правим то же сообщение."""
    answer = {"callback_query_id": cq["id"]}
    try:
        data = cq.get("data") or ""
        msg = cq.get("message")
        key = data[2:] if data.startswith("r:") else None
        if not msg or (key != "all" and key not in SECTIONS):
            return
        try:
            tg(
                "editMessageText",
                chat_id=msg["chat"]["id"],
                message_id=msg["message_id"],
                text=build(key),
                parse_mode="HTML",
                reply_markup=refresh_keyboard(key),
            )
        except RuntimeError as e:
            if "not modified" in str(e):
                answer["text"] = "Без изменений"
            else:
                raise
    finally:
        # На каждый callback нужно ответить, иначе у кнопки крутится индикатор
        try:
            tg("answerCallbackQuery", **answer)
        except Exception:
            log.warning("answerCallbackQuery не удался")


def main() -> None:
    me = tg("getMe")
    log.info("Бот запущен: @%s", me["username"])
    # Если раньше был установлен webhook — getUpdates не будет работать
    tg("deleteWebhook", drop_pending_updates=True)
    # Меню команд
    tg("setMyCommands", commands=[{"command": c, "description": d} for c, d in COMMANDS])

    # Сообщения, пришедшие, пока бот был офлайн, игнорируем: offset=-1 берёт
    # только самое последнее обновление и подтверждает (забывает) все прежние.
    offset = None
    stale = tg("getUpdates", offset=-1, timeout=0)
    if stale:
        offset = stale[-1]["update_id"] + 1
        log.info("Пропущены сообщения, пришедшие в офлайне (до update_id %s)", stale[-1]["update_id"])

    while True:
        try:
            params = {
                "timeout": POLL_TIMEOUT,
                "allowed_updates": ["message", "callback_query"],
            }
            if offset is not None:
                params["offset"] = offset
            updates = tg("getUpdates", **params)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            log.warning("Ошибка getUpdates: %s", e)
            time.sleep(3)
            continue

        for upd in updates:
            offset = upd["update_id"] + 1
            try:
                if upd.get("message"):
                    handle_message(upd["message"])
                elif upd.get("callback_query"):
                    handle_callback(upd["callback_query"])
            except Exception:
                log.exception("Ошибка обработки update %s", upd["update_id"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Остановлено")
