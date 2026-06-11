# KindleFeeder

Send any web article to your Kindle (2011 / Kindle 3) in one click.

## How it works

1. You're on any article page in Chrome
2. Click the KindleFeeder toolbar icon → **Send to Kindle**
3. The extension extracts the article using Mozilla Readability (same as Firefox Reader View)
4. A native helper converts it to MOBI6 using Calibre
5. The MOBI is copied to your Kindle's `documents/` folder over USB

If your Kindle isn't connected, the article is **queued** and automatically sent the next time you plug in.

---

## Setup (one time)

### 1. Install Python
Download from https://www.python.org/downloads/ — check **"Add Python to PATH"** during install.

### 2. Install Calibre
Download from https://calibre-ebook.com/download_windows — use the default install path.

### 3. Run the installer
Double-click **`install.bat`** — no admin rights needed.

### 4. Load the Chrome extension
1. Open Chrome → go to `chrome://extensions`
2. Enable **Developer mode** (toggle, top right)
3. Click **Load unpacked** → select `C:\KindleFeeder\extension`
4. Note the **Extension ID** (a long string of letters shown under the extension name)

### 5. Update the native messaging manifest
Open `C:\KindleFeeder\host\com.kindlefeeder.host.json` in Notepad and replace `REPLACE_WITH_YOUR_EXTENSION_ID` with your actual Extension ID. Save the file, then re-run `install.bat` (or just re-run the `reg add` line in it).

---

## Usage

- Navigate to any article (BBC, Guardian, NYT, WashPost, etc.)
- Click the 📚 icon in the Chrome toolbar
- Click **Send to Kindle**

### Kindle not detected?

- Make sure the Kindle screen is **unlocked** before plugging in via USB
- Windows 10/11 must mount it as a **drive letter** (not MTP). If it mounts as a camera/MTP device:
  - On the Kindle, go to **Settings → USB Mode → Store** (or drag down the notification bar and tap the USB mode option)
- Try a different USB cable (some cables are charge-only)

### Queue

If the Kindle isn't connected when you send, the article is saved locally. The extension checks for your Kindle every 30 seconds and copies queued articles automatically. A badge on the extension icon shows the queue count.

---

## Supported sites

| Site | Notes |
|------|-------|
| BBC News | Works; fallback extraction if Shadow DOM issues |
| The Guardian | Works; article images may be stripped |
| NY Times | Works when logged in or within free article limit |
| Washington Post | Works |
| WSJ | Requires active subscription (full article must load in browser) |
| Most article sites | Works with Readability's automatic extraction |

---

## Troubleshooting

**"Native host not responding"** — Run `install.bat` again. Make sure Python is in your PATH.

**"Calibre not found"** — Install Calibre from the link shown in the extension popup.

**Blank or very short article** — The page may be behind a paywall or using heavy JavaScript. Try pressing **F9** (Reader View in Firefox) to verify the article is extractable, or check you're logged in.

**Windows Defender / SmartScreen** — The `.bat` file may trigger a SmartScreen warning. Click "More info" → "Run anyway". This is a false positive from unsigned scripts.
