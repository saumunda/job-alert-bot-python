import os
import time
import json
import random
import threading
import asyncio
import requests
from flask import Flask
from playwright.async_api import async_playwright

# === CONFIGURATION ===
GRAPHQL_URL = "https://qy64m4juabaffl7tjakii4gdoa.appsync-api.eu-west-1.amazonaws.com/graphql"
JOB_PAGE_URL = "https://www.jobsatamazon.co.uk/app#/jobSearch?query=Warehouse%20Operative&locale=en-GB"

# === TELEGRAM BOT SETTINGS (loaded securely from Render environment variables) ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Multiple chat IDs can be separated by commas in env var (e.g. "12345,-1001234567890")
CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS", "")
CHAT_IDS = [chat.strip() for chat in CHAT_IDS.split(",") if chat.strip()]


# === PROXY & USER-AGENT ROTATION ===
PROXIES = [
    # add your own reliable proxies
    "http://185.199.229.156:7492",
    "http://103.155.54.26:83",
    "http://91.92.155.207:3128",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15 Edg/129.0.0.0",
]

seen_jobs = set()
app = Flask(__name__)

# === TELEGRAM MESSAGE ===
def send_telegram_message(message: str):
    for chat_id in CHAT_IDS:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
            requests.post(url, data=payload, timeout=10)
        except Exception as e:
            print(f"⚠️ Telegram send error to {chat_id}: {e}")

# === FETCH SESSION TOKEN (Playwright) ===
async def get_auth_token():
    try:
        proxy = random.choice(PROXIES)
        agent = random.choice(USER_AGENTS)
        print(f"🌐 Using proxy: {proxy}")
        print(f"🧭 Using User-Agent: {agent}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                proxy={"server": proxy}
            )
            context = await browser.new_context(
                user_agent=agent,
                extra_http_headers={
                    "Accept": "text/html",
                    "Referer": "https://www.jobsatamazon.co.uk/"
                }
            )

            page = await context.new_page()
            await page.goto(JOB_PAGE_URL, wait_until="load")
            cookies = await context.cookies()
            await browser.close()

            for cookie in cookies:
                if "session" in cookie["name"].lower():
                    print(f"✅ Session cookie found: {cookie['name']}")
                    send_telegram_message("✅ Session cookie fetched successfully.")
                    return f"Bearer {cookie['value']}"

    except Exception as e:
        print(f"❌ Playwright token fetch failed: {e}")
    return None

# === FETCH JOB DATA ===
def fetch_jobs(auth_token: str):
    payload = {
        "operationName": "searchJobCardsByLocation",
        "variables": {
            "searchJobRequest": {
                "locale": "en-GB",
                "country": "United Kingdom",
                "keyWords": "Warehouse Operative",
                "equalFilters": [],
                "containFilters": [{"key": "isPrivateSchedule", "val": ["true", "false"]}],
                "rangeFilters": [],
                "orFilters": [],
                "dateFilters": [],
                "sorters": [{"fieldName": "totalPayRateMax", "ascending": "false"}],
                "pageSize": 20,
                "consolidateSchedule": True
            }
        },
        "query": """
        query searchJobCardsByLocation($searchJobRequest: SearchJobRequest!) {
          searchJobCardsByLocation(searchJobRequest: $searchJobRequest) {
            jobCards {
              jobId
              jobTitle
              city
              state
              postalCode
              jobType
              employmentType
              totalPayRateMax
            }
          }
        }
        """
    }

    headers = {
        "Authorization": auth_token,
        "Content-Type": "application/json",
        "Origin": "https://www.jobsatamazon.co.uk",
        "Referer": "https://www.jobsatamazon.co.uk/",
        "User-Agent": random.choice(USER_AGENTS)
    }

    try:
        response = requests.post(GRAPHQL_URL, headers=headers, json=payload, timeout=15)
        if response.status_code != 200:
            print("⚠️ GraphQL request failed:", response.status_code, response.text)
            return

        job_cards = response.json().get("data", {}).get("searchJobCardsByLocation", {}).get("jobCards", [])
        print(f"📦 Found {len(job_cards)} jobs.")
        send_telegram_message(f"[📦 {len(job_cards)} warehouse jobs currently available.](https://www.jobsatamazon.co.uk/app#/jobSearch)")

        for job in job_cards:
            job_id = job.get("jobId")
            if job_id not in seen_jobs:
                seen_jobs.add(job_id)
                msg = (
                    f"💼 *{job.get('jobTitle')}*\n"
                    f"📍 {job.get('city')}, {job.get('state')} {job.get('postalCode')}\n"
                    f"💰 £{job.get('totalPayRateMax')}/hr\n"
                    f"🕒 {job.get('jobType')} | {job.get('employmentType')}\n"
                    f"🔗 [View Job](https://www.jobsatamazon.co.uk/app#/jobDetail?jobId={job_id}&locale=en-GB)"
                )
                print("🔔 New job found:", job.get("jobTitle"))
                send_telegram_message(msg)

    except Exception as e:
        print("⚠️ Fetch error:", e)

# === JOB LOOP ===
def job_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    DEFAULT_TOKEN = "Bearer Status|unauthenticated|Session|exampleToken"

    while True:
        print("⏳ Running scheduled job check...")
        token = loop.run_until_complete(get_auth_token())
        if not token:
            print("⚠️ Using fallback token.")
            token = DEFAULT_TOKEN

        fetch_jobs(token)
        print("✅ Sleeping for 1 hour before next check.")
        time.sleep(3600)

# === KEEP RENDER INSTANCE ALIVE ===
def keep_alive():
    url = os.getenv("RENDER_URL")  # e.g., https://yourapp.onrender.com/
    if not url:
        return
    while True:
        try:
            requests.get(url, timeout=10)
        except:
            pass
        time.sleep(600)

# === FLASK ROUTE ===
@app.route("/")
def home():
    send_telegram_message("✅ Amazon Job Bot is running online.")
    return "✅ Amazon Job Bot is running online."

# === START EVERYTHING ===
if __name__ == "__main__":
    threading.Thread(target=job_loop, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

