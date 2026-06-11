#!/usr/bin/env python3
"""
KindleFeeder Native Messaging Host
Receives article HTML from the Chrome extension, converts to MOBI via Calibre,
and copies to a connected Kindle. Queues articles if Kindle is not connected.
"""

import sys
import json
import os
import struct
import shutil
import subprocess
import tempfile
import ctypes
import ctypes.wintypes
import re
import datetime
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

APP_DATA = Path(os.environ.get('APPDATA', Path.home())) / 'KindleFeeder'
QUEUE_DIR = APP_DATA / 'queue'
QUEUE_JSON = APP_DATA / 'queue.json'

CALIBRE_PATHS = [
    r'C:\Program Files\Calibre2\ebook-convert.exe',
    r'C:\Program Files (x86)\Calibre2\ebook-convert.exe',
]

# ── Native messaging protocol (4-byte LE length prefix) ──────────────────────

def read_message():
    raw_len = sys.stdin.buffer.read(4)
    if not raw_len or len(raw_len) < 4:
        return None
    msg_len = struct.unpack('<I', raw_len)[0]
    data = sys.stdin.buffer.read(msg_len)
    return json.loads(data.decode('utf-8'))


def send_message(obj):
    data = json.dumps(obj).encode('utf-8')
    sys.stdout.buffer.write(struct.pack('<I', len(data)))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()

# ── Calibre detection ─────────────────────────────────────────────────────────

def find_calibre():
    for p in CALIBRE_PATHS:
        if Path(p).exists():
            return p
    found = shutil.which('ebook-convert')
    return found  # None if not found

# ── Kindle USB detection ──────────────────────────────────────────────────────

def get_removable_drives():
    drives = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for i, letter in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
        if bitmask & (1 << i):
            path = Path(f'{letter}:\\')
            drive_type = ctypes.windll.kernel32.GetDriveTypeW(str(path))
            if drive_type == 2:  # DRIVE_REMOVABLE
                drives.append(path)
    return drives


def get_volume_label(drive_path):
    buf = ctypes.create_unicode_buffer(261)
    try:
        ctypes.windll.kernel32.GetVolumeInformationW(
            str(drive_path), buf, 261, None, None, None, None, 0
        )
        return buf.value
    except Exception:
        return ''


def find_kindle_docs():
    """Return Path to Kindle's documents folder, or None."""
    for drive in get_removable_drives():
        docs = drive / 'documents'
        if docs.exists():
            label = get_volume_label(drive)
            # Kindle 3 labels the drive "Kindle"
            if 'kindle' in label.lower() or True:  # fallback: any removable with /documents
                return docs
    return None

# ── MOBI conversion ───────────────────────────────────────────────────────────

def safe_filename(title):
    """Sanitize title for use as a filename."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', title)
    name = name.strip().strip('.')
    return name[:80] or 'article'


def convert_to_mobi(title, author, html_content, output_path):
    calibre = find_calibre()
    if not calibre:
        raise FileNotFoundError('calibre_not_found')

    with tempfile.TemporaryDirectory() as tmpdir:
        input_html = Path(tmpdir) / 'article.html'
        safe_title = title.replace('"', '&quot;')
        safe_author = (author or 'Unknown').replace('"', '&quot;')

        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{safe_title}</title>
</head>
<body>
  <h1>{safe_title}</h1>
  {html_content}
</body>
</html>"""
        input_html.write_text(html, encoding='utf-8')

        tmp_mobi = Path(tmpdir) / 'output.mobi'
        cmd = [
            calibre,
            str(input_html),
            str(tmp_mobi),
            '--title', title,
            '--authors', author or 'Unknown',
            '--output-profile', 'kindle',
            '--mobi-file-type', 'old',  # force MOBI6 for Kindle 3
            '--no-inline-toc',
            '--disable-font-rescaling',
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f'ebook-convert failed: {result.stderr[-500:]}')

        if not tmp_mobi.exists():
            raise RuntimeError('ebook-convert produced no output file')

        shutil.copy2(str(tmp_mobi), str(output_path))

# ── Queue management ──────────────────────────────────────────────────────────

def load_queue():
    if QUEUE_JSON.exists():
        try:
            return json.loads(QUEUE_JSON.read_text(encoding='utf-8'))
        except Exception:
            return []
    return []


def save_queue(items):
    QUEUE_JSON.write_text(json.dumps(items, indent=2), encoding='utf-8')


def enqueue(title, mobi_path):
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    dest = QUEUE_DIR / mobi_path.name
    shutil.move(str(mobi_path), str(dest))
    items = load_queue()
    items.append({
        'title': title,
        'filename': dest.name,
        'queued_at': datetime.datetime.utcnow().isoformat(),
    })
    save_queue(items)


def flush_queue():
    """Try to copy all queued MOBIs to the Kindle. Returns list of flushed titles."""
    kindle_docs = find_kindle_docs()
    if not kindle_docs:
        items = load_queue()
        return [], len(items)

    items = load_queue()
    flushed = []
    remaining = []
    for item in items:
        src = QUEUE_DIR / item['filename']
        if src.exists():
            try:
                shutil.copy2(str(src), str(kindle_docs / src.name))
                src.unlink()
                flushed.append(item['title'])
            except Exception:
                remaining.append(item)
        # if file is missing, drop it from queue silently

    save_queue(remaining)
    return flushed, len(remaining)

# ── Request handlers ──────────────────────────────────────────────────────────

def handle_convert(msg):
    title = msg.get('title', 'Untitled Article')
    author = msg.get('author', '')
    html_content = msg.get('html_content', '')

    if not html_content.strip():
        return {'error': 'empty_content'}

    APP_DATA.mkdir(parents=True, exist_ok=True)
    filename = safe_filename(title) + '.mobi'
    tmp_mobi = APP_DATA / filename

    try:
        convert_to_mobi(title, author, html_content, tmp_mobi)
    except FileNotFoundError:
        return {'error': 'calibre_not_found', 'download_url': 'https://calibre-ebook.com/download_windows'}
    except Exception as e:
        return {'error': str(e)}

    kindle_docs = find_kindle_docs()
    if kindle_docs:
        try:
            shutil.copy2(str(tmp_mobi), str(kindle_docs / filename))
            tmp_mobi.unlink(missing_ok=True)
            return {'status': 'sent', 'title': title}
        except Exception as e:
            return {'error': f'copy_failed: {e}'}
    else:
        enqueue(title, tmp_mobi)
        items = load_queue()
        return {'status': 'queued', 'title': title, 'queue_count': len(items)}


def handle_flush_queue(_msg):
    flushed, remaining = flush_queue()
    return {'flushed': flushed, 'queue_count': remaining}


def handle_check_calibre(_msg):
    calibre = find_calibre()
    if calibre:
        return {'calibre_found': True, 'path': calibre}
    return {'calibre_missing': True, 'download_url': 'https://calibre-ebook.com/download_windows'}

# ── Main loop ─────────────────────────────────────────────────────────────────

HANDLERS = {
    'convert': handle_convert,
    'flush_queue': handle_flush_queue,
    'check_calibre': handle_check_calibre,
}

def main():
    while True:
        msg = read_message()
        if msg is None:
            break
        action = msg.get('action', '')
        handler = HANDLERS.get(action)
        if handler:
            try:
                result = handler(msg)
            except Exception as e:
                result = {'error': str(e)}
        else:
            result = {'error': f'unknown_action: {action}'}
        send_message(result)


if __name__ == '__main__':
    main()
