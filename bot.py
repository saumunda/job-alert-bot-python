import requests
import json
import time

# === CONFIGURATION ===
GRAPHQL_URL = "https://qy64m4juabaffl7tjakii4gdoa.appsync-api.eu-west-1.amazonaws.com/graphql"
JOB_PAGE_URL = "https://www.jobsatamazon.co.uk/app#/jobSearch?query=Warehouse%20Operative&locale=en-GB"

# Telegram settings
TELEGRAM_BOT_TOKEN = "8214392800:AAGrRksRKpAD8Oa8H4aByo5XKSwc_9SM9Bo"
CHAT_ID = "7943617436"

# To track what we've already sent
seen_jobs = set()


def get_auth_token():
    """Fetch session token automatically from the job site cookies"""
    try:
        session = requests.Session()
        resp = session.get(JOB_PAGE_URL, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "text/html",
            "Referer": "https://www.jobsatamazon.co.uk/"
        })
        for cookie in session.cookies:
            if "session" in cookie.name.lower():
                print(f"✅ Found session cookie: {cookie.name}")
                return f"Bearer {cookie.value}"
        print("⚠️ No valid session cookie found.")
    except Exception as e:
        print(f"❌ Failed to fetch AUTH_TOKEN: {e}")
    return None


def send_telegram_message(message):
    """Send Telegram alert"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message}
        requests.post(url, data=payload)
    except Exception as e:
        print(f"⚠️ Telegram send error: {e}")


def fetch_jobs(auth_token):
    """Perform the GraphQL query and send alerts for new jobs"""
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
              totalPayRateMax
              locationName
              totalPayRateMaxL10N
              employmentType
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    response = requests.post(GRAPHQL_URL, headers=headers, json=payload)
    if response.status_code == 200:
        data = response.json()
        job_cards = data.get("data", {}).get("searchJobCardsByLocation", {}).get("jobCards", [])
        print(f"📦 Found {len(job_cards)} jobs.")

        for job in job_cards:
            job_id = job.get("jobId")
            if job_id not in seen_jobs:
                seen_jobs.add(job_id)
                title = job.get("jobTitle")
                city = job.get("city")
                pay = job.get("totalPayRateMax")
                msg = f"💼 *{title}* in {city}\n💰 Pay: £{pay}/hr\n🔗 https://www.jobsatamazon.co.uk/app#/jobDetail/{job_id}"
                print("🔔 New job found:", title)
                send_telegram_message(msg)
    else:
        print("⚠️ GraphQL request failed:", response.status_code, response.text)


if __name__ == "__main__":
    while True:
        port = int(os.getenv("PORT", 5000))
        app.run(host="0.0.0.0", port=port)
        livecheck = "✅ Amazon Job Bot is running (Offline).."
        send_telegram_message(livecheck)
        token = get_auth_token()
        if token:
            print("✅ Using token:", token[:60], "...")
            fetch_jobs(token)
        else:
            print("⚠️ Could not get a token. Retrying in 10 mins...")
        time.sleep(600)
