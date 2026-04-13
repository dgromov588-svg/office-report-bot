
import os
import re
import time
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional, List, Tuple

import requests
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
GOOGLE_SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID", "")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json")
BOT_TIMEZONE = os.getenv("BOT_TIMEZONE", "Europe/Kyiv")
ALLOWED_CHAT_IDS_RAW = os.getenv("ALLOWED_CHAT_IDS", "").strip()

MANAGER_CHAT_IDS = os.getenv("MANAGER_CHAT_IDS", "")
TEAMLEAD_CHAT_IDS = os.getenv("TEAMLEAD_CHAT_IDS", "")
HEAD_CHAT_IDS = os.getenv("HEAD_CHAT_IDS", "")
SUPERVISOR_CHAT_IDS = os.getenv("SUPERVISOR_CHAT_IDS", "")
ADMIN_CHAT_IDS = os.getenv("ADMIN_CHAT_IDS", "")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

SETTINGS_SHEET = "Settings"
MANAGER_SHEET = "Manager_Reports"
TEAMLEAD_SHEET = "TeamLead_Reports"
HEAD_SHEET = "Head_Reports"

ROLE_MANAGER = "manager"
ROLE_TEAMLEAD = "teamlead"
ROLE_HEAD = "head"
ROLE_SUPERVISOR = "supervisor"
ROLE_ADMIN = "admin"

PENDING_STATUS = "На проверке"
APPROVED_STATUS = "Подтвержден"
REJECTED_STATUS = "Отклонён"
NO_REVIEWER_STATUS = "Без проверяющего"
NO_REVIEW_STATUS = "Без проверки"
PRIMARY_SUBMISSION = "Первичная"
RESUBMISSION = "Пересдача"

PRESET_REJECTION_REASONS = {
    "incomplete": "Неполный отчёт",
    "numbers": "Ошибка в цифрах",
    "total": "Нет тотала",
    "format": "Не тот формат",
}

MANAGER_METRICS = [
    {
        "key": "numbers_for_check",
        "label": "Номеров на проверку",
        "question": "1/6. Номеров на проверку — отправьте в формате сделано/план\nПример: 15/20",
    },
    {
        "key": "positive",
        "label": "Плюсовых",
        "question": "2/6. Плюсовых — отправьте в формате сделано/план\nПример: 4/7",
    },
    {
        "key": "active",
        "label": "Актив",
        "question": "3/6. Актив — отправьте в формате сделано/план\nПример: 10/12",
    },
    {
        "key": "throw_in",
        "label": "Вброс",
        "question": "4/6. Вброс — отправьте в формате сделано/план\nПример: 6/8",
    },
    {
        "key": "proposal",
        "label": "Предлог",
        "question": "5/6. Предлог — отправьте в формате сделано/план\nПример: 3/5",
    },
    {
        "key": "agreements",
        "label": "Согласий",
        "question": "6/6. Согласий — отправьте в формате сделано/план\nПример: 2/4",
    },
]

LEADER_FIELDS = [
    {"key": "team_count", "label": "Команда кол-во", "question": "1/12. Команда кол-во — отправьте число", "type": "int"},
    {"key": "total_active", "label": "Общий актив", "question": "2/12. Общий актив — отправьте число", "type": "int"},
    {"key": "numbers_taken", "label": "Взято всего номеров", "question": "3/12. Взято всего номеров — отправьте число", "type": "int"},
    {"key": "positive", "label": "Плюсовые", "question": "4/12. Плюсовые — отправьте число", "type": "int"},
    {"key": "avg_active_per_manager", "label": "Средний актив на менеджера", "question": "5/12. Средний актив на менеджера — отправьте число", "type": "int"},
    {"key": "throw_in", "label": "Кол-во вбросов", "question": "6/12. Кол-во вбросов — отправьте число", "type": "int"},
    {"key": "proposal", "label": "Кол-во предлог", "question": "7/12. Кол-во предлог — отправьте число", "type": "int"},
    {"key": "agreements", "label": "Кол-во согласий", "question": "8/12. Кол-во согласий — отправьте число", "type": "int"},
    {"key": "leads", "label": "Лиды", "question": "9/12. Лиды — отправьте число", "type": "int"},
    {"key": "deposits", "label": "Депы", "question": "10/12. Депы — отправьте число", "type": "int"},
    {"key": "plan", "label": "План", "question": "11/12. План — отправьте число", "type": "int"},
    {"key": "total", "label": "Тотал", "question": "12/12. Тотал — отправьте в формате сделано/план\nПример: 9/3", "type": "pair"},
]

MANAGER_HEADERS = [
    "Дата",
    "Время",
    "Reporter chat id",
    "Reporter name",
    "Teamlead chat id",
    "Номеров сделано",
    "Номеров план",
    "Плюсовых сделано",
    "Плюсовых план",
    "Актив сделано",
    "Актив план",
    "Вброс сделано",
    "Вброс план",
    "Предлог сделано",
    "Предлог план",
    "Согласий сделано",
    "Согласий план",
    "Created at",
    "Reviewer chat id",
    "Review status",
    "Reviewed by",
    "Reviewed at",
    "Review comment",
    "Submission type",
    "Previous rejected row",
]

TEAMLEAD_HEADERS = [
    "Дата",
    "Время",
    "Role",
    "Reporter chat id",
    "Reporter name",
    "Head chat id",
    "Команда кол-во",
    "Общий актив",
    "Взято всего номеров",
    "Плюсовые",
    "Средний актив на менеджера",
    "Кол-во вбросов",
    "Кол-во предлог",
    "Кол-во согласий",
    "Лиды",
    "Депы",
    "План",
    "Тотал сделано",
    "Тотал план",
    "Created at",
    "Reviewer chat id",
    "Review status",
    "Reviewed by",
    "Reviewed at",
    "Review comment",
    "Submission type",
    "Previous rejected row",
]

HEAD_HEADERS = [
    "Дата",
    "Время",
    "Role",
    "Reporter chat id",
    "Reporter name",
    "Команда кол-во",
    "Общий актив",
    "Взято всего номеров",
    "Плюсовые",
    "Средний актив на менеджера",
    "Кол-во вбросов",
    "Кол-во предлог",
    "Кол-во согласий",
    "Лиды",
    "Депы",
    "План",
    "Тотал сделано",
    "Тотал план",
    "Created at",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

user_states: Dict[int, Dict[str, Any]] = {}


def parse_chat_ids(raw: str) -> set[int]:
    result = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            result.add(int(part))
        except ValueError:
            continue
    return result


MANAGER_IDS = parse_chat_ids(MANAGER_CHAT_IDS)
TEAMLEAD_IDS = parse_chat_ids(TEAMLEAD_CHAT_IDS)
HEAD_IDS = parse_chat_ids(HEAD_CHAT_IDS)
SUPERVISOR_IDS = parse_chat_ids(SUPERVISOR_CHAT_IDS)
ADMIN_IDS = parse_chat_ids(ADMIN_CHAT_IDS)
ALLOWED_IDS = parse_chat_ids(ALLOWED_CHAT_IDS_RAW)


def require_env() -> None:
    missing = []
    for var_name, value in [
        ("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN),
        ("GOOGLE_SPREADSHEET_ID", GOOGLE_SPREADSHEET_ID),
        ("GOOGLE_CREDENTIALS_FILE", GOOGLE_CREDENTIALS_FILE),
    ]:
        if not value:
            missing.append(var_name)

    if missing:
        raise RuntimeError(f"Не заданы переменные окружения: {', '.join(missing)}")

    if not os.path.exists(GOOGLE_CREDENTIALS_FILE):
        raise FileNotFoundError(f"Файл сервисного аккаунта не найден: {GOOGLE_CREDENTIALS_FILE}")


def is_chat_allowed(chat_id: int) -> bool:
    if not ALLOWED_IDS:
        return True
    return chat_id in ALLOWED_IDS


def get_role(chat_id: int) -> Optional[str]:
    if chat_id in ADMIN_IDS:
        return ROLE_ADMIN
    if chat_id in SUPERVISOR_IDS:
        return ROLE_SUPERVISOR
    if chat_id in HEAD_IDS:
        return ROLE_HEAD
    if chat_id in TEAMLEAD_IDS:
        return ROLE_TEAMLEAD
    if chat_id in MANAGER_IDS:
        return ROLE_MANAGER
    return None


def now_local() -> datetime:
    return datetime.now(ZoneInfo(BOT_TIMEZONE))


def today_str() -> str:
    return now_local().strftime("%Y-%m-%d")


def format_dt() -> Tuple[str, str, str]:
    dt = now_local()
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S"), dt.strftime("%Y-%m-%d %H:%M:%S")


def get_display_name(user: Dict[str, Any]) -> str:
    full_name = " ".join(filter(None, [user.get("first_name", ""), user.get("last_name", "")])).strip()
    username = user.get("username", "")
    if full_name:
        return full_name
    if username:
        return f"@{username}"
    return str(user.get("id", ""))


def build_reply_keyboard(rows: List[List[str]]) -> Dict[str, Any]:
    return {
        "keyboard": [[{"text": item} for item in row] for row in rows],
        "resize_keyboard": True,
        "one_time_keyboard": False,
    }


def build_inline_keyboard(button_rows: List[List[Tuple[str, str]]]) -> Dict[str, Any]:
    return {
        "inline_keyboard": [
            [{"text": title, "callback_data": callback_data} for title, callback_data in row]
            for row in button_rows
        ]
    }


def main_menu(role: Optional[str]) -> List[List[str]]:
    if role == ROLE_MANAGER:
        return [
            ["📝 Отчёт менеджера"],
            ["📌 Мой статус", "📈 Сводка сегодня"],
            ["🆔 Мой ID"],
        ]
    if role == ROLE_TEAMLEAD:
        return [
            ["👔 Отчёт тимлида"],
            ["✅ Проверить менеджеров", "👥 Моя команда"],
            ["📌 Мой статус", "📈 Сводка сегодня"],
            ["🆔 Мой ID"],
        ]
    if role in {ROLE_HEAD, ROLE_SUPERVISOR}:
        return [
            ["🧠 Отчёт хеда"],
            ["✅ Проверить тимлидов", "👥 Моя команда"],
            ["📌 Мой статус", "📈 Сводка сегодня"],
            ["🆔 Мой ID"],
        ]
    if role == ROLE_ADMIN:
        return [
            ["📝 Отчёт менеджера", "👔 Отчёт тимлида"],
            ["🧠 Отчёт хеда"],
            ["✅ Проверить менеджеров", "✅ Проверить тимлидов"],
            ["👥 Моя команда", "📈 Сводка сегодня"],
            ["📌 Мой статус", "🆔 Мой ID"],
        ]
    return [["🆔 Мой ID"]]


def telegram_request(method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    response = requests.post(f"{BASE_URL}/{method}", json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")
    return data


def send_message(chat_id: int, text: str, reply_keyboard: Optional[List[List[str]]] = None, inline_keyboard: Optional[List[List[Tuple[str, str]]]] = None) -> None:
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
    }
    if inline_keyboard:
        payload["reply_markup"] = build_inline_keyboard(inline_keyboard)
    elif reply_keyboard:
        payload["reply_markup"] = build_reply_keyboard(reply_keyboard)
    telegram_request("sendMessage", payload)


def edit_message(chat_id: int, message_id: int, text: str, inline_keyboard: Optional[List[List[Tuple[str, str]]]] = None) -> None:
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
    }
    if inline_keyboard:
        payload["reply_markup"] = build_inline_keyboard(inline_keyboard)
    telegram_request("editMessageText", payload)


def answer_callback(callback_id: str, text: Optional[str] = None) -> None:
    payload: Dict[str, Any] = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text
    try:
        telegram_request("answerCallbackQuery", payload)
    except Exception:
        logger.exception("Не удалось ответить на callback")


def get_updates(offset: Optional[int]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"timeout": 25}
    if offset is not None:
        payload["offset"] = offset
    return telegram_request("getUpdates", payload)


def get_sheets_service():
    credentials = Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_FILE,
        scopes=SCOPES,
    )
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def col_letter(index_1based: int) -> str:
    result = ""
    while index_1based:
        index_1based, remainder = divmod(index_1based - 1, 26)
        result = chr(65 + remainder) + result
    return result


def get_sheet_values(sheet_name: str) -> List[List[Any]]:
    service = get_sheets_service()
    resp = service.spreadsheets().values().get(
        spreadsheetId=GOOGLE_SPREADSHEET_ID,
        range=f"{sheet_name}!A:Z",
    ).execute()
    return resp.get("values", [])


def append_row(sheet_name: str, row: List[Any]) -> None:
    service = get_sheets_service()
    service.spreadsheets().values().append(
        spreadsheetId=GOOGLE_SPREADSHEET_ID,
        range=f"{sheet_name}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()


def update_row_fields(sheet_name: str, row_number: int, updates: Dict[int, Any]) -> None:
    service = get_sheets_service()
    data = []
    for column_number, value in updates.items():
        cell = f"{sheet_name}!{col_letter(column_number)}{row_number}"
        data.append({"range": cell, "values": [[value]]})
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=GOOGLE_SPREADSHEET_ID,
        body={
            "valueInputOption": "USER_ENTERED",
            "data": data,
        },
    ).execute()


def ensure_sheet_headers(sheet_name: str, headers: List[str]) -> None:
    service = get_sheets_service()
    resp = service.spreadsheets().values().get(
        spreadsheetId=GOOGLE_SPREADSHEET_ID,
        range=f"{sheet_name}!1:1",
    ).execute()
    values = resp.get("values", [])
    if values and values[0][:len(headers)] == headers:
        return
    service.spreadsheets().values().update(
        spreadsheetId=GOOGLE_SPREADSHEET_ID,
        range=f"{sheet_name}!A1:{col_letter(len(headers))}1",
        valueInputOption="RAW",
        body={"values": [headers]},
    ).execute()


def ensure_sheets_ready() -> None:
    ensure_sheet_headers(MANAGER_SHEET, MANAGER_HEADERS)
    ensure_sheet_headers(TEAMLEAD_SHEET, TEAMLEAD_HEADERS)
    ensure_sheet_headers(HEAD_SHEET, HEAD_HEADERS)


def normalize_chat_id(raw: Any) -> str:
    return str(raw).strip() if raw is not None else ""


def settings_rows() -> List[List[Any]]:
    return get_sheet_values(SETTINGS_SHEET)


def get_manager_mappings() -> List[Dict[str, str]]:
    rows = settings_rows()
    items = []
    for row in rows[2:]:
        if not row or len(row) < 4:
            continue
        active = str(row[3]).strip().lower()
        if active not in {"1", "true", "yes", "y", "active", "да"}:
            continue
        items.append({
            "name": str(row[0]).strip(),
            "chat_id": normalize_chat_id(row[1]),
            "teamlead_chat_id": normalize_chat_id(row[2]),
        })
    return items


def get_teamlead_mappings() -> List[Dict[str, str]]:
    rows = settings_rows()
    items = []
    for row in rows[2:]:
        if len(row) < 8:
            continue
        active = str(row[7]).strip().lower() if len(row) > 7 else ""
        if active not in {"1", "true", "yes", "y", "active", "да"}:
            continue
        items.append({
            "name": str(row[4]).strip(),
            "chat_id": normalize_chat_id(row[5]),
            "head_chat_id": normalize_chat_id(row[6]),
        })
    return items


def get_head_mappings() -> List[Dict[str, str]]:
    rows = settings_rows()
    items = []
    for row in rows[2:]:
        if len(row) < 10:
            continue
        head_name = str(row[8]).strip()
        head_chat_id = normalize_chat_id(row[9])
        if not head_name or not head_chat_id:
            continue
        items.append({"name": head_name, "chat_id": head_chat_id})
    return items


def find_manager_mapping(chat_id: int) -> Optional[Dict[str, str]]:
    chat_id_str = str(chat_id)
    for item in get_manager_mappings():
        if item["chat_id"] == chat_id_str:
            return item
    return None


def find_teamlead_mapping(chat_id: int) -> Optional[Dict[str, str]]:
    chat_id_str = str(chat_id)
    for item in get_teamlead_mappings():
        if item["chat_id"] == chat_id_str:
            return item
    return None


def parse_done_plan(raw: str) -> Tuple[int, int]:
    parts = re.findall(r"-?\d+", raw.replace(",", "."))
    if len(parts) < 2:
        raise ValueError("Ожидался формат сделано/план")
    return int(parts[0]), int(parts[1])


def parse_int_value(raw: str) -> int:
    match = re.search(r"-?\d+", raw)
    if not match:
        raise ValueError("Ожидалось число")
    return int(match.group(0))


def clear_state(chat_id: int) -> None:
    user_states.pop(chat_id, None)


def start_manager_report(
    chat_id: int,
    user: Dict[str, Any],
    submission_type: str = PRIMARY_SUBMISSION,
    previous_rejected_row: str = "",
) -> None:
    user_states[chat_id] = {
        "mode": "manager_report",
        "step": 0,
        "data": {
            "reporter_chat_id": chat_id,
            "reporter_name": get_display_name(user),
            "created_at": format_dt()[2],
            "submission_type": submission_type,
            "previous_rejected_row": previous_rejected_row,
        },
    }
    intro = "Начинаем отчёт менеджера. Все показатели вводятся в формате сделано/план."
    if submission_type == RESUBMISSION:
        intro = "Исправьте отчёт менеджера и отправьте заново. Все показатели вводятся в формате сделано/план."
    send_message(chat_id, intro, reply_keyboard=main_menu(get_role(chat_id)))
    ask_next_question(chat_id)


def start_leader_report(
    chat_id: int,
    user: Dict[str, Any],
    role: str,
    submission_type: str = PRIMARY_SUBMISSION,
    previous_rejected_row: str = "",
) -> None:
    mode = "teamlead_report" if role == ROLE_TEAMLEAD else "head_report"
    title = "тимлида" if role == ROLE_TEAMLEAD else "хеда"
    user_states[chat_id] = {
        "mode": mode,
        "step": 0,
        "data": {
            "role": role,
            "reporter_chat_id": chat_id,
            "reporter_name": get_display_name(user),
            "created_at": format_dt()[2],
            "submission_type": submission_type,
            "previous_rejected_row": previous_rejected_row,
        },
    }
    intro = f"Начинаем отчёт {title}. Последний пункт — тотал в формате сделано/план."
    if submission_type == RESUBMISSION:
        intro = f"Исправьте отчёт {title} и отправьте заново. Последний пункт — тотал в формате сделано/план."
    send_message(chat_id, intro, reply_keyboard=main_menu(get_role(chat_id)))
    ask_next_question(chat_id)


def ask_next_question(chat_id: int) -> None:
    state = user_states.get(chat_id)
    if not state:
        return

    mode = state.get("mode")
    step = state.get("step", 0)

    if mode == "manager_report":
        if step >= len(MANAGER_METRICS):
            send_manager_preview(chat_id)
            return
        send_message(chat_id, MANAGER_METRICS[step]["question"], reply_keyboard=main_menu(get_role(chat_id)))
        return

    if mode in {"teamlead_report", "head_report"}:
        if step >= len(LEADER_FIELDS):
            send_leader_preview(chat_id)
            return
        send_message(chat_id, LEADER_FIELDS[step]["question"], reply_keyboard=main_menu(get_role(chat_id)))
        return


def send_manager_preview(chat_id: int) -> None:
    data = user_states[chat_id]["data"]
    lines = [
        "Проверьте отчёт менеджера:",
        f"Менеджер: {data.get('reporter_name', '')}",
    ]
    for metric in MANAGER_METRICS:
        done_val = data[f"{metric['key']}_done"]
        plan_val = data[f"{metric['key']}_plan"]
        lines.append(f"{metric['label']}: {done_val}/{plan_val}")
    send_message(
        chat_id,
        "\n".join(lines),
        inline_keyboard=[
            [("✅ Сохранить", "save_report"), ("🔄 Заполнить заново", "restart_report")],
            [("❌ Отмена", "cancel_report")]
        ],
    )


def send_leader_preview(chat_id: int) -> None:
    data = user_states[chat_id]["data"]
    title = "тимлида" if user_states[chat_id]["mode"] == "teamlead_report" else "хеда"
    lines = [
        f"Проверьте отчёт {title}:",
        f"Репортёр: {data.get('reporter_name', '')}",
    ]
    for field in LEADER_FIELDS:
        value = data.get(field["key"])
        if field["type"] == "pair":
            value = f"{data.get('total_done', 0)}/{data.get('total_plan', 0)}"
        lines.append(f"{field['label']}: {value}")
    send_message(
        chat_id,
        "\n".join(lines),
        inline_keyboard=[
            [("✅ Сохранить", "save_report"), ("🔄 Заполнить заново", "restart_report")],
            [("❌ Отмена", "cancel_report")]
        ],
    )


def save_current_report(chat_id: int) -> None:
    state = user_states.get(chat_id)
    if not state:
        return

    date_str, time_str, created_at = format_dt()
    data = state["data"]
    mode = state["mode"]

    if mode == "manager_report":
        mapping = find_manager_mapping(chat_id)
        reviewer_chat_id = mapping["teamlead_chat_id"] if mapping else ""
        review_status = PENDING_STATUS if reviewer_chat_id else NO_REVIEWER_STATUS
        row = [
            date_str,
            time_str,
            str(chat_id),
            data.get("reporter_name", ""),
            reviewer_chat_id,
            data.get("numbers_for_check_done", 0),
            data.get("numbers_for_check_plan", 0),
            data.get("positive_done", 0),
            data.get("positive_plan", 0),
            data.get("active_done", 0),
            data.get("active_plan", 0),
            data.get("throw_in_done", 0),
            data.get("throw_in_plan", 0),
            data.get("proposal_done", 0),
            data.get("proposal_plan", 0),
            data.get("agreements_done", 0),
            data.get("agreements_plan", 0),
            created_at,
            reviewer_chat_id,
            review_status,
            "",
            "",
            "",
            data.get("submission_type", PRIMARY_SUBMISSION),
            data.get("previous_rejected_row", ""),
        ]
        append_row(MANAGER_SHEET, row)
        clear_state(chat_id)
        send_message(chat_id, f"Отчёт менеджера сохранён.\nСтатус: {review_status}", reply_keyboard=main_menu(get_role(chat_id)))
        return

    if mode == "teamlead_report":
        mapping = find_teamlead_mapping(chat_id)
        reviewer_chat_id = mapping["head_chat_id"] if mapping else ""
        review_status = PENDING_STATUS if reviewer_chat_id else NO_REVIEWER_STATUS
        row = [
            date_str,
            time_str,
            ROLE_TEAMLEAD,
            str(chat_id),
            data.get("reporter_name", ""),
            reviewer_chat_id,
            data.get("team_count", 0),
            data.get("total_active", 0),
            data.get("numbers_taken", 0),
            data.get("positive", 0),
            data.get("avg_active_per_manager", 0),
            data.get("throw_in", 0),
            data.get("proposal", 0),
            data.get("agreements", 0),
            data.get("leads", 0),
            data.get("deposits", 0),
            data.get("plan", 0),
            data.get("total_done", 0),
            data.get("total_plan", 0),
            created_at,
            reviewer_chat_id,
            review_status,
            "",
            "",
            "",
            data.get("submission_type", PRIMARY_SUBMISSION),
            data.get("previous_rejected_row", ""),
        ]
        append_row(TEAMLEAD_SHEET, row)
        clear_state(chat_id)
        send_message(chat_id, f"Отчёт тимлида сохранён.\nСтатус: {review_status}", reply_keyboard=main_menu(get_role(chat_id)))
        return

    if mode == "head_report":
        row = [
            date_str,
            time_str,
            ROLE_HEAD,
            str(chat_id),
            data.get("reporter_name", ""),
            data.get("team_count", 0),
            data.get("total_active", 0),
            data.get("numbers_taken", 0),
            data.get("positive", 0),
            data.get("avg_active_per_manager", 0),
            data.get("throw_in", 0),
            data.get("proposal", 0),
            data.get("agreements", 0),
            data.get("leads", 0),
            data.get("deposits", 0),
            data.get("plan", 0),
            data.get("total_done", 0),
            data.get("total_plan", 0),
            created_at,
        ]
        append_row(HEAD_SHEET, row)
        clear_state(chat_id)
        send_message(chat_id, f"Отчёт хеда сохранён.\nСтатус: {NO_REVIEW_STATUS}", reply_keyboard=main_menu(get_role(chat_id)))


def restart_report(chat_id: int, user: Dict[str, Any]) -> None:
    state = user_states.get(chat_id)
    if not state:
        return
    mode = state.get("mode")
    if mode == "manager_report":
        start_manager_report(chat_id, user)
    elif mode == "teamlead_report":
        start_leader_report(chat_id, user, ROLE_TEAMLEAD)
    elif mode == "head_report":
        start_leader_report(chat_id, user, ROLE_HEAD)
    else:
        clear_state(chat_id)


def show_menu(chat_id: int) -> None:
    role = get_role(chat_id)
    text = "Главное меню."
    if role is None:
        text = "Роль не определена. Добавьте chat_id в .env или в список разрешённых."
    send_message(chat_id, text, reply_keyboard=main_menu(role))


def latest_row_for_reporter(sheet_name: str, reporter_chat_id: int) -> Optional[Tuple[int, List[Any]]]:
    rows = get_sheet_values(sheet_name)
    today = today_str()
    reporter_chat_id = str(reporter_chat_id)
    latest = None
    for idx, row in enumerate(rows[1:], start=2):
        if len(row) < 4:
            continue
        if str(row[0]).strip() != today:
            continue
        target_col = 2 if sheet_name == MANAGER_SHEET else 3
        if normalize_chat_id(row[target_col]) != reporter_chat_id:
            continue
        latest = (idx, row)
    return latest


def show_my_status(chat_id: int) -> None:
    role = get_role(chat_id)
    if role == ROLE_MANAGER:
        latest = latest_row_for_reporter(MANAGER_SHEET, chat_id)
        if not latest:
            send_message(chat_id, "Сегодня отчёт менеджера ещё не сдан.", reply_keyboard=main_menu(role))
            return
        row_number, row = latest
        comment = row[22] if len(row) > 22 else ""
        review_status = row[19] if len(row) > 19 else ""
        submission_type = row[23] if len(row) > 23 else PRIMARY_SUBMISSION
        text = (
            f"Статус отчёта менеджера за сегодня:\n"
            f"Статус: {review_status}\n"
            f"Тип отправки: {submission_type or PRIMARY_SUBMISSION}\n"
            f"Комментарий: {comment or '—'}"
        )
        inline_keyboard = None
        if review_status == REJECTED_STATUS:
            inline_keyboard = [[("🔁 Исправить и пересдать", f"resubmit:manager:{row_number}")]]
        send_message(chat_id, text, inline_keyboard=inline_keyboard)
        return

    if role == ROLE_TEAMLEAD:
        latest = latest_row_for_reporter(TEAMLEAD_SHEET, chat_id)
        if not latest:
            send_message(chat_id, "Сегодня отчёт тимлида ещё не сдан.", reply_keyboard=main_menu(role))
            return
        row_number, row = latest
        comment = row[24] if len(row) > 24 else ""
        review_status = row[21] if len(row) > 21 else ""
        submission_type = row[25] if len(row) > 25 else PRIMARY_SUBMISSION
        text = (
            f"Статус отчёта тимлида за сегодня:\n"
            f"Статус: {review_status}\n"
            f"Тип отправки: {submission_type or PRIMARY_SUBMISSION}\n"
            f"Комментарий: {comment or '—'}"
        )
        inline_keyboard = None
        if review_status == REJECTED_STATUS:
            inline_keyboard = [[("🔁 Исправить и пересдать", f"resubmit:teamlead:{row_number}")]]
        send_message(chat_id, text, inline_keyboard=inline_keyboard)
        return

    if role in {ROLE_HEAD, ROLE_SUPERVISOR, ROLE_ADMIN}:
        latest = latest_row_for_reporter(HEAD_SHEET, chat_id)
        if not latest:
            send_message(chat_id, "Сегодня отчёт хеда ещё не сдан.", reply_keyboard=main_menu(role))
            return
        send_message(chat_id, "Отчёт хеда за сегодня сохранён.", reply_keyboard=main_menu(role))
        return

    send_message(chat_id, "Роль не определена.", reply_keyboard=main_menu(role))


def metrics_sum_from_latest(rows: List[List[Any]], start_pairs: List[Tuple[int, int]]) -> Dict[str, int]:
    totals: Dict[str, int] = {}
    for key, (done_idx, plan_idx) in {
        "numbers": start_pairs[0],
        "positive": start_pairs[1],
        "active": start_pairs[2],
        "throw_in": start_pairs[3],
        "proposal": start_pairs[4],
        "agreements": start_pairs[5],
    }.items():
        totals[f"{key}_done"] = sum(int((r[done_idx] if len(r) > done_idx else 0) or 0) for r in rows)
        totals[f"{key}_plan"] = sum(int((r[plan_idx] if len(r) > plan_idx else 0) or 0) for r in rows)
    return totals


def get_latest_rows_for_chat_ids(sheet_name: str, chat_ids: List[str], reporter_col_idx: int) -> Dict[str, List[Any]]:
    rows = get_sheet_values(sheet_name)
    today = today_str()
    result: Dict[str, List[Any]] = {}
    chat_set = {str(x) for x in chat_ids if str(x)}
    for row in rows[1:]:
        if not row:
            continue
        if str(row[0]).strip() != today:
            continue
        if len(row) <= reporter_col_idx:
            continue
        reporter_id = normalize_chat_id(row[reporter_col_idx])
        if reporter_id not in chat_set:
            continue
        result[reporter_id] = row
    return result


def show_team_summary(chat_id: int) -> None:
    role = get_role(chat_id)

    if role == ROLE_TEAMLEAD:
        manager_items = [item for item in get_manager_mappings() if item["teamlead_chat_id"] == str(chat_id)]
        manager_chat_ids = [item["chat_id"] for item in manager_items]
        latest_rows = get_latest_rows_for_chat_ids(MANAGER_SHEET, manager_chat_ids, 2)
        submitted = len(latest_rows)
        total = len(manager_items)
        without_report = [item["name"] or item["chat_id"] for item in manager_items if item["chat_id"] not in latest_rows]
        latest_values = list(latest_rows.values())
        status_counts = {
            PENDING_STATUS: sum(1 for row in latest_values if len(row) > 19 and row[19] == PENDING_STATUS),
            APPROVED_STATUS: sum(1 for row in latest_values if len(row) > 19 and row[19] == APPROVED_STATUS),
            REJECTED_STATUS: sum(1 for row in latest_values if len(row) > 19 and row[19] == REJECTED_STATUS),
        }
        totals = metrics_sum_from_latest(latest_values, [(5, 6), (7, 8), (9, 10), (11, 12), (13, 14), (15, 16)])
        text = [
            "👥 Моя команда",
            f"Менеджеров: {total}",
            f"Сдали сегодня: {submitted}",
            f"Без отчёта: {total - submitted}",
            f"Подтверждено: {status_counts[APPROVED_STATUS]}",
            f"На проверке: {status_counts[PENDING_STATUS]}",
            f"Отклонено: {status_counts[REJECTED_STATUS]}",
            "",
            f"Номеров: {totals['numbers_done']}/{totals['numbers_plan']}",
            f"Плюсовых: {totals['positive_done']}/{totals['positive_plan']}",
            f"Актив: {totals['active_done']}/{totals['active_plan']}",
            f"Вброс: {totals['throw_in_done']}/{totals['throw_in_plan']}",
            f"Предлог: {totals['proposal_done']}/{totals['proposal_plan']}",
            f"Согласий: {totals['agreements_done']}/{totals['agreements_plan']}",
        ]
        if without_report:
            text += ["", "Без отчёта:", *[f"• {name}" for name in without_report]]
        send_message(chat_id, "\n".join(text), reply_keyboard=main_menu(role))
        return

    if role in {ROLE_HEAD, ROLE_SUPERVISOR, ROLE_ADMIN}:
        teamlead_items = [item for item in get_teamlead_mappings() if item["head_chat_id"] == str(chat_id)]
        tl_chat_ids = [item["chat_id"] for item in teamlead_items]
        manager_items = [item for item in get_manager_mappings() if item["teamlead_chat_id"] in tl_chat_ids]
        manager_chat_ids = [item["chat_id"] for item in manager_items]
        latest_manager_rows = get_latest_rows_for_chat_ids(MANAGER_SHEET, manager_chat_ids, 2)
        latest_tl_rows = get_latest_rows_for_chat_ids(TEAMLEAD_SHEET, tl_chat_ids, 3)
        manager_values = list(latest_manager_rows.values())
        totals = metrics_sum_from_latest(manager_values, [(5, 6), (7, 8), (9, 10), (11, 12), (13, 14), (15, 16)])
        lines = [
            "👥 Моя команда",
            f"Тимлидов: {len(teamlead_items)}",
            f"Менеджеров: {len(manager_items)}",
            f"Менеджерских отчётов сегодня: {len(manager_values)}",
            f"Тимлидских отчётов сегодня: {len(latest_tl_rows)}",
            "",
            f"Номеров: {totals['numbers_done']}/{totals['numbers_plan']}",
            f"Плюсовых: {totals['positive_done']}/{totals['positive_plan']}",
            f"Актив: {totals['active_done']}/{totals['active_plan']}",
            f"Вброс: {totals['throw_in_done']}/{totals['throw_in_plan']}",
            f"Предлог: {totals['proposal_done']}/{totals['proposal_plan']}",
            f"Согласий: {totals['agreements_done']}/{totals['agreements_plan']}",
            "",
            "Разбивка по тимлидам:",
        ]
        for item in teamlead_items:
            tl_managers = [m for m in manager_items if m["teamlead_chat_id"] == item["chat_id"]]
            tl_latest = [latest_manager_rows[m["chat_id"]] for m in tl_managers if m["chat_id"] in latest_manager_rows]
            lines.append(f"• {item['name'] or item['chat_id']}: {len(tl_latest)}/{len(tl_managers)} отчётов менеджеров")
        send_message(chat_id, "\n".join(lines), reply_keyboard=main_menu(role))
        return

    send_message(chat_id, "Эта кнопка доступна тимлидам и хедам.", reply_keyboard=main_menu(role))


def show_daily_summary(chat_id: int) -> None:
    today = today_str()
    manager_rows = get_sheet_values(MANAGER_SHEET)[1:]
    teamlead_rows = get_sheet_values(TEAMLEAD_SHEET)[1:]
    head_rows = get_sheet_values(HEAD_SHEET)[1:]

    manager_today = [row for row in manager_rows if row and str(row[0]).strip() == today]
    tl_today = [row for row in teamlead_rows if row and str(row[0]).strip() == today]
    head_today = [row for row in head_rows if row and str(row[0]).strip() == today]

    manager_resubmits = sum(1 for row in manager_today if len(row) > 23 and row[23] == RESUBMISSION)
    tl_resubmits = sum(1 for row in tl_today if len(row) > 25 and row[25] == RESUBMISSION)
    text = (
        f"📈 Сводка за сегодня ({today})\n"
        f"Менеджерских отчётов: {len(manager_today)}\n"
        f"Тимлидских отчётов: {len(tl_today)}\n"
        f"Хедских отчётов: {len(head_today)}\n"
        f"Менеджерских пересдач: {manager_resubmits}\n"
        f"Тимлидских пересдач: {tl_resubmits}\n"
        f"Менеджерских на проверке: {sum(1 for row in manager_today if len(row) > 19 and row[19] == PENDING_STATUS)}\n"
        f"Тимлидских на проверке: {sum(1 for row in tl_today if len(row) > 21 and row[21] == PENDING_STATUS)}"
    )
    send_message(chat_id, text, reply_keyboard=main_menu(get_role(chat_id)))


def start_review(chat_id: int, scope: str) -> None:
    if scope == "manager":
        rows = get_sheet_values(MANAGER_SHEET)
        queue = []
        for idx, row in enumerate(rows[1:], start=2):
            if len(row) < 20:
                continue
            if normalize_chat_id(row[18]) != str(chat_id):
                continue
            if row[19] != PENDING_STATUS:
                continue
            queue.append({
                "sheet": MANAGER_SHEET,
                "row_number": idx,
                "owner_chat_id": normalize_chat_id(row[2]),
                "reporter_name": row[3] if len(row) > 3 else "",
                "row": row,
                "scope": "manager",
            })
    else:
        rows = get_sheet_values(TEAMLEAD_SHEET)
        queue = []
        for idx, row in enumerate(rows[1:], start=2):
            if len(row) < 22:
                continue
            if normalize_chat_id(row[20]) != str(chat_id):
                continue
            if row[21] != PENDING_STATUS:
                continue
            queue.append({
                "sheet": TEAMLEAD_SHEET,
                "row_number": idx,
                "owner_chat_id": normalize_chat_id(row[3]),
                "reporter_name": row[4] if len(row) > 4 else "",
                "row": row,
                "scope": "teamlead",
            })

    if not queue:
        send_message(chat_id, "Нет отчётов на проверке.", reply_keyboard=main_menu(get_role(chat_id)))
        return

    user_states[chat_id] = {
        "mode": "review_queue",
        "queue": queue,
        "index": 0,
    }
    send_current_review(chat_id)


def build_review_text(item: Dict[str, Any]) -> str:
    row = item["row"]
    if item["scope"] == "manager":
        labels = [
            ("Номеров", f"{row[5]}/{row[6]}"),
            ("Плюсовых", f"{row[7]}/{row[8]}"),
            ("Актив", f"{row[9]}/{row[10]}"),
            ("Вброс", f"{row[11]}/{row[12]}"),
            ("Предлог", f"{row[13]}/{row[14]}"),
            ("Согласий", f"{row[15]}/{row[16]}"),
        ]
        body = [f"{label}: {value}" for label, value in labels]
        return "\n".join([
            "Проверка отчёта менеджера",
            f"Менеджер: {item['reporter_name']}",
            f"Дата: {row[0]} {row[1]}",
            *body,
        ])

    labels = [
        ("Команда кол-во", row[6]),
        ("Общий актив", row[7]),
        ("Взято всего номеров", row[8]),
        ("Плюсовые", row[9]),
        ("Средний актив на менеджера", row[10]),
        ("Кол-во вбросов", row[11]),
        ("Кол-во предлог", row[12]),
        ("Кол-во согласий", row[13]),
        ("Лиды", row[14]),
        ("Депы", row[15]),
        ("План", row[16]),
        ("Тотал", f"{row[17]}/{row[18]}"),
    ]
    body = [f"{label}: {value}" for label, value in labels]
    return "\n".join([
        "Проверка отчёта тимлида",
        f"Тимлид: {item['reporter_name']}",
        f"Дата: {row[0]} {row[1]}",
        *body,
    ])


def send_current_review(chat_id: int) -> None:
    state = user_states.get(chat_id)
    if not state or state.get("mode") != "review_queue":
        return
    queue = state["queue"]
    index = state["index"]
    if index >= len(queue):
        clear_state(chat_id)
        send_message(chat_id, "Очередь проверки закончилась.", reply_keyboard=main_menu(get_role(chat_id)))
        return

    item = queue[index]
    send_message(
        chat_id,
        build_review_text(item),
        inline_keyboard=[
            [("✅ Подтвердить", "review_approve"), ("❌ Отклонить", "review_reject")],
            [("⏭ Следующий", "review_next"), ("🏠 Меню", "review_exit")],
        ],
    )


def apply_review_result(chat_id: int, approved: bool, comment: str = "") -> None:
    state = user_states.get(chat_id)
    if not state or state.get("mode") not in {"review_queue", "awaiting_reject_comment"}:
        return

    queue_state = state if state.get("mode") == "review_queue" else state["review_queue_state"]
    queue = queue_state["queue"]
    index = queue_state["index"]
    if index >= len(queue):
        return

    item = queue[index]
    reviewed_at = format_dt()[2]
    reviewer_name = f"{get_role(chat_id) or 'reviewer'}:{chat_id}"

    if item["sheet"] == MANAGER_SHEET:
        updates = {
            20: APPROVED_STATUS if approved else REJECTED_STATUS,
            21: reviewer_name,
            22: reviewed_at,
            23: comment,
        }
    else:
        updates = {
            22: APPROVED_STATUS if approved else REJECTED_STATUS,
            23: reviewer_name,
            24: reviewed_at,
            25: comment,
        }

    update_row_fields(item["sheet"], item["row_number"], updates)

    owner_chat_id = item["owner_chat_id"]
    if owner_chat_id:
        try:
            text = f"Ваш отчёт {'подтверждён' if approved else 'отклонён'}."
            if comment:
                text += f"\nПричина: {comment}"
            inline_keyboard = None
            if not approved:
                inline_keyboard = [[("🔁 Исправить и пересдать", f"resubmit:{item['scope']}:{item['row_number']}")]]
            send_message(int(owner_chat_id), text, inline_keyboard=inline_keyboard)
        except Exception:
            logger.exception("Не удалось уведомить автора отчёта")

    queue_state["index"] += 1
    if state.get("mode") == "awaiting_reject_comment":
        user_states[chat_id] = queue_state
    send_current_review(chat_id)


def request_rejection_reason(chat_id: int) -> None:
    send_message(
        chat_id,
        "Выберите причину отклонения или напишите свою:",
        inline_keyboard=[
            [("Неполный отчёт", "reject_reason:incomplete"), ("Ошибка в цифрах", "reject_reason:numbers")],
            [("Нет тотала", "reject_reason:total"), ("Не тот формат", "reject_reason:format")],
            [("✍️ Свой комментарий", "reject_reason:custom")],
        ],
    )


def handle_reject_reason(chat_id: int, reason_key: str) -> None:
    if reason_key == "custom":
        state = user_states.get(chat_id)
        if not state or state.get("mode") != "review_queue":
            return
        user_states[chat_id] = {
            "mode": "awaiting_reject_comment",
            "review_queue_state": state,
        }
        send_message(chat_id, "Напишите причину отклонения одним сообщением.", reply_keyboard=main_menu(get_role(chat_id)))
        return

    reason = PRESET_REJECTION_REASONS.get(reason_key)
    if not reason:
        return
    apply_review_result(chat_id, approved=False, comment=reason)


def handle_callback(chat_id: int, callback_id: str, data: str, user: Dict[str, Any]) -> None:
    answer_callback(callback_id)

    if data == "save_report":
        save_current_report(chat_id)
        return
    if data == "restart_report":
        restart_report(chat_id, user)
        return
    if data == "cancel_report":
        clear_state(chat_id)
        send_message(chat_id, "Действие отменено.", reply_keyboard=main_menu(get_role(chat_id)))
        return
    if data.startswith("resubmit:"):
        parts = data.split(":")
        if len(parts) != 3:
            return
        scope = parts[1]
        previous_row = parts[2]
        role = get_role(chat_id)
        if scope == "manager" and role in {ROLE_MANAGER, ROLE_ADMIN}:
            start_manager_report(chat_id, user, submission_type=RESUBMISSION, previous_rejected_row=previous_row)
        elif scope == "teamlead" and role in {ROLE_TEAMLEAD, ROLE_ADMIN}:
            start_leader_report(chat_id, user, ROLE_TEAMLEAD, submission_type=RESUBMISSION, previous_rejected_row=previous_row)
        else:
            send_message(chat_id, "Эта кнопка недоступна для вашей роли.", reply_keyboard=main_menu(role))
        return
    if data == "review_approve":
        apply_review_result(chat_id, approved=True)
        return
    if data == "review_reject":
        request_rejection_reason(chat_id)
        return
    if data == "review_next":
        state = user_states.get(chat_id)
        if state and state.get("mode") == "review_queue":
            state["index"] += 1
        send_current_review(chat_id)
        return
    if data == "review_exit":
        clear_state(chat_id)
        send_message(chat_id, "Проверка завершена.", reply_keyboard=main_menu(get_role(chat_id)))
        return
    if data.startswith("reject_reason:"):
        handle_reject_reason(chat_id, data.split(":", 1)[1])
        return


def handle_report_input(chat_id: int, text: str) -> bool:
    state = user_states.get(chat_id)
    if not state:
        return False

    mode = state.get("mode")
    if mode == "awaiting_reject_comment":
        comment = text.strip()
        if not comment:
            send_message(chat_id, "Причина не должна быть пустой.")
            return True
        apply_review_result(chat_id, approved=False, comment=comment)
        return True

    if mode == "manager_report":
        step = state["step"]
        metric = MANAGER_METRICS[step]
        try:
            done_val, plan_val = parse_done_plan(text)
        except Exception:
            send_message(chat_id, f"Нужен формат сделано/план для поля «{metric['label']}».")
            return True
        state["data"][f"{metric['key']}_done"] = done_val
        state["data"][f"{metric['key']}_plan"] = plan_val
        state["step"] += 1
        ask_next_question(chat_id)
        return True

    if mode in {"teamlead_report", "head_report"}:
        step = state["step"]
        field = LEADER_FIELDS[step]
        try:
            if field["type"] == "pair":
                done_val, plan_val = parse_done_plan(text)
                state["data"]["total_done"] = done_val
                state["data"]["total_plan"] = plan_val
                state["data"]["total"] = f"{done_val}/{plan_val}"
            else:
                state["data"][field["key"]] = parse_int_value(text)
        except Exception:
            send_message(chat_id, f"Некорректное значение для поля «{field['label']}».")
            return True
        state["step"] += 1
        ask_next_question(chat_id)
        return True

    return False


def show_my_id(chat_id: int) -> None:
    send_message(chat_id, f"Ваш chat_id: {chat_id}\nРоль: {get_role(chat_id) or 'не определена'}", reply_keyboard=main_menu(get_role(chat_id)))


def handle_text_message(chat_id: int, text: str, user: Dict[str, Any]) -> None:
    text = text.strip()

    if not is_chat_allowed(chat_id):
        send_message(chat_id, "У вас нет доступа к этому боту.")
        return

    low = text.lower()

    if low in {"/start", "/menu", "меню", "🏠 главное меню"}:
        clear_state(chat_id)
        show_menu(chat_id)
        return

    if low in {"/cancel", "❌ отмена"}:
        clear_state(chat_id)
        send_message(chat_id, "Действие отменено.", reply_keyboard=main_menu(get_role(chat_id)))
        return

    if handle_report_input(chat_id, text):
        return

    if low in {"/myid", "🆔 мой id"}:
        show_my_id(chat_id)
        return

    if low in {"/status", "📌 мой статус"}:
        show_my_status(chat_id)
        return

    if low in {"/summary", "📈 сводка сегодня"}:
        show_daily_summary(chat_id)
        return

    if low in {"/report", "📝 отчёт менеджера"}:
        if get_role(chat_id) not in {ROLE_MANAGER, ROLE_ADMIN}:
            send_message(chat_id, "Эта кнопка доступна менеджерам.", reply_keyboard=main_menu(get_role(chat_id)))
            return
        start_manager_report(chat_id, user)
        return

    if low in {"/teamleadreport", "👔 отчёт тимлида"}:
        if get_role(chat_id) not in {ROLE_TEAMLEAD, ROLE_ADMIN}:
            send_message(chat_id, "Эта кнопка доступна тимлидам.", reply_keyboard=main_menu(get_role(chat_id)))
            return
        start_leader_report(chat_id, user, ROLE_TEAMLEAD)
        return

    if low in {"/headreport", "🧠 отчёт хеда"}:
        if get_role(chat_id) not in {ROLE_HEAD, ROLE_SUPERVISOR, ROLE_ADMIN}:
            send_message(chat_id, "Эта кнопка доступна хедам.", reply_keyboard=main_menu(get_role(chat_id)))
            return
        start_leader_report(chat_id, user, ROLE_HEAD)
        return

    if low in {"✅ проверить менеджеров"}:
        if get_role(chat_id) not in {ROLE_TEAMLEAD, ROLE_ADMIN}:
            send_message(chat_id, "Эта кнопка доступна тимлидам.", reply_keyboard=main_menu(get_role(chat_id)))
            return
        start_review(chat_id, "manager")
        return

    if low in {"✅ проверить тимлидов"}:
        if get_role(chat_id) not in {ROLE_HEAD, ROLE_SUPERVISOR, ROLE_ADMIN}:
            send_message(chat_id, "Эта кнопка доступна хедам.", reply_keyboard=main_menu(get_role(chat_id)))
            return
        start_review(chat_id, "teamlead")
        return

    if low in {"👥 моя команда"}:
        show_team_summary(chat_id)
        return

    show_menu(chat_id)


def process_update(update: Dict[str, Any]) -> None:
    if "callback_query" in update:
        callback = update["callback_query"]
        user = callback.get("from", {})
        message = callback.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        if chat_id is None:
            return
        handle_callback(chat_id, callback.get("id", ""), callback.get("data", ""), user)
        return

    message = update.get("message")
    if not message:
        return
    text = message.get("text")
    if not text:
        return
    user = message.get("from", {})
    chat_id = message.get("chat", {}).get("id")
    if chat_id is None:
        return
    handle_text_message(chat_id, text, user)


def main() -> None:
    require_env()
    ensure_sheets_ready()

    logger.info("Бот запущен.")
    offset = None
    while True:
        try:
            updates = get_updates(offset)
            for item in updates.get("result", []):
                offset = item["update_id"] + 1
                process_update(item)
        except KeyboardInterrupt:
            logger.info("Бот остановлен вручную.")
            break
        except Exception as exc:
            logger.exception("Ошибка в основном цикле: %s", exc)
            time.sleep(3)


if __name__ == "__main__":
    main()
