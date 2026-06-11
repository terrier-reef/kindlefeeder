"""
KindleFeeder Tray — persistent background helper.
Runs with pythonw.exe (no console window).
Shows a green system-tray icon while running.
Polls for a connected Kindle every 30 s and flushes the queue.
"""

import sys
import os
import json
import shutil
import ctypes
import ctypes.wintypes
import threading
import datetime
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

# ── Paths (must match kindlefeeder_host.py) ───────────────────────────────────

APP_DATA = Path(os.environ.get('APPDATA', Path.home())) / 'KindleFeeder'
QUEUE_DIR = APP_DATA / 'queue'
QUEUE_JSON = APP_DATA / 'queue.json'
LOG_FILE = APP_DATA / 'tray.log'

POLL_INTERVAL_SECONDS = 30

# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg):
    APP_DATA.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f'[{timestamp}] {msg}\n')
    except Exception:
        pass

# ── Tray icon (green circle, drawn with Pillow) ───────────────────────────────

def make_icon(color='#22c55e'):
    """Draw a 64×64 circle icon."""
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill=color)
    return img

# ── Kindle USB detection (duplicated from host so tray is self-contained) ─────

def get_removable_drives():
    drives = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for i, letter in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
        if bitmask & (1 << i):
            path = Path(f'{letter}:\\')
            if ctypes.windll.kernel32.GetDriveTypeW(str(path)) == 2:
                drives.append(path)
    return drives


def find_kindle_docs():
    for drive in get_removable_drives():
        docs = drive / 'documents'
        if docs.exists():
            return docs
    return None

# ── Queue flush ───────────────────────────────────────────────────────────────

def load_queue():
    if QUEUE_JSON.exists():
        try:
            return json.loads(QUEUE_JSON.read_text(encoding='utf-8'))
        except Exception:
            return []
    return []


def save_queue(items):
    QUEUE_JSON.write_text(json.dumps(items, indent=2), encoding='utf-8')


def flush_queue():
    kindle_docs = find_kindle_docs()
    if not kindle_docs:
        return 0

    items = load_queue()
    if not items:
        return 0

    remaining = []
    sent = 0
    for item in items:
        src = QUEUE_DIR / item['filename']
        if src.exists():
            try:
                shutil.copy2(str(src), str(kindle_docs / src.name))
                src.unlink()
                sent += 1
                log(f'Sent queued article: {item["title"]}')
            except Exception as e:
                log(f'Failed to send {item["title"]}: {e}')
                remaining.append(item)

    save_queue(remaining)
    return sent

# ── Polling loop ──────────────────────────────────────────────────────────────

def poll_loop(icon):
    """Run in a background thread. Polls for Kindle and flushes queue."""
    import time
    log('Tray started, polling every 30 s')
    while getattr(icon, '_running', True):
        try:
            queue = load_queue()
            if queue:
                sent = flush_queue()
                if sent:
                    icon.notify(
                        f'Sent {sent} article(s) to your Kindle.',
                        'KindleFeeder'
                    )
        except Exception as e:
            log(f'Poll error: {e}')
        time.sleep(POLL_INTERVAL_SECONDS)


# ── Tray menu actions ─────────────────────────────────────────────────────────

def on_check_now(icon, item):
    queue = load_queue()
    if not queue:
        icon.notify('No articles in queue.', 'KindleFeeder')
        return
    kindle_docs = find_kindle_docs()
    if not kindle_docs:
        icon.notify(
            f'{len(queue)} article(s) queued — connect your Kindle via USB.',
            'KindleFeeder'
        )
        return
    sent = flush_queue()
    remaining = len(load_queue())
    if sent:
        msg = f'Sent {sent} article(s) to Kindle.'
        if remaining:
            msg += f' {remaining} still queued.'
        icon.notify(msg, 'KindleFeeder')
    else:
        icon.notify('Nothing new to send.', 'KindleFeeder')


def on_quit(icon, item):
    log('Tray stopped by user')
    icon._running = False
    icon.stop()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    # Prevent duplicate instances
    mutex = ctypes.windll.kernel32.CreateMutexW(None, True, 'KindleFeederTrayMutex')
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        sys.exit(0)

    queue_count = len(load_queue())
    status_label = f'KindleFeeder — {queue_count} queued' if queue_count else 'KindleFeeder — Running'

    menu = pystray.Menu(
        pystray.MenuItem(status_label, None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Check Kindle Now', on_check_now),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Quit', on_quit),
    )

    icon = pystray.Icon(
        'kindlefeeder',
        make_icon('#22c55e'),
        'KindleFeeder',
        menu
    )
    icon._running = True

    thread = threading.Thread(target=poll_loop, args=(icon,), daemon=True)
    thread.start()

    icon.run()


if __name__ == '__main__':
    main()
