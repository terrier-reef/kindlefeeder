const sendBtn = document.getElementById('send-btn');
const statusEl = document.getElementById('status');
const queueSection = document.getElementById('queue-section');
const queueCount = document.getElementById('queue-count');
const calibreWarning = document.getElementById('calibre-warning');
const calibreLink = document.getElementById('calibre-link');

function showStatus(msg, type) {
  statusEl.textContent = msg;
  statusEl.className = type;
}

async function updateQueueBadge() {
  const data = await chrome.storage.local.get('queueCount');
  const count = data.queueCount || 0;
  if (count > 0) {
    queueCount.textContent = count;
    queueSection.classList.add('visible');
  } else {
    queueSection.classList.remove('visible');
  }
}

async function checkCalibreStatus() {
  try {
    const response = await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ action: 'check_calibre' }, (resp) => {
        if (chrome.runtime.lastError) reject(chrome.runtime.lastError);
        else resolve(resp);
      });
    });
    if (response && response.calibre_missing) {
      calibreWarning.classList.add('visible');
      calibreLink.href = 'https://calibre-ebook.com/download_windows';
      calibreLink.onclick = (e) => {
        e.preventDefault();
        chrome.tabs.create({ url: 'https://calibre-ebook.com/download_windows' });
      };
    }
  } catch (_) {
    // host not running yet — ignore
  }
}

sendBtn.addEventListener('click', async () => {
  sendBtn.disabled = true;
  showStatus('Extracting article…', 'info');

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    // Inject Readability + content script
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ['lib/Readability.js']
    });

    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ['content_script.js']
    });

    const article = results?.[0]?.result;

    if (!article || !article.title) {
      showStatus('Could not extract article from this page. Try Reader View first (F9).', 'error');
      return;
    }

    showStatus(`Converting "${article.title}"…`, 'info');

    const response = await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        { action: 'send_to_kindle', article, sourceUrl: tab.url },
        (resp) => {
          if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
          else resolve(resp);
        }
      );
    });

    if (!response) {
      showStatus('Native host not responding. Run install.bat first.', 'error');
      return;
    }

    if (response.error === 'calibre_not_found') {
      showStatus('Calibre not found. Install it using the link below.', 'error');
      calibreWarning.classList.add('visible');
      calibreLink.href = 'https://calibre-ebook.com/download_windows';
      calibreLink.onclick = (e) => {
        e.preventDefault();
        chrome.tabs.create({ url: 'https://calibre-ebook.com/download_windows' });
      };
      return;
    }

    if (response.error === 'kindle_not_found' || response.status === 'queued') {
      showStatus(`Queued! "${article.title}" will be sent when Kindle is connected.`, 'queued');
      await updateQueueBadge();
      return;
    }

    if (response.error) {
      showStatus(`Error: ${response.error}`, 'error');
      return;
    }

    if (response.status === 'sent') {
      showStatus(`✓ Sent to Kindle: "${article.title}"`, 'success');
      await updateQueueBadge();
      return;
    }

    showStatus('Unexpected response from host.', 'error');
  } catch (err) {
    showStatus(`Error: ${err.message}`, 'error');
  } finally {
    sendBtn.disabled = false;
  }
});

updateQueueBadge();
checkCalibreStatus();
