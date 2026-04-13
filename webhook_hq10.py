import asyncio
import importlib
import inspect
import json
import os
from typing import Any, Callable

from flask import Flask, abort, jsonify, request

app = Flask(__name__)

SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
BOT_MODULE = os.getenv("BOT_MODULE", "bot").strip() or "bot"
PROCESS_UPDATE_FN = os.getenv("BOT_PROCESS_UPDATE_FN", "process_update").strip()
INIT_FN = os.getenv("BOT_INIT_FN", "setup_bot").strip()

_module = None
_init_done = False


def _load_module():
    global _module
    if _module is None:
        _module = importlib.import_module(BOT_MODULE)
    return _module


def _run_callable(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    if inspect.iscoroutinefunction(fn):
        return asyncio.run(fn(*args, **kwargs))
    result = fn(*args, **kwargs)
    if inspect.isawaitable(result):
        return asyncio.run(result)
    return result


def _ensure_init(mod: Any) -> None:
    global _init_done
    if _init_done:
        return
    init_fn = getattr(mod, INIT_FN, None)
    if callable(init_fn):
        _run_callable(init_fn)
    _init_done = True


def _resolve_update_handler(mod: Any) -> Callable[[dict], Any]:
    handler = getattr(mod, PROCESS_UPDATE_FN, None)
    if callable(handler):
        return handler

    for candidate in ("handle_update", "dispatch_update", "on_update"):
        handler = getattr(mod, candidate, None)
        if callable(handler):
            return handler

    bot_obj = getattr(mod, "bot", None)
    if bot_obj is not None and hasattr(bot_obj, "process_new_updates"):
        try:
            from telebot.types import Update  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "Found bot.process_new_updates but telebot is unavailable. "
                "Install pyTelegramBotAPI or set BOT_PROCESS_UPDATE_FN."
            ) from exc

        def _telebot_handler(update: dict) -> Any:
            payload = json.dumps(update, ensure_ascii=False)
            return bot_obj.process_new_updates([Update.de_json(payload)])

        return _telebot_handler

    raise RuntimeError(
        "Could not resolve update handler. Set BOT_MODULE and BOT_PROCESS_UPDATE_FN in .env."
    )


@app.get("/")
def index():
    return jsonify(
        {
            "ok": True,
            "service": "office-report-bot-hq10-webhook",
            "bot_module": BOT_MODULE,
            "process_fn": PROCESS_UPDATE_FN,
            "init_fn": INIT_FN,
        }
    )


@app.post("/webhook")
def webhook():
    if SECRET:
        header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if header_secret != SECRET:
            abort(403)

    update = request.get_json(silent=True) or {}
    mod = _load_module()
    _ensure_init(mod)
    handler = _resolve_update_handler(mod)
    _run_callable(handler, update)
    return "ok", 200


application = app
