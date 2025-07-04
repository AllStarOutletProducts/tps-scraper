# app.py
from flask import Flask, request, jsonify
import os, requests, re
from bs4 import BeautifulSoup
from urllib.parse import quote
from urllib.parse import urljoin

app = Flask(__name__)
SCRAPE_DO_API_KEY = os.getenv('SCRAPE_DO_API_KEY')
if not SCRAPE_DO_API_KEY:
    raise RuntimeError("Set SCRAPE_DO_API_KEY in your environment!")

@app.route('/find_email', methods=['POST'])
def find_email():
    data  = request.get_json() or {}
    name  = data.get('name', '').strip()
    city  = data.get('city', '').strip()
    state = data.get('state', '').strip()

    if not name:
        return jsonify(error="Missing 'name'"), 400

    # ─── Build the search‐results URL ──────────────────────────────
    base = "https://www.truepeoplesearch.com/results"
    qs   = {'name': name}
    if city and state:      qs['citystatezip'] = f"{city}, {state}"
    elif state:             qs['citystatezip'] = state
    results_url = requests.Request('GET', base, params=qs).prepare().url

    # ─── Fetch results page ────────────────────────────────────────
    enc = quote(results_url, safe='')
    scrape_results = (
      f"https://api.scrape.do"
      f"?token={SCRAPE_DO_API_KEY}"
      f"&url={enc}&geoCode=us&super=true"
    )
    r = requests.get(scrape_results, timeout=30)
    r.raise_for_status()
    results_html = r.text
    results_soup = BeautifulSoup(results_html, 'html.parser')

    # ─── Find the “View Details” link ─────────────────────────────
    # 1) Find the exact anchor whose text is “View Details”
    detail_link = results_soup.find(
        'a',
        string=lambda t: t and 'View Details' in t
    )
    if not detail_link:
        return jsonify(error="No detail link found"), 404

    # 2) href now contains BOTH the path AND the ?name=…&citystatezip=… 
    raw_href = detail_link['href']

    # 3) Build the full URL
    detail_url = urljoin("https://www.truepeoplesearch.com", raw_href)

    # e.g. detail_url == 
    # "https://www.truepeoplesearch.com/find/person/px22luu44u428rn224ul9?"
    #    "name=Joann+Hollen&citystatezip=Georgetown%2C+KY"
    
    enc2 = quote(detail_url, safe='')
    scrape_detail = (
      f"https://api.scrape.do"
      f"?token={SCRAPE_DO_API_KEY}"
      f"&url={enc2}&geoCode=us&super=true"
    )
    d = requests.get(scrape_detail, timeout=30)
    d.raise_for_status()
    detail_html = d.text
    detail_soup = BeautifulSoup(detail_html, 'html.parser')

    # ─── Extract every email‐like string and drop the TPS support address ───────────
    all_emails = sorted(set(re.findall(r'[\w\.-]+@[\w\.-]+', detail_html)))
    emails = [e for e in all_emails if not e.lower().endswith('@truepeoplesearch.com')]


    return jsonify({
        "query": qs,
        "emails": emails or ["not available"]
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
