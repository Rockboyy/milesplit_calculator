# app.py
from flask import Flask, request, render_template_string
import re, os

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, InvalidSessionIdException

from webdriver_manager.chrome import ChromeDriverManager

app = Flask(__name__)

# matches either "M:SS.ms" or "SS.ms"
TIME_RE = re.compile(r"^(?:\d+:\d+\.\d+|\d+\.\d+)$")

def setup_driver():
    options = Options()
    options.binary_location = "/usr/bin/google-chrome-stable"
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # auto‑download matching ChromeDriver
    path = ChromeDriverManager().install()
    return webdriver.Chrome(service=Service(path), options=options)

def parse_time_to_seconds(t: str) -> float:
    if ":" in t:
        mins, rest = t.split(":", 1)
        return int(mins) * 60 + float(rest)
    return float(t)

def get_event_total(driver, meet_id: str, event_id: int, gender: str):
    url = f"https://milesplit.live/meets/{meet_id}/events/{event_id}/assignments/F/{gender}"
    driver.get(url)

    try:
        WebDriverWait(driver, 10).until(
            EC.any_of(
                EC.presence_of_element_located((By.CSS_SELECTOR, "td.seed")),
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'There are no assignments to display')]"))
            )
        )
    except TimeoutException:
        return None, True

    if "There are no assignments to display." in driver.page_source:
        return None, True

    total, saw_heat = 0.0, False
    for tbl in driver.find_elements(By.TAG_NAME, "table"):
        seeds = tbl.find_elements(By.CSS_SELECTOR, "td.seed")
        times = []
        for td in seeds:
            txt = td.text.strip()
            if "-" in txt:
                continue
            if TIME_RE.match(txt):
                times.append(parse_time_to_seconds(txt))
        if times:
            saw_heat = True
            total += max(times)

    return (total, False) if saw_heat else (None, False)

def calculate_total(meet_id: str, upto_event: int = None) -> float:
    driver = setup_driver()
    grand, eid = 0.0, 1

    while True:
        gender = 'F' if eid % 2 else 'M'
        try:
            res, done = get_event_total(driver, meet_id, eid, gender)
        except InvalidSessionIdException:
            # Chrome session died mid-scrape: restart once and retry
            driver.quit()
            driver = setup_driver()
            res, done = get_event_total(driver, meet_id, eid, gender)

        if done:
            break
        if res is not None:
            grand += res

        eid += 1
        if upto_event and eid >= upto_event:
            break

    driver.quit()
    return grand

INDEX_HTML = '''…'''  # unchanged
RESULT_HTML = '''…'''  # unchanged

@app.route('/', methods=['GET','POST'])
def index():
    if request.method == 'POST':
        meet_id = request.form['meet_id'].strip()
        mode = request.form.get('mode')
        upto = None
        if mode == 'upto':
            try: upto = int(request.form['upto_event'])
            except: upto = None

        secs = calculate_total(meet_id,
                               upto_event = upto if mode=='upto' else None)
        mins = int(secs // 60)
        s = secs - mins * 60
        formatted = f"{mins}:{s:05.2f}"
        desc = (f"Total time for meet {meet_id}"
                if mode=='total'
                else f"Time up to event {upto} for meet {meet_id}")

        return render_template_string(RESULT_HTML,
                                      description=desc,
                                      formatted=formatted,
                                      seconds=f"{secs:.2f}")
    return render_template_string(INDEX_HTML)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT',5000)))
