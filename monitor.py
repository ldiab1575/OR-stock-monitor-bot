#!/usr/bin/env python3
"""
OR Stock Monitor Bot
Monitors client stock prices and market caps daily, sends email alerts.
"""

import json
import logging
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yfinance as yf

# --- Configuration ---
SCRIPT_DIR = Path(__file__).parent
CLIENTS_FILE = SCRIPT_DIR / "clients.json"
TRACKING_FILE = SCRIPT_DIR / "tracking.json"
LOG_FILE = SCRIPT_DIR / "monitor.log"

RECIPIENTS = ["louisdiab5@gmail.com"]
PRICE_THRESHOLD = 1.00
MARKET_CAP_THRESHOLD = 5_000_000

ET = ZoneInfo("America/New_York")

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def is_weekday_10am_et() -> bool:
    """Check if current time is a weekday around 10 AM ET."""
    now = datetime.now(ET)
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        log.info(f"Skipping: today is {now.strftime('%A')} (weekend)")
        return False
    return True


def load_json(path: Path, default=None):
    if default is None:
        default = {}
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return default


def save_json(path: Path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def fetch_stock_data(tickers: list[str]) -> dict:
    """Fetch current price and market cap for a list of tickers."""
    results = {}
    for ticker_symbol in tickers:
        try:
            stock = yf.Ticker(ticker_symbol)
            info = stock.info
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            market_cap = info.get("marketCap")

            # Fallback: try fast_info
            if price is None:
                try:
                    price = stock.fast_info.get("lastPrice")
                except Exception:
                    pass
            if market_cap is None:
                try:
                    market_cap = stock.fast_info.get("marketCap")
                except Exception:
                    pass

            results[ticker_symbol] = {
                "price": price,
                "market_cap": market_cap,
            }
            log.info(f"  {ticker_symbol}: price=${price}, mcap={market_cap}")
        except Exception as e:
            log.warning(f"  {ticker_symbol}: fetch failed — {e}")
            results[ticker_symbol] = {"price": None, "market_cap": None}
    return results


def update_tracking(
    tracking: dict, clients: dict, stock_data: dict
) -> dict:
    """Update consecutive-days-under-$1 tracking. Returns updated tracking dict."""
    for client_name, ticker in clients.items():
        data = stock_data.get(ticker, {})
        price = data.get("price")
        if price is not None and price < PRICE_THRESHOLD:
            tracking[ticker] = tracking.get(ticker, 0) + 1
        else:
            tracking[ticker] = 0
    return tracking


def format_market_cap(value: float) -> str:
    if value is None:
        return "N/A"
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:,.0f}"


def build_email_html(
    clients: dict,
    stock_data: dict,
    tracking: dict,
) -> tuple[str, bool]:
    """Build the HTML email body. Returns (html, has_flags)."""
    under_dollar = []
    low_mcap = []

    for client_name, ticker in sorted(clients.items()):
        data = stock_data.get(ticker, {})
        price = data.get("price")
        market_cap = data.get("market_cap")

        if price is not None and price < PRICE_THRESHOLD:
            days = tracking.get(ticker, 1)
            under_dollar.append((client_name, ticker, price, days))

        if market_cap is not None and market_cap < MARKET_CAP_THRESHOLD:
            low_mcap.append((client_name, ticker, market_cap))

    has_flags = bool(under_dollar or low_mcap)
    today = datetime.now(ET).strftime("%B %d, %Y")

    html_parts = [
        f"""
<!DOCTYPE html>
<html>
<head>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #333; margin: 0; padding: 0; }}
  .container {{ max-width: 700px; margin: 0 auto; padding: 20px; }}
  h1 {{ color: #1a1a2e; font-size: 22px; border-bottom: 2px solid #e94560; padding-bottom: 10px; }}
  h2 {{ color: #1a1a2e; font-size: 18px; margin-top: 30px; }}
  .section {{ background: #f8f9fa; border-radius: 8px; padding: 16px; margin: 12px 0; }}
  .alert {{ background: #fff3f3; border-left: 4px solid #e94560; }}
  .warning {{ background: #fff8e1; border-left: 4px solid #f9a825; }}
  .ok {{ background: #e8f5e9; border-left: 4px solid #4caf50; }}
  table {{ width: 100%; border-collapse: collapse; margin: 8px 0; }}
  th {{ text-align: left; padding: 8px 12px; background: #e9ecef; font-size: 13px; text-transform: uppercase; color: #666; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #eee; font-size: 14px; }}
  .price {{ font-weight: bold; color: #e94560; }}
  .days {{ color: #888; font-size: 13px; }}
  .mcap {{ font-weight: bold; color: #f9a825; }}
  .footer {{ margin-top: 30px; font-size: 12px; color: #999; border-top: 1px solid #eee; padding-top: 10px; }}
</style>
</head>
<body>
<div class="container">
<h1>OR Stock Monitor — {today}</h1>
"""
    ]

    if not has_flags:
        html_parts.append(
            '<div class="section ok"><strong>All clients in compliance.</strong>'
            " No clients are trading below $1.00 and no clients have a market cap below $5M.</div>"
        )
    else:
        # Section 1: Under $1
        if under_dollar:
            html_parts.append(
                '<h2>&#9888; Clients Trading Below $1.00</h2>'
                '<div class="section alert"><table>'
                "<tr><th>Client</th><th>Ticker</th><th>Price</th><th>Consecutive Days</th></tr>"
            )
            for name, ticker, price, days in under_dollar:
                html_parts.append(
                    f'<tr><td>{name}</td><td>{ticker}</td>'
                    f'<td class="price">${price:.4f}</td>'
                    f'<td class="days">{days} day{"s" if days != 1 else ""}</td></tr>'
                )
            html_parts.append("</table></div>")
        else:
            html_parts.append(
                '<div class="section ok"><strong>No clients trading below $1.00.</strong></div>'
            )

        # Section 2: Low market cap
        if low_mcap:
            html_parts.append(
                '<h2>&#9888; Clients with Market Cap Below $5M</h2>'
                '<div class="section warning"><table>'
                "<tr><th>Client</th><th>Ticker</th><th>Market Cap</th></tr>"
            )
            for name, ticker, mcap in low_mcap:
                html_parts.append(
                    f'<tr><td>{name}</td><td>{ticker}</td>'
                    f'<td class="mcap">{format_market_cap(mcap)}</td></tr>'
                )
            html_parts.append("</table></div>")
        else:
            html_parts.append(
                '<div class="section ok"><strong>No clients with market cap below $5M.</strong></div>'
            )

    html_parts.append(
        '<div class="footer">This is an automated report from OR Stock Monitor Bot. '
        "Data sourced from Yahoo Finance. Prices may be delayed.</div>"
        "</div></body></html>"
    )

    return "".join(html_parts), has_flags


def send_email(subject: str, html_body: str):
    """Send email via Resend HTTP API (works on Railway where SMTP ports are blocked)."""
    api_key = os.environ.get("RESEND_API_KEY") or os.environ.get("SMTP_PASSWORD")
    sender = os.environ.get("RESEND_FROM") or os.environ.get("SMTP_FROM", "onboarding@resend.dev")

    if not api_key:
        log.error("RESEND_API_KEY (or SMTP_PASSWORD) environment variable is required")
        sys.exit(1)

    payload = {
        "from": sender,
        "to": RECIPIENTS,
        "subject": subject,
        "html": html_body,
    }
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "OR-Stock-Monitor/1.0",
        },
        method="POST",
    )

    log.info(f"Sending email via Resend API to {RECIPIENTS}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            log.info(f"Email sent successfully: {body}")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        log.error(f"Resend API error {e.code}: {err_body}")
        sys.exit(1)
    except urllib.error.URLError as e:
        log.error(f"Network error calling Resend API: {e}")
        sys.exit(1)


def main():
    log.info("=" * 60)
    log.info("OR Stock Monitor — run starting")

    # Timezone / weekday gate
    if not is_weekday_10am_et():
        log.info("Not a weekday — exiting")
        return

    # Load clients and tracking state
    clients = load_json(CLIENTS_FILE)
    if not clients:
        log.error("No clients found in clients.json")
        sys.exit(1)
    log.info(f"Loaded {len(clients)} clients")

    tracking = load_json(TRACKING_FILE)

    # Fetch data
    tickers = list(clients.values())
    log.info(f"Fetching data for {len(tickers)} tickers...")
    stock_data = fetch_stock_data(tickers)

    # Update tracking
    tracking = update_tracking(tracking, clients, stock_data)
    save_json(TRACKING_FILE, tracking)
    log.info("Tracking state updated")

    # Build and send email
    today = datetime.now(ET).strftime("%Y-%m-%d")
    html_body, has_flags = build_email_html(clients, stock_data, tracking)

    if has_flags:
        subject = f"⚠ OR Stock Alert — {today}"
    else:
        subject = f"✅ OR Stock Monitor — All Clear — {today}"

    send_email(subject, html_body)
    log.info("Run complete")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
