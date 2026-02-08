# Event Management Telegram Bot

This repository contains a Telegram bot for ticket reservations with pay-on-spot flow.

## Setup

1. Create a Telegram bot via BotFather and grab the token.
2. Copy `.env.example` to `.env` and update the values.
3. Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

4. Run the bot:

```bash
python bot.py
```

## Notes

- SQLite is used for storage (`data/bot.db`).
- Admin IDs are controlled via the `ADMIN_IDS` environment variable.
- The bot is organized into modules under `ticketbot/` (config, database, services, app).
