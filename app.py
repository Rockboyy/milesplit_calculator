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

from webdriver_manager.chrome import ChromeDriverManager

app = Flask(__name__)

# matches either "M:SS.ms" or "SS.ms"
TIME_RE = re.compile(r"^(?:\d+:\d+\.\d+|\d+\.\d+)$")

def setup_driver():
    options = Options()
    # point to the Chrome installed in the container
    options.binary_location = "/usr/bin/google-chrome-stable"
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-zygote")
    # auto‑download matching ChromeDriver
    driver_path = ChromeDriverManager().install()
    service = Service(driver_path)
    return webdriver.Chrome(service=service, options=options)

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
        return None, True  # nothing loaded → treat as end

    if "There are no assignments to display." in driver.page_source:
        return None, True

    total = 0.0
    any_heat = False
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
            any_heat = True
            total += max(times)
    return (total, False) if any_heat else (None, False)

def calculate_total(meet_id: str, upto_event: int = None) -> float:
    driver = setup_driver()
    grand = 0.0
    eid = 1
    while True:
        gender = 'F' if eid % 2 else 'M'
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

INDEX_HTML = '''
<!doctype html>
<html><head><title>Track Meet Time Calculator</title></head>
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
<html><head><title>Result</title></head>
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
                upto = int(request.form.get('upto_event','').strip())
            except ValueError:
                upto = None

        seconds = calculate_total(meet_id,
                                  upto_event=upto if mode=='upto' else None)
        mins = int(seconds // 60)
        secs = seconds - mins * 60
        formatted = f"{mins}:{secs:05.2f}"
        description = (f"Total time for meet {meet_id}" 
                       if mode=='total'
                       else f"Time up to event {upto} for meet {meet_id}")
        return render_template_string(RESULT_HTML,
                                      description=description,
                                      formatted=formatted,
                                      seconds=f"{seconds:.2f}")
    return render_template_string(INDEX_HTML)

if __name__ == '__main__':
    # on Render this will be managed by gunicorn
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
