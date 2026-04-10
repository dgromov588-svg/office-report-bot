# Office Reports Bot

Telegram-бот для офисных отчётов с записью в Google Sheets.

## Что лежит в репозитории
- `office-report-bot-package.zip` — полная рабочая сборка проекта
- `.env.example` — шаблон переменных окружения
- `requirements.txt` — зависимости
- `.gitignore` — защита от случайного коммита секретов и служебных файлов

## Важно по безопасности
Никогда не коммить:
- реальный `TELEGRAM_BOT_TOKEN`
- `service_account.json`
- файл `.env`

Если токен уже был отправлен в чат или где-либо засвечен, его нужно немедленно перевыпустить в BotFather.

## Что умеет бот
- кнопочные меню по ролям: менеджер, тимлид, хед, админ
- отчёт менеджера в формате `сделано/план`
- отдельные отчёты тимлида и хеда
- проверка менеджеров тимлидом
- проверка тимлидов хедом
- `👥 Моя команда` для тимлида и хеда
- `📌 Мой статус`, `📈 Сводка сегодня`, `🆔 Мой ID`
- причины отклонения кнопками
- `🔁 Исправить и пересдать`

## Быстрый старт
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python bot.py
```

## Шаги после скачивания сборки
1. Распаковать `office-report-bot-package.zip`
2. Импортировать `office_reports_template.xlsx` в Google Sheets
3. Создать Telegram-бота через BotFather
4. Создать service account в Google Cloud и выдать ему доступ к таблице
5. Заполнить `.env`
6. Запустить `bot.py`
