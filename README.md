# Event Management Telegram Bot

Telegram bot for event reservations with mandatory transfer-proof approval flow.

## Setup

1. Create a Telegram bot with BotFather and get token.
2. Copy `.env.example` to `.env` and update values.
3. Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

4. Run:

```bash
python bot.py
```

Optional (for Mini App local server):

```bash
python -m ticketbot.miniapp_server
```

## Railway Deployment (Fastest)

For current architecture (Telegram polling + SQLite), use one Railway service that runs both bot and Mini App.

### Recommended: Single Service + One Volume

1. Create new Railway project from this repo.
2. Add a Volume to the service and mount it at `/data`.
3. Set Start Command:

```bash
bash deploy/railway/start_combined.sh
```

4. Set variables:

- `BOT_TOKEN=...`
- `ADMIN_IDS=7164876915` (or comma-separated admin ids)
- `DATABASE_PATH=/data/bot.db`
- `WEB_APP_URL=https://<your-service>.up.railway.app`

5. Deploy and open:

- `https://<your-service>.up.railway.app/health` should return `{"status":"ok"}`
- In Telegram run `/book` and test booking.

If logs show an `Updater` AttributeError on Python 3.13, pin runtime to Python 3.12:
- This repo includes `.python-version` set to `3.12`.
- If needed, also set Railway variable `NIXPACKS_PYTHON_VERSION=3.12` and redeploy.

Mini App visibility checklist:
- `WEB_APP_URL` must be set.
- URL must be `https://`.
- In BotFather, set Mini App domain to the same domain.
- Restart service after changing vars.

### About Two Services

- `Procfile` and scripts for split mode are included:
  - `deploy/railway/start_web.sh`
  - `deploy/railway/start_bot.sh`
- With SQLite, split services are not recommended because DB storage is per-service volume.
- If you want true split (`web` + `worker`), migrate DB to shared PostgreSQL first.

## Oracle Always Free Deployment (Alternative)

This bot runs as long-polling + SQLite, so use an always-on VM.

### 1. Create VM

- In Oracle Cloud: create an `Always Free` Ubuntu VM.
- Open ingress for SSH (`22`).
- Connect:

```bash
ssh -i <your_private_key> ubuntu@<vm_public_ip>
```

### 2. Bootstrap VM

```bash
sudo apt-get update
sudo apt-get install -y git
git clone <your_repo_url> /opt/eventmanagement
cd /opt/eventmanagement
sudo ./deploy/oracle/bootstrap_vm.sh
```

### 3. Install bot app

```bash
cd /opt/eventmanagement
sudo ./deploy/oracle/install_bot.sh
sudo cp deploy/oracle/.env.example /opt/eventmanagement/.env
sudo chown ubuntu:ubuntu /opt/eventmanagement/.env
sudo chmod 600 /opt/eventmanagement/.env
```

If `/opt/eventmanagement` does not exist yet, use:

```bash
sudo ./deploy/oracle/install_bot.sh <your_repo_url>
```

Edit env:

```bash
nano /opt/eventmanagement/.env
```

Set:

- `BOT_TOKEN=...`
- `ADMIN_IDS=7164876915` (or comma-separated admin IDs)
- `DATABASE_PATH=data/bot.db`
- `WEB_APP_URL=https://<public-https-url-for-miniapp>` (optional but required for `/book`)

### 4. Install and start systemd service

```bash
cd /opt/eventmanagement
sudo ./deploy/oracle/install_service.sh
sudo systemctl start eventbot.service
sudo systemctl status eventbot.service
```

### 5. Logs and troubleshooting

```bash
sudo journalctl -u eventbot.service -f
sudo journalctl -u eventbot.service --since "10 minutes ago"
```

### 6. Update after code changes

```bash
cd /opt/eventmanagement
sudo ./deploy/oracle/update_bot.sh main
```

### 7. Enable daily DB backup

```bash
cd /opt/eventmanagement
sudo crontab -e
```

Add:

```cron
30 3 * * * /opt/eventmanagement/deploy/oracle/backup_db.sh >> /var/log/eventbot-backup.log 2>&1
```

Backups are saved to `/opt/eventmanagement/backups` and old backups (older than 14 days) are deleted automatically.

## Notes

- SQLite storage is auto-created at `data/bot.db`.
- DB schema migrations run automatically on startup.
- Admin users are controlled with `ADMIN_IDS` env var (numeric Telegram IDs).
- Mini App button uses `WEB_APP_URL` env var (must be a public `https://` URL).
- Guest Mini App route: `/`
- Admin Mini App route: `/admin`

## User Commands

- `/start` - create profile.
- `/events` - browse events.
- `/book` - open Mini App booking UI.
- `/mytickets` - show all reservations and statuses.
- `/cancel <reservation_code>` - cancel your reservation.

Users can use menu buttons after `/start`:
- `Browse Events`
- `Open Booking App`
- `My Tickets`

Users can also cancel via inline `Cancel` button in `/mytickets`.

## Admin Commands

- `/admin` - create event, view event list, blocked users.
- `/adminapp` - open Admin Mini App dashboard.
- `/admin_stats [sort] [search]` - analytics with counts/revenue and optional search.
- `/export <event_id>` - export reservations CSV.
- `/admin_find [sort] <query>` - search reservations by code, event, buyer, phone, tg id.
- `/admin_guests [sort] [search]` - list guests across all reservations.
- `/admin_guest_add <reservation_code> <boy|girl> <Name Surname>` - add guest to reservation.
- `/admin_guest_remove <attendee_id>` - remove guest from reservation.
- `/admin_guest_rename <attendee_id> <Name Surname>` - rename guest.
- `/admin_event_show <event_id>` - show event details (prices/qty/text).
- `/admin_event_set <event_id> <field> <value>` - edit event fields.

Admin can do most actions via buttons:
- `/admin` -> `Guests` for guest list/search/sort/open/add/remove/rename.
- `/admin` -> `Edit events` for button-driven event field updates.
- `/admin` -> `Open Admin App` for full web dashboard.

Sort options:
- `admin_stats`: `date`, `title`, `approved`, `pending`, `sold`, `revenue`
- `admin_find`: `newest`, `amount`, `status`, `event_date`
- `admin_guests`: `newest`, `name`, `event`, `reservation`, `status`

## Booking Workflow

- Admin creates event with mandatory photo and custom caption.
- Admin sets 3 tiers with gender-based prices and quantities:
  - Early Bird (boys/girls + qty)
  - Regular Tier-1 (boys/girls + qty)
  - Regular Tier-2 (boys/girls + qty)
- User sees only current active tier price (no visible ticket counts).
- User can book in two ways:
  - Mini App (`/book` or button in `/events`) for modern form UI.
  - Classic chat flow.
- User enters boys/girls counts first; total attendees is automatic.
- User submits attendee full names in `Name Surname` format.
- User uploads one transfer proof file (image or PDF).
- User accepts rules.
- Reservation becomes `pending_payment_review` and stock is held immediately.
- All admins get Telegram notification with buttons:
  - Approve
  - Reject with template reason
  - Reject with custom message
  - Edit event prices
- On rejection/cancellation, held stock is released.

## Mini App Local Test

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Start bot in terminal #1:

```bash
python bot.py
```

3. Start Mini App server in terminal #2:

```bash
python -m ticketbot.miniapp_server
```

4. Expose Mini App with public HTTPS tunnel (example using ngrok):

```bash
ngrok http 8080
```

5. Put tunnel URL into `.env`:

```env
WEB_APP_URL=https://<your-ngrok-domain>
```

6. In BotFather for your bot:
- Set Web App domain to your tunnel domain.
- Optionally set chat menu button URL to `WEB_APP_URL`.

7. Restart bot and run `/book` in Telegram.

Mini App sends booking draft to bot via `web_app_data`. Then user continues payment proof + rules in chat.

## Admin Mini App Local Test

1. Ensure your Telegram user id is in `ADMIN_IDS`.
2. Run bot and Mini App server as above.
3. Use the same tunnel/public URL in `WEB_APP_URL`.
4. In Telegram, run `/admin` and tap `Open Admin App` (or run `/adminapp`).
5. Admin Mini App route is `https://<your-domain>/admin`.
