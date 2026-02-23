import requests
from bs4 import BeautifulSoup
import os
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]         # your friend's chat ID
ADMIN_CHAT_ID = os.environ["ADMIN_CHAT_ID"]      # your chat ID

BASE_URL = (
    "https://beta.jobs.nhs.uk/candidate/search/results"
    "?keyword=assistant+psychologist"
    "&location=London"
    "&skipPhraseSuggester=true"
    "&searchFormType=sortBy"
    "&sort=publicationDateDesc"
    "&language=en"
)

TODAY = datetime.today().strftime("%-d %B %Y")  # e.g. "23 February 2026"

# Alert if job title contains this (case-insensitive)
TARGET_TITLE = "team leader"
# Alert if employer/location contains either of these (case-insensitive)
TARGET_EMPLOYERS = [
    "south west london and st georges mental",  # partial match, handles small typos in NHS listing
    "sw17 0yf",
]


def is_match(job):
    title_match = TARGET_TITLE in job["title"].lower()
    employer_lower = job["employer"].lower()
    employer_match = any(t in employer_lower for t in TARGET_EMPLOYERS)
    return title_match or employer_match


def fetch_page(page):
    url = f"{BASE_URL}&page={page}&_cb={int(time.time())}"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; job-alert-bot/1.0)",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    return r.text


def parse_jobs(html):
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    for li in soup.select("li[data-test='search-result']"):
        title_el = li.select_one("a[data-test='search-result-job-title']")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        link = title_el.get("href", "")
        if not link.startswith("http"):
            link = "https://beta.jobs.nhs.uk" + link

        employer_el = li.select_one("div[data-test='search-result-location'] h3")
        employer = employer_el.get_text(separator=" ", strip=True) if employer_el else "Unknown"

        date_el = li.select_one("li[data-test='search-result-publicationDate'] strong")
        date_posted = date_el.get_text(strip=True) if date_el else "Unknown"

        closing_el = li.select_one("li[data-test='search-result-closingDate'] strong")
        closing = closing_el.get_text(strip=True) if closing_el else "Unknown"

        salary_el = li.select_one("li[data-test='search-result-salary'] strong")
        salary = salary_el.get_text(strip=True) if salary_el else "Unknown"

        jobs.append({
            "title": title,
            "employer": employer,
            "date_posted": date_posted,
            "closing": closing,
            "salary": salary,
            "link": link,
        })

    return jobs


def get_all_todays_jobs():
    todays_jobs = []
    page = 1

    while True:
        print(f"Fetching page {page}...")
        html = fetch_page(page)
        jobs = parse_jobs(html)

        if not jobs:
            print(f"  No jobs on page {page}, stopping.")
            break

        for job in jobs:
            print(f"  [{job['date_posted']}] {job['title']} | {job['employer']}")
            if job["date_posted"] == TODAY:
                todays_jobs.append(job)
            else:
                print(f"  Hit older job, stopping pagination.")
                return todays_jobs

        page += 1
        time.sleep(1)

    return todays_jobs


def send_telegram(msg, chat_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": msg}, timeout=10)
    print(f"  Telegram response ({chat_id}): {resp.status_code} {resp.text}")
    return resp

def alert(msg):
    """Send to both friend and admin."""
    send_telegram(msg, CHAT_ID)
    send_telegram(msg, ADMIN_CHAT_ID)

def log(msg):
    """Send only to admin (monitoring/status messages)."""
    send_telegram(msg, ADMIN_CHAT_ID)


def main():
    print(f"Checking NHS Jobs... (today is {TODAY})")

    todays_jobs = get_all_todays_jobs()
    print(f"\n--- Jobs posted TODAY ({TODAY}): {len(todays_jobs)} ---\n")

    # Debug: print everything posted today before filtering
    for job in todays_jobs:
        print(f"  Title    : {job['title']}")
        print(f"  Employer : {job['employer']}")
        print(f"  Match?   : {is_match(job)}")
        print()

    # Filter and alert
    matched = [j for j in todays_jobs if is_match(j)]
    print(f"--- Matched jobs to alert: {len(matched)} ---\n")

    if matched:
        # Send one summary telegram first so we know it's working
        alert(f"🔍 Found {len(matched)} job alert(s) on NHS Jobs today!")
        for job in matched:
            print(f"  Alerting: {job['title']} | {job['employer']}")
            msg = (
                f"🚨 NHS Job Alert!\n\n"
                f"{job['title']}\n"
                f"🏥 {job['employer']}\n"
                f"💰 {job['salary']}\n"
                f"📅 Closes: {job['closing']}\n"
                f"🔗 {job['link']}"
            )
            alert(msg)
    else:
        print("No matching jobs today.")
        # Uncomment the line below to test your Telegram is working:
        log("✅ NHS checker ran - no matching jobs today.")


if __name__ == "__main__":
    main()
    print("Sleeping for 15 minutes...")
    time.sleep(900)