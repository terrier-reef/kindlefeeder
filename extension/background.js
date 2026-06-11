const HOST_NAME = 'com.kindlefeeder.host';

// ── Native messaging helpers ──────────────────────────────────────────────────

function sendNativeMessage(msg) {
  return new Promise((resolve) => {
    chrome.runtime.sendNativeMessage(HOST_NAME, msg, (response) => {
      if (chrome.runtime.lastError) {
        resolve({ error: chrome.runtime.lastError.message });
      } else {
        resolve(response);
      }
    });
  });
}

// ── Queue badge ───────────────────────────────────────────────────────────────

async function setQueueCount(count) {
  await chrome.storage.local.set({ queueCount: count });
  if (count > 0) {
    chrome.action.setBadgeText({ text: String(count) });
    chrome.action.setBadgeBackgroundColor({ color: '#e94560' });
  } else {
    chrome.action.setBadgeText({ text: '' });
  }
}

// ── Alarm: poll for Kindle every 30 seconds ───────────────────────────────────

chrome.alarms.create('kindlePoller', { periodInMinutes: 0.5 });

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== 'kindlePoller') return;

  const response = await sendNativeMessage({ action: 'flush_queue' });

  if (response && response.flushed && response.flushed.length > 0) {
    await setQueueCount(0);
    const titles = response.flushed.join(', ');
    chrome.notifications.create({
      type: 'basic',
      iconUrl: 'icons/icon48.png',
      title: 'KindleFeeder',
      message: `Sent to Kindle: ${titles}`,
    });
  } else if (response && typeof response.queue_count === 'number') {
    await setQueueCount(response.queue_count);
  }
});

// ── Message handler from popup ────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.action === 'send_to_kindle') {
    const payload = {
      action: 'convert',
      title: msg.article.title,
      author: msg.article.author || '',
      html_content: msg.article.content,
      source_url: msg.sourceUrl || '',
    };

    sendNativeMessage(payload).then(async (response) => {
      if (response && response.status === 'queued') {
        const data = await chrome.storage.local.get('queueCount');
        await setQueueCount((data.queueCount || 0) + 1);
      }
      sendResponse(response);
    });

    return true; // keep channel open for async response
  }

  if (msg.action === 'check_calibre') {
    sendNativeMessage({ action: 'check_calibre' }).then(sendResponse);
    return true;
  }
});
