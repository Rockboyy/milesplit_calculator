from flask import Flask, request, render_template_string
import re
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

app = Flask(__name__)

# Path to your ChromeDriver executable (adjust as needed)
CHROMEDRIVER_PATH = "/usr/local/bin/chromedriver"

# Regex to match MM:SS.ms or SS.ms
TIME_RE = re.compile(r"^(?:\d+:\d+\.\d+|\d+\.\d+)$")

# --- Selenium setup ---
def setup_driver():
    if not (os.path.isfile(CHROMEDRIVER_PATH) and os.access(CHROMEDRIVER_PATH, os.X_OK)):
        raise FileNotFoundError(f"chromedriver not found or not executable: {CHROMEDRIVER_PATH}")
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    return webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=options)

# --- Time parsing ---
def parse_time_to_seconds(t: str) -> float:
    if ":" in t:
        mins, rest = t.split(":", 1)
        return int(mins) * 60 + float(rest)
    return float(t)

# --- Event scraping ---
def get_event_total(driver, meet_id: str, event_id: int, gender: str):
    url = f"https://milesplit.live/meets/{meet_id}/events/{event_id}/assignments/F/{gender}"
    driver.get(url)
    # wait for seeds or end message
    try:
        WebDriverWait(driver, 20).until(
            EC.any_of(
                EC.presence_of_element_located((By.CSS_SELECTOR, "td.seed")),
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'There are no assignments to display')]") )
            )
        )
    except TimeoutException:
        # no content
        return None, True
    if "There are no assignments to display." in driver.page_source:
        return None, True

    tables = driver.find_elements(By.TAG_NAME, "table")
    event_total = 0.0
    any_heat = False
    for tbl in tables:
        seeds = tbl.find_elements(By.CSS_SELECTOR, "td.seed")
        times = []
        for td in seeds:
            text = td.text.strip()
            if '-' in text:
                continue
            if TIME_RE.match(text):
                times.append(parse_time_to_seconds(text))
        if times:
            any_heat = True
            event_total += max(times)
    if not any_heat:
        return None, False
    return event_total, False

# --- Aggregate totals ---
def calculate_total(meet_id: str, upto_event: int=None) -> float:
    driver = setup_driver()
    total = 0.0
    event_id = 1
    while True:
        gender = 'F' if event_id % 2 == 1 else 'M'
        result, end_flag = get_event_total(driver, meet_id, event_id, gender)
        if end_flag:
            break
        if result is not None:
            total += result
        event_id += 1
        if upto_event and event_id >= upto_event:
            break
    driver.quit()
    return total

# --- Flask routes ---
INDEX_HTML = '''
<!doctype html>
<html>
  <head><title>Track Meet Time Calculator</title></head>
  <body>
    <h1>Track Meet Time Calculator</h1>
    <form method="post">
      <label>Meet ID: <input name="meet_id" required></label><br>
      <label><input type="radio" name="mode" value="total" checked> Total meet time</label><br>
      <label><input type="radio" name="mode" value="upto"> Time up to event #</label>
      <input name="upto_event" size="3" placeholder="Event #"><br>
      <button type="submit">Calculate</button>
    </form>
  </body>
</html>
'''

RESULT_HTML = '''
<!doctype html>
<html>
  <head><title>Result</title></head>
  <body>
    <h1>Result</h1>
    <p>{{ description }}: <strong>{{ formatted }}</strong> ({{ seconds }} seconds)</p>
    <a href="/">↩ Back</a>
  </body>
</html>
'''

@app.route('/', methods=['GET','POST'])
def index():
    if request.method == 'POST':
        meet_id = request.form['meet_id'].strip()
        mode = request.form.get('mode')
        upto = None
        if mode == 'upto':
            try:
                upto = int(request.form.get('upto_event', '').strip())
            except ValueError:
                upto = None

        seconds = calculate_total(meet_id, upto_event=upto if mode=='upto' else None)
        mins = int(seconds // 60)
        secs = seconds - mins * 60
        formatted = f"{mins}:{secs:05.2f}"
        description = (f"Total time for meet {meet_id}" if mode=='total'
                       else f"Time up to event {upto} for meet {meet_id}")
        return render_template_string(RESULT_HTML, description=description,
                                      formatted=formatted, seconds=f"{seconds:.2f}")
    return render_template_string(INDEX_HTML)

if __name__ == '__main__':
    app.run(debug=True)
