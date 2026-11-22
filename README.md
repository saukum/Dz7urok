# Telegram-бот: погода, биткоин и курсы валют

Учебный Telegram-бот на Python. Показывает время и погоду в Астане, курс биткоина, курсы валют к тенге и случайные цитаты. Управляется командами, кнопками под строкой ввода и inline-кнопкой «Обновить».

## Возможности

| Команда | Кнопка | Что делает |
|---|---|---|
| `/start` | — | Приветствие и показ кнопок |
| `/weather` | 🌤 Погода | Погода в Астане |
| `/crypto` | ₿ Крипто | Курс биткоина в USD и тенге, изменение за 24 ч |
| `/rates` | 💵 Курсы валют | USD, EUR, 100 RUB, CNY к тенге |
| `/quote` | 💬 Цитата | Случайная цитата |
| `/time` | — | Время в Астане |
| `/summary` | 📋 Сводка | Время, погода, биткоин и валюты сразу |
| `/help` | ℹ️ Помощь | Список команд |

- Любое другое сообщение (включая фото, стикеры и т. д.) — полная сводка.
- Под ответами есть кнопка «🔄 Обновить» (у цитаты «🔄 Другая цитата»): она правит то же сообщение, а не шлёт новое.
- Каждый блок ответа запрашивается независимо: если один источник недоступен, остальные всё равно придут.
- Сообщения, отправленные боту, пока он был выключен, при запуске игнорируются.

## Быстрый старт

Нужен Python 3.10+ и токен бота от [@BotFather](https://t.me/BotFather).

1. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
2. Создайте файл `.env` в корне проекта и впишите токен:
   ```
   BOT_TOKEN=ваш_токен_от_BotFather
   ```
   Файл `.env` исключён из git через `.gitignore`, не коммитьте его и не показывайте токен другим.
3. Запустите бота:
   ```bash
   python bot.py
   ```
   Остановка — `Ctrl+C`.

Одновременно должен работать только один экземпляр бота, иначе `getUpdates` будет конфликтовать.

## Используемые API

Все внешние API бесплатные и не требуют ключей.

### Telegram Bot API
Основа бота. Адрес: `https://api.telegram.org/bot<токен>/МЕТОД`, запросы POST с JSON, ответ `{"ok": true, "result": ...}`. [Документация](https://core.telegram.org/bots/api).

| Метод | Зачем |
|---|---|
| `getMe` | Проверка токена при старте |
| `deleteWebhook` | Сброс webhook, чтобы работал `getUpdates` |
| `setMyCommands` | Меню команд |
| `getUpdates` | Получение сообщений через long polling (`timeout=30`, `allowed_updates=[message, callback_query]`). Запрос с `offset=-1` при старте пропускает сообщения, пришедшие в офлайне |
| `sendMessage` | Ответы с `parse_mode=HTML` и клавиатурами в `reply_markup` |
| `sendChatAction` | Статус «печатает…» |
| `editMessageText` | Обновление сообщения по кнопке «Обновить» |
| `answerCallbackQuery` | Ответ на нажатие inline-кнопки |

Используются объекты `Update`, `Message`, `CallbackQuery`, `ReplyKeyboardMarkup` (кнопки под строкой ввода), `InlineKeyboardMarkup` (кнопка «Обновить») и `BotCommand`.

### Open-Meteo — погода
`GET https://api.open-meteo.com/v1/forecast` ([документация](https://open-meteo.com/en/docs))

- Параметры: координаты Астаны (51.1694, 71.4491), `current=`, `wind_speed_unit=ms`, `timezone=auto`.
- Поля: `temperature_2m`, `apparent_temperature`, `relative_humidity_2m`, `pressure_msl`, `wind_speed_10m`, `precipitation`, `weather_code`.
- Код погоды (WMO) переводится в текст с эмодзи, давление пересчитывается из гПа в мм рт. ст.
- Бесплатно для некоммерческого использования.

### CoinGecko — курс биткоина
`GET https://api.coingecko.com/api/v3/simple/price` ([документация](https://docs.coingecko.com))

- Параметры: `ids=bitcoin`, `vs_currencies=usd,kzt`, `include_24hr_change=true`.
- У бесплатного доступа есть лимит запросов в минуту. При большой нагрузке стоит добавить кэширование.

### ExchangeRate-API (open.er-api.com) — курсы валют
`GET https://open.er-api.com/v6/latest/USD` ([документация](https://www.exchangerate-api.com/docs/free))

- Ответ содержит курсы всех валют к USD. Бот считает, сколько тенге стоят 1 USD, 1 EUR, 100 RUB и 1 CNY.
- Данные обновляются раз в сутки. Это рыночный курс: он может отличаться от банковского и от официального курса Нацбанка РК.
- Бесплатный доступ может требовать указания источника, проверьте условия на сайте сервиса.

Время берётся из системных часов со сдвигом UTC+5 (в Казахстане нет перехода на летнее время), цитаты хранятся списком в коде.

## Структура проекта

```
bot.py            весь код бота
requirements.txt  зависимости (requests, python-dotenv)
.env              токен бота (не в git)
.gitignore        исключения для git
CLAUDE.md         заметки о проекте для Claude Code
```

Главные части `bot.py`: функции `get_*_text` (получение данных), `SECTIONS` и `build` (сборка ответов), `BUTTONS`, `COMMANDS` и `resolve` (маршрутизация), `tg` (вызов Bot API), `handle_message`, `handle_callback` и `main`.

## Как добавить новый раздел

1. Написать функцию `get_xxx_text()` в `bot.py`.
2. Добавить её в `SECTIONS` и, при необходимости, в `SUMMARY`.
3. Добавить команду в `COMMANDS` и `COMMAND_KEYS`, кнопку в `BUTTONS` и `MAIN_KEYBOARD`, строку в `HELP_TEXT`.
