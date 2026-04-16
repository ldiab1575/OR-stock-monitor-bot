# OR Stock Monitor Bot

Daily stock monitoring bot for OR LLP clients. Checks stock prices and market caps every weekday at 10:00 AM ET and sends an email alert to `louisdiab5@gmail.com`.

## What it monitors

- **Price threshold**: Clients trading below $1.00, with consecutive trading day count
- **Market cap threshold**: Clients with market cap below $5,000,000

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/YOUR_USER/OR-stock-monitor-bot.git
cd OR-stock-monitor-bot
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in your SMTP credentials:

```bash
cp .env.example .env
```

For Gmail, you need an [App Password](https://support.google.com/accounts/answer/185833):
- `SMTP_USER` — your Gmail address
- `SMTP_PASSWORD` — your Gmail App Password (not your regular password)
- `SMTP_HOST` — `smtp.gmail.com`
- `SMTP_PORT` — `587`

### 3. Run locally

```bash
python monitor.py
```

### 4. Deploy to Railway

1. Push to GitHub
2. Connect the repo in [Railway](https://railway.app)
3. Add environment variables (`SMTP_USER`, `SMTP_PASSWORD`, `SMTP_HOST`, `SMTP_PORT`) in the Railway dashboard
4. Railway will use `railway.toml` for cron scheduling (weekdays at 10 AM ET)

## Files

| File | Description |
|---|---|
| `monitor.py` | Main script — fetches data, updates tracking, sends email |
| `clients.json` | Client name → ticker mapping (50 clients) |
| `tracking.json` | Auto-created; tracks consecutive days under $1 per ticker |
| `requirements.txt` | Python dependencies |
| `railway.toml` | Railway cron configuration |
| `Procfile` | Backup process definition |
| `.env.example` | Template for required environment variables |

## Editing clients

To add or remove clients, edit `clients.json`. The format is:

```json
{
  "Company Name": "TICKER"
}
```
