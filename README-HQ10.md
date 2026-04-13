# Office Report Bot on HOSTiQ HQ10

This additive setup is for shared hosting where long polling is unreliable.

## Files added for HQ10
- `webhook_hq10.py` — Flask webhook entrypoint
- `passenger_wsgi.py` — Passenger/cPanel entrypoint
- `requirements-hq10.txt` — dependencies for Python App
- `.env.hq10.example` — environment template

## Required project files
To make the bot fully runnable, the repository root still needs the real project files from `office-report-bot-v3-package.zip`, especially:
- `bot.py`
- `office_reports_template.xlsx`

If they are not in the repository root yet, unpack the archive and place them there.

## cPanel / Python App settings
- Application root: project folder
- Startup file: `passenger_wsgi.py`
- Entry point: `application`
- Python requirements: `pip install -r requirements-hq10.txt`

## Environment
Copy `.env.hq10.example` to `.env` and fill the values.

## Webhook
After the app is reachable via HTTPS, run:

```bash
https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://reports.YOURDOMAIN/webhook&secret_token=YOUR_SECRET
```

## Important
The webhook entrypoint tries to import `BOT_MODULE` (default: `bot`) and call `BOT_PROCESS_UPDATE_FN` (default: `process_update`).
If your real bot uses different function names, set them in `.env`.
