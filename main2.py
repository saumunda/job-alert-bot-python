from playwright.sync_api import sync_playwright
import time
import os
import requests

# ------------- Settings -------------
LOCATION = "Sheffield"
WAIT_TIME_MS = 5000           # Wait for page to load GraphQL requests
REFRESH_INTERVAL = 3600       # Seconds between checks

# Telegram Settings
TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("CHAT_ID")

# Keep track of jobs already sent
sent_job_ids = set()

# --------- Function to send message to Telegram ----------
def send_telegram_message(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print("Error sending Telegram message:", e)

# --------- Function to fetch jobs via Playwright ----------
def fetch_jobs():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        graphql_responses = []

        # Intercept GraphQL responses
        def handle_response(response):
            if "graphql" in response.url and response.status == 200:
                try:
                    data = response.json()
                    graphql_responses.append(data)
                except:
                    pass

        page.on("response", handle_response)

        # Visit Amazon Jobs UK search page
        page.goto(f"https://www.jobsatamazon.co.uk/search?location={LOCATION.lower()}")
        page.wait_for_timeout(WAIT_TIME_MS)
        page.reload()
        page.wait_for_timeout(WAIT_TIME_MS)

        browser.close()

        # Extract jobs using the new query structure
        jobs_list = []
        for r in graphql_responses:
            if "data" in r and "searchJobCardsByLocation" in r["data"]:
                job_cards = r["data"]["searchJobCardsByLocation"].get("jobCards", [])
                jobs_list.extend(job_cards)

        return jobs_list

# --------- Main Loop ----------
if __name__ == "__main__":
    while True:
        jobs = fetch_jobs()
        new_jobs = []

        for job in jobs:
            # Use jobTitle + city as a unique ID
            job_id = f"{job.get('jobTitle')}_{job.get('city')}"
            if job_id and job_id not in sent_job_ids:
                new_jobs.append(job)
                sent_job_ids.add(job_id)

        if new_jobs:
            print(f"📢 Found {len(new_jobs)} new jobs in {LOCATION}!")
            for job in new_jobs:
                title = job.get("jobTitle")
                city = job.get("city")
                job_type = job.get("jobType")
                msg = f"💼 <b>{title}</b>\n📍 {city}\n📝 {job_type}"
                send_telegram_message(msg)
        else:
            print("No new jobs found.")

        # Wait before next refresh
        time.sleep(REFRESH_INTERVAL)
