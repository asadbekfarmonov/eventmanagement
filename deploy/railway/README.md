# Railway Deployment Guide

## Files

- `start_combined.sh`: Runs Mini App web server + Telegram bot worker in one Railway service.
- `start_web.sh`: Runs only Mini App web server.
- `start_bot.sh`: Runs only Telegram bot worker.
- `.env.example`: Suggested env vars for Railway.
- `../../Procfile`: Defines `web` and `worker` process types.

## Recommended Setup (SQLite)

Use one service with one volume.

1. Create service from repo.
2. Add volume mount path `/data`.
3. Set start command:

```bash
bash deploy/railway/start_combined.sh
```

4. Set env vars:

```env
BOT_TOKEN=...
ADMIN_IDS=7164876915
DATABASE_PATH=/data/bot.db
WEB_APP_URL=https://<service>.up.railway.app
```

5. Deploy and test:

- `GET /health` returns `{"status":"ok"}`
- Telegram `/book` opens Mini App.

## Split Services Setup (Requires shared DB, e.g. PostgreSQL)

SQLite volume is per service, so split mode with SQLite is not safe.

- Web service start command: `bash deploy/railway/start_web.sh`
- Worker service start command: `bash deploy/railway/start_bot.sh`

Use split mode only after moving DB to a shared database backend.
