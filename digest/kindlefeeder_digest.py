"""
KindleFeeder Daily Digest
Fetches opinion articles from NYTimes, Guardian, BBC, LiveMint,
synthesizes them with Claude, and drops a MOBI into the KindleFeeder queue.
"""

import os
import sys
import json
import shutil
import struct
import subprocess
import tempfile
import datetime
import logging
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import feedparser
import anthropic

from fetcher import fetch_article

# ── Config ────────────────────────────────────────────────────────────────────

APP_DATA = Path(os.environ.get('APPDATA', Path.home())) / 'KindleFeeder'
QUEUE_DIR = APP_DATA / 'queue'
QUEUE_JSON = APP_DATA / 'queue.json'
SETTINGS_JSON = APP_DATA / 'digest_settings.json'
LOG_FILE = APP_DATA / 'digest.log'

TARGET_ARTICLES = 15
MAX_PER_SOURCE = 5

CALIBRE_PATHS = [
    r'C:\Program Files\Calibre2\ebook-convert.exe',
    r'C:\Program Files (x86)\Calibre2\ebook-convert.exe',
]

FEEDS = [
    {
        'source': 'NYTimes Opinion',
        'url': 'https://rss.nytimes.com/services/xml/rss/nyt/Opinion.xml',
        'filter': None,
    },
    {
        'source': 'Guardian Opinion',
        'url': 'https://www.theguardian.com/uk/commentisfree/rss',
        'filter': None,
    },
    {
        'source': 'BBC',
        'url': 'https://feeds.bbci.co.uk/news/world/rss.xml',
        # Only include BBC items tagged as analysis/opinion
        'filter': lambda e: any(
            kw in ' '.join(t.get('term', '') for t in e.get('tags', [])).lower()
            for kw in ('analysis', 'explainer', 'in depth', 'opinion', 'viewpoint')
        ),
    },
    {
        'source': 'LiveMint Opinion',
        'url': 'https://www.livemint.com/rss/opinion',
        'filter': None,
    },
]

# ── Logging ───────────────────────────────────────────────────────────────────

APP_DATA.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)
log = logging.getLogger('digest')

# ── Settings ──────────────────────────────────────────────────────────────────

def load_settings():
    if SETTINGS_JSON.exists():
        try:
            return json.loads(SETTINGS_JSON.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {}

# ── Feed fetching & selection ─────────────────────────────────────────────────

def _normalise_url(url):
    p = urlparse(url)
    return urlunparse(p._replace(query='', fragment=''))


def _age_hours(entry):
    import time as _time
    t = entry.get('published_parsed') or entry.get('updated_parsed')
    if not t:
        return 999
    return (_time.time() - _time.mktime(t)) / 3600


def fetch_candidates():
    """Fetch all feeds and return scored, deduplicated candidate list."""
    seen_urls = set()
    candidates = []

    for feed_cfg in FEEDS:
        log.info('Fetching feed: %s', feed_cfg['source'])
        try:
            parsed = feedparser.parse(feed_cfg['url'])
        except Exception as e:
            log.warning('Feed error %s: %s', feed_cfg['source'], e)
            continue

        source_count = 0
        for entry in parsed.entries:
            if source_count >= MAX_PER_SOURCE:
                break

            url = entry.get('link', '')
            if not url:
                continue

            norm = _normalise_url(url)
            if norm in seen_urls:
                continue

            # Apply source-specific filter (e.g. BBC analysis-only)
            if feed_cfg['filter'] and not feed_cfg['filter'](entry):
                continue

            age = _age_hours(entry)
            score = 0
            if age <= 24:
                score += 3
            elif age <= 48:
                score += 1

            summary = entry.get('summary', '')
            if len(summary) > 200:
                score += 1

            seen_urls.add(norm)
            candidates.append({
                'source': feed_cfg['source'],
                'title': entry.get('title', 'Untitled'),
                'url': url,
                'summary': summary,
                'score': score,
            })
            source_count += 1

    candidates.sort(key=lambda x: x['score'], reverse=True)
    return candidates[:TARGET_ARTICLES]

# ── Article synthesis ─────────────────────────────────────────────────────────

def synthesize(title, text, api_key):
    client = anthropic.Anthropic(api_key=api_key)
    prompt = (
        'You are a newspaper editor preparing a Kindle digest. '
        'Condense the following opinion article into 400-500 words of clean, '
        'readable prose. Keep the author\'s core argument, key evidence, and '
        'any memorable quotes. Do not use bullet points. Write in third person. '
        'Output only the condensed article — no preamble, no labels.\n\n'
        f'Title: {title}\n\nArticle:\n{text[:8000]}'
    )
    msg = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=700,
        messages=[{'role': 'user', 'content': prompt}],
    )
    return msg.content[0].text.strip()

# ── HTML assembly ─────────────────────────────────────────────────────────────

def assemble_html(articles, date_str):
    parts = [f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>KindleFeeder Daily — {date_str}</title>
</head>
<body>
<h1>KindleFeeder Daily</h1>
<p>{date_str} &bull; {len(articles)} opinion pieces</p>
"""]
    for art in articles:
        parts.append('<mbp:pagebreak/>')
        source = art['source']
        title = art['title'].replace('<', '&lt;').replace('>', '&gt;')
        body = art['synthesized'].replace('\n\n', '</p><p>').replace('\n', ' ')
        parts.append(f"""
<h2>{title}</h2>
<p><em>{source}</em></p>
<p>{body}</p>
""")
    parts.append('</body></html>')
    return ''.join(parts)

# ── Calibre conversion ────────────────────────────────────────────────────────

def find_calibre():
    for p in CALIBRE_PATHS:
        if Path(p).exists():
            return p
    import shutil as _shutil
    return _shutil.which('ebook-convert')


def convert_to_mobi(title, html_content, output_path):
    calibre = find_calibre()
    if not calibre:
        raise FileNotFoundError('Calibre not found. Install from calibre-ebook.com')

    with tempfile.TemporaryDirectory() as tmpdir:
        input_html = Path(tmpdir) / 'digest.html'
        input_html.write_text(html_content, encoding='utf-8')
        tmp_mobi = Path(tmpdir) / 'digest.mobi'

        cmd = [
            calibre,
            str(input_html), str(tmp_mobi),
            '--title', title,
            '--authors', 'KindleFeeder',
            '--output-profile', 'kindle',
            '--mobi-file-type', 'old',
            '--no-inline-toc',
            '--disable-font-rescaling',
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            raise RuntimeError(f'ebook-convert failed:\n{result.stderr[-800:]}')
        if not tmp_mobi.exists():
            raise RuntimeError('ebook-convert produced no output file')

        shutil.copy2(str(tmp_mobi), str(output_path))

# ── Queue ─────────────────────────────────────────────────────────────────────

def enqueue(title, mobi_path):
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    dest = QUEUE_DIR / mobi_path.name
    shutil.move(str(mobi_path), str(dest))
    items = []
    if QUEUE_JSON.exists():
        try:
            items = json.loads(QUEUE_JSON.read_text(encoding='utf-8'))
        except Exception:
            pass
    items.append({
        'title': title,
        'filename': dest.name,
        'queued_at': datetime.datetime.utcnow().isoformat(),
    })
    QUEUE_JSON.write_text(json.dumps(items, indent=2), encoding='utf-8')

# ── Main ──────────────────────────────────────────────────────────────────────

def run(api_key=None, progress_cb=None):
    """
    Main digest run. progress_cb(msg) is called with status strings
    if provided (used by the tray UI to stream progress).
    """
    # Force UTF-8 output so arrow characters don't crash on Windows cp1252
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    def progress(msg):
        log.info(msg)
        print(msg, flush=True)
        if progress_cb:
            progress_cb(msg)

    api_key = api_key or os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        progress('ERROR: ANTHROPIC_API_KEY not set. Open Digest Settings to add it.')
        sys.exit(1)

    today = datetime.date.today()
    date_str = today.strftime('%A, %d %B %Y')
    filename = f'KindleFeeder_Daily_{today.isoformat()}.mobi'

    progress(f'=== KindleFeeder Daily Digest — {date_str} ===')
    progress('Fetching RSS feeds...')
    candidates = fetch_candidates()
    progress(f'Selected {len(candidates)} articles')

    articles = []
    for i, cand in enumerate(candidates, 1):
        progress(f'[{i}/{len(candidates)}] {cand["source"]}: {cand["title"][:60]}')
        fetched = fetch_article(cand['url'], rss_summary=cand['summary'])
        text = fetched['text']
        if not text.strip():
            progress(f'  -> skipped (no content)')
            continue
        try:
            synthesized = synthesize(cand['title'], text, api_key)
            articles.append({**cand, 'synthesized': synthesized})
            progress(f'  -> synthesized ({len(synthesized)} chars)')
        except Exception as e:
            progress(f'  -> synthesis failed: {e}')

    if not articles:
        progress('ERROR: No articles — aborting.')
        sys.exit(1)

    progress(f'Assembling HTML ({len(articles)} articles)...')
    html = assemble_html(articles, date_str)

    APP_DATA.mkdir(parents=True, exist_ok=True)
    tmp_mobi = APP_DATA / filename
    progress('Converting to MOBI (Calibre)...')
    try:
        convert_to_mobi(f'KindleFeeder Daily — {date_str}', html, tmp_mobi)
    except Exception as e:
        progress(f'ERROR: Conversion failed: {e}')
        sys.exit(1)

    progress('Adding to Kindle queue...')
    enqueue(f'KindleFeeder Daily — {date_str}', tmp_mobi)
    progress(f'Done. {filename} queued — will send when Kindle is connected.')


if __name__ == '__main__':
    run()
