import requests
import json
import time
import schedule
import os
from datetime import datetime
from telegram import Bot

# --- CONFIG ---
AUTH_TOKEN = os.getenv("AUTH_TOKEN")  # Set in Render Environment
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

GRAPHQL_URL = "https://qy64m4juabaffl7tjakii4gdoa.appsync-api.eu-west-1.amazonaws.com/graphql"

QUERY = {
    "query": """query searchJobCardsByLocation($searchJobRequest: SearchJobRequest!) {
      searchJobCardsByLocation(searchJobRequest: $searchJobRequest) {
        jobCards {
          jobId
          jobTitle
          city
          state
          totalPayRateMaxL10N
          locationName
          employmentType
        }
      }
    }""",
    "variables": {
        "searchJobRequest": {
            "locale": "en-GB",
            "country": "United Kingdom",
            "keyWords": "Sheffield",
            "equalFilters": [],
            "containFilters": [{"key": "isPrivateSchedule", "val": ["true", "false"]}],
            "rangeFilters": [],
            "orFilters": [],
            "dateFilters": [],
            "sorters": [{"fieldName": "totalPayRateMax", "ascending": "false"}],
            "pageSize": 50,
            "consolidateSchedule": True
        }
    }
}


def fetch_jobs():
    headers = {
        'authorization': AUTH_TOKEN,
        'content-type': 'application/json',
        'origin': 'https://www.jobsatamazon.co.uk',
        'referer': 'https://www.jobsatamazon.co.uk/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }

    try:
        response = requests.post(GRAPHQL_URL, headers=headers, data=json.dumps(QUERY))
        data = response.json()

        if "errors" in data:
            print(f"⚠️ GraphQL Error: {data['errors']}")
            return []

        jobs = data['data']['searchJobCardsByLocation']['jobCards']
        print(f"[{datetime.now()}] ✅ Fetched {len(jobs)} jobs.")
        return jobs

    except Exception as e:
        print(f"❌ Request failed: {e}")
        return []


def send_to_telegram(jobs):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Telegram config missing.")
        return

    bot = Bot(token=TELEGRAM_TOKEN)
    if not jobs:
        bot.send_message(chat_id=CHAT_ID, text="No new jobs found.")
        return

    msg = "📢 *Amazon Jobs (Sheffield)*\n\n"
    for job in jobs[:5]:  # top 5
        msg += f"🧾 *{job['jobTitle']}*\n📍 {job['locationName']}\n💷 {job['totalPayRateMaxL10N']}\n\n"

    bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")


def main_job():
    print("🔁 Running scheduled job fetch...")
    jobs = fetch_jobs()
    send_to_telegram(jobs)
    print("✅ Job cycle complete.\n")


# Schedule every hour
schedule.every(1).hours.do(main_job)

# Run immediately on start
main_job()

while True:
    schedule.run_pending()
    time.sleep(30)
