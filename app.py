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

    # ─── Build the search-results URL ──────────────────────────────
    base = "https://www.truepeoplesearch.com/results"
    qs   = {'name': name}
    if city and state:
        qs['citystatezip'] = f"{city}, {state}"
    elif state:
        qs['citystatezip'] = state
    results_url = requests.Request('GET', base, params=qs).prepare().url

    # 🖨️ Print the unencoded results URL for debugging
    print("TPS RESULTS URL (unencoded):", results_url)

    # ─── Fetch results page ────────────────────────────────────────
    enc = quote(results_url, safe='')
    scrape_results = (
        f"https://api.scrape.do"
        f"?token={SCRAPE_DO_API_KEY}"
        f"&url={enc}&geoCode=us&super=true"
    )
    
    # 🖨️ Print the scrape.do results URL for debugging
    print("SCRAPE RESULTS URL:", scrape_results)

    r = requests.get(scrape_results, timeout=30)
    r.raise_for_status()
    results_html = r.text
    results_soup = BeautifulSoup(results_html, 'html.parser')

    # 🖨️ Print all links for debugging
    for a in results_soup.find_all('a', href=True):
        print("ANCHOR TAG:", a, "TEXT:", a.get_text())
        
        
    # Print first 500 characters for debugging
    print("RESULTS_HTML SAMPLE:", results_html[:500])

    filtered_links = [
        link for link in results_soup.find_all('a', href=True)
        if 'View Details' in link.get_text()
    ]

    print("DETAIL LINKS FOUND:", [link['href'] for link in filtered_links])

    if not filtered_links:
        return jsonify(error="No detail link found"), 404

    # 🟢 Just pick the first one for now:
    detail_link = filtered_links[0]
    raw_href = detail_link['href']

    # If the link itself has no querystring, grab the original one from results_url
    if '?' not in raw_href:
        query = results_url.split('?', 1)[1]
        raw_href = f"{raw_href}?{query}"

    detail_url = urljoin("https://www.truepeoplesearch.com", raw_href)

    # 🖨️ Print the unencoded detail URL for debugging
    print("TPS DETAIL URL (unencoded):", detail_url)

    # ─── Fetch detail page ─────────────────────────────────────────
    enc2 = quote(detail_url, safe='')
    scrape_detail = (
        f"https://api.scrape.do"
        f"?token={SCRAPE_DO_API_KEY}"
        f"&url={enc2}&geoCode=us&super=true"
    )

    # 🖨️ Print the scrape.do detail URL for debugging
    print("SCRAPE DETAIL URL:", scrape_detail)

    d = requests.get(scrape_detail, timeout=30)
    d.raise_for_status()
    detail_html = d.text
    detail_soup = BeautifulSoup(detail_html, 'html.parser')

    # ─── Extract every email-like string and drop TPS support address ───────────
    all_emails = sorted(set(re.findall(r'[\w\.-]+@[\w\.-]+', detail_html)))
    emails = [e for e in all_emails if not e.lower().endswith('@truepeoplesearch.com')]

    return jsonify({
        "query": qs,
        "emails": emails or ["not available"]
    })

# ←────── HEALTH-CHECK ENDPOINT ───────→
@app.route('/health', methods=['GET'])
def health():
    return jsonify(status='ok'), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
