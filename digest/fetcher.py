"""
fetcher.py — Article body fetcher for KindleFeeder Digest.
Reads Chrome cookies for paywalled sites (NYTimes, LiveMint).
Falls back to RSS summary if body extraction fails or is too short.
"""

import time
import requests
from readability import Document
from bs4 import BeautifulSoup

BROWSER_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/124.0.0.0 Safari/537.36'
)

# Sites that need Chrome login cookies
COOKIE_DOMAINS = {
    'nytimes.com': '.nytimes.com',
    'livemint.com': '.livemint.com',
}

MIN_BODY_CHARS = 500


def _get_chrome_cookies(url):
    for key, domain in COOKIE_DOMAINS.items():
        if key in url:
            try:
                import browser_cookie3
                return browser_cookie3.chrome(domain_name=domain)
            except Exception:
                return None
    return None


def _extract_text(html):
    return BeautifulSoup(html, 'lxml').get_text(' ', strip=True)


def fetch_article(url, rss_summary='', retries=1):
    """
    Fetch and clean article body from URL.
    Returns dict: {title, text}
    Falls back to rss_summary if body is too short or fetch fails.
    """
    cookies = _get_chrome_cookies(url)

    for attempt in range(retries + 1):
        try:
            r = requests.get(
                url,
                headers={'User-Agent': BROWSER_UA},
                cookies=cookies,
                timeout=15,
            )
            r.raise_for_status()
            doc = Document(r.text)
            text = _extract_text(doc.summary())
            if len(text) >= MIN_BODY_CHARS:
                return {'title': doc.short_title(), 'text': text}
        except Exception:
            if attempt < retries:
                time.sleep(2)

    # Fallback to RSS summary
    return {'title': '', 'text': rss_summary}
