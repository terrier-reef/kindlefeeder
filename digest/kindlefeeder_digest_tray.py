"""
KindleFeeder Digest Tray — separate from the Kindle-sync tray.
Blue icon. Runs kindlefeeder_digest.py daily at a configured time.
Settings UI via tkinter (no extra install needed).
"""

import sys
import os
import json
import ctypes
import threading
import subprocess
import webbrowser
import datetime
from pathlib import Path

import pystray
from PIL import Image, ImageDraw
import tkinter as tk
from tkinter import ttk, scrolledtext

# ── Paths ─────────────────────────────────────────────────────────────────────

APP_DATA = Path(os.environ.get('APPDATA', Path.home())) / 'KindleFeeder'
SETTINGS_JSON = APP_DATA / 'digest_settings.json'
LOG_FILE = APP_DATA / 'digest.log'
DIGEST_SCRIPT = Path(__file__).parent / 'kindlefeeder_digest.py'

DEFAULT_SETTINGS = {
    'api_key': '',
    'run_time': '06:00',
    'sources': {
        'NYTimes Opinion': True,
        'Guardian Opinion': True,
        'BBC': True,
        'LiveMint Opinion': True,
    },
}

# ── Settings persistence ──────────────────────────────────────────────────────

def load_settings():
    if SETTINGS_JSON.exists():
        try:
            s = json.loads(SETTINGS_JSON.read_text(encoding='utf-8'))
            merged = {**DEFAULT_SETTINGS, **s}
            merged['sources'] = {**DEFAULT_SETTINGS['sources'], **s.get('sources', {})}
            return merged
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)


def save_settings(s):
    APP_DATA.mkdir(parents=True, exist_ok=True)
    SETTINGS_JSON.write_text(json.dumps(s, indent=2), encoding='utf-8')

# ── Tray icon (blue circle) ───────────────────────────────────────────────────

def make_icon(color='#3b82f6'):
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill=color)
    return img

# ── Daily scheduler ───────────────────────────────────────────────────────────

_scheduler_timer = None


def _seconds_until(time_str):
    """Seconds until next occurrence of HH:MM."""
    now = datetime.datetime.now()
    h, m = map(int, time_str.split(':'))
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if target <= now:
        target += datetime.timedelta(days=1)
    return (target - now).total_seconds()


def schedule_daily(icon):
    global _scheduler_timer
    settings = load_settings()
    run_time = settings.get('run_time', '06:00')
    delay = _seconds_until(run_time)

    def fire():
        run_digest(icon)
        schedule_daily(icon)  # reschedule for next day

    _scheduler_timer = threading.Timer(delay, fire)
    _scheduler_timer.daemon = True
    _scheduler_timer.start()

# ── Run digest ────────────────────────────────────────────────────────────────

def run_digest(icon, output_widget=None):
    settings = load_settings()
    env = {**os.environ, 'ANTHROPIC_API_KEY': settings.get('api_key', '')}

    def _run():
        try:
            proc = subprocess.Popen(
                [sys.executable, str(DIGEST_SCRIPT)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            for line in proc.stdout:
                line = line.rstrip()
                if output_widget:
                    output_widget.after(0, _append, output_widget, line)
            proc.wait()
            if proc.returncode == 0:
                icon.notify('Daily digest queued for Kindle.', 'KindleFeeder Digest')
            else:
                icon.notify('Digest run failed — check the log.', 'KindleFeeder Digest')
        except Exception as e:
            if output_widget:
                output_widget.after(0, _append, output_widget, f'ERROR: {e}')

    threading.Thread(target=_run, daemon=True).start()


def _append(widget, text):
    widget.config(state='normal')
    widget.insert('end', text + '\n')
    widget.see('end')
    widget.config(state='disabled')

# ── Settings window ───────────────────────────────────────────────────────────

_settings_window = None


def open_settings(icon):
    global _settings_window
    if _settings_window and _settings_window.winfo_exists():
        _settings_window.lift()
        return

    settings = load_settings()
    win = tk.Tk()
    win.title('KindleFeeder — Digest Settings')
    win.resizable(False, False)
    win.configure(bg='#1a1a2e')
    _settings_window = win

    PAD = {'padx': 12, 'pady': 6}
    LABEL_FG = '#e0e0e0'
    ENTRY_BG = '#16213e'
    BTN_BG = '#3b82f6'

    # ── API key ───────────────────────────────────────────────────────────────
    tk.Label(win, text='Anthropic API Key', bg='#1a1a2e', fg=LABEL_FG).grid(
        row=0, column=0, sticky='w', **PAD)
    api_frame = tk.Frame(win, bg='#1a1a2e')
    api_frame.grid(row=0, column=1, columnspan=2, sticky='ew', **PAD)
    api_var = tk.StringVar(value=settings.get('api_key', ''))
    api_entry = tk.Entry(api_frame, textvariable=api_var, show='●',
                         bg=ENTRY_BG, fg=LABEL_FG, insertbackground=LABEL_FG, width=32)
    api_entry.pack(side='left')
    tk.Button(api_frame, text='?', bg=BTN_BG, fg='white', relief='flat',
              command=lambda: webbrowser.open('https://console.anthropic.com/')).pack(
        side='left', padx=4)

    # ── Run time ──────────────────────────────────────────────────────────────
    tk.Label(win, text='Daily run time (HH:MM)', bg='#1a1a2e', fg=LABEL_FG).grid(
        row=1, column=0, sticky='w', **PAD)
    time_var = tk.StringVar(value=settings.get('run_time', '06:00'))
    tk.Entry(win, textvariable=time_var, bg=ENTRY_BG, fg=LABEL_FG,
             insertbackground=LABEL_FG, width=8).grid(row=1, column=1, sticky='w', **PAD)

    # ── Sources ───────────────────────────────────────────────────────────────
    tk.Label(win, text='Sources', bg='#1a1a2e', fg=LABEL_FG).grid(
        row=2, column=0, sticky='nw', **PAD)
    src_frame = tk.Frame(win, bg='#1a1a2e')
    src_frame.grid(row=2, column=1, sticky='w', **PAD)
    src_vars = {}
    for i, (src, enabled) in enumerate(settings['sources'].items()):
        var = tk.BooleanVar(value=enabled)
        tk.Checkbutton(src_frame, text=src, variable=var,
                       bg='#1a1a2e', fg=LABEL_FG, selectcolor='#0f3460',
                       activebackground='#1a1a2e', activeforeground=LABEL_FG).grid(
            row=i, column=0, sticky='w')
        src_vars[src] = var

    # ── Separator ─────────────────────────────────────────────────────────────
    ttk.Separator(win, orient='horizontal').grid(
        row=3, column=0, columnspan=3, sticky='ew', pady=4)

    # ── Last run status ───────────────────────────────────────────────────────
    last_run = '—'
    if LOG_FILE.exists():
        try:
            lines = LOG_FILE.read_text(encoding='utf-8', errors='ignore').splitlines()
            for line in reversed(lines):
                if 'Done.' in line or 'ERROR' in line:
                    last_run = line[-80:]
                    break
        except Exception:
            pass
    tk.Label(win, text=f'Last run: {last_run}', bg='#1a1a2e', fg='#888',
             wraplength=360, justify='left').grid(
        row=4, column=0, columnspan=3, sticky='w', **PAD)
    tk.Button(win, text='View Log', bg='#16213e', fg=LABEL_FG, relief='flat',
              command=lambda: os.startfile(str(LOG_FILE)) if LOG_FILE.exists() else None
              ).grid(row=5, column=0, sticky='w', **PAD)

    # ── Log output panel ──────────────────────────────────────────────────────
    ttk.Separator(win, orient='horizontal').grid(
        row=6, column=0, columnspan=3, sticky='ew', pady=4)
    log_box = scrolledtext.ScrolledText(win, width=52, height=10,
                                        bg='#0a0a1a', fg='#74c69d',
                                        state='disabled', font=('Consolas', 9))
    log_box.grid(row=7, column=0, columnspan=3, padx=12, pady=4)

    # ── Buttons ───────────────────────────────────────────────────────────────
    btn_frame = tk.Frame(win, bg='#1a1a2e')
    btn_frame.grid(row=8, column=0, columnspan=3, pady=10)

    def on_run_now():
        run_digest(icon, output_widget=log_box)

    def on_save():
        s = {
            'api_key': api_var.get().strip(),
            'run_time': time_var.get().strip() or '06:00',
            'sources': {k: v.get() for k, v in src_vars.items()},
        }
        save_settings(s)
        # reschedule with new time
        if _scheduler_timer:
            _scheduler_timer.cancel()
        schedule_daily(icon)
        win.destroy()

    tk.Button(btn_frame, text='Run Now', bg='#22c55e', fg='white', relief='flat',
              padx=16, pady=6, command=on_run_now).pack(side='left', padx=8)
    tk.Button(btn_frame, text='Save & Close', bg=BTN_BG, fg='white', relief='flat',
              padx=16, pady=6, command=on_save).pack(side='left', padx=8)

    win.mainloop()

# ── Tray menu ─────────────────────────────────────────────────────────────────

def on_run_now(icon, item):
    run_digest(icon)


def on_settings(icon, item):
    threading.Thread(target=open_settings, args=(icon,), daemon=True).start()


def on_quit(icon, item):
    if _scheduler_timer:
        _scheduler_timer.cancel()
    icon.stop()

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    # Single-instance guard
    mutex = ctypes.windll.kernel32.CreateMutexW(None, True, 'KindleFeederDigestTrayMutex')
    if ctypes.windll.kernel32.GetLastError() == 183:
        sys.exit(0)

    menu = pystray.Menu(
        pystray.MenuItem('KindleFeeder Digest', None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Run Now', on_run_now),
        pystray.MenuItem('Digest Settings', on_settings),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Quit', on_quit),
    )

    icon = pystray.Icon('kindlefeeder_digest', make_icon('#3b82f6'),
                        'KindleFeeder Digest', menu)

    schedule_daily(icon)
    icon.run()


if __name__ == '__main__':
    main()
