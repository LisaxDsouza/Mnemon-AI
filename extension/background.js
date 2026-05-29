const BACKEND_URL = "http://localhost:8000";
let runtimeConfig = {
  privacy_mode: "balanced",
  capture_enabled: true,
  blocked_domains: [],
  allowed_categories: {},
  capture_thresholds: { min_time_seconds: 20, min_scroll_depth: 40 }
};

// Map of tabId -> active capture eventId
let activeCaptures = {};

// Map of tabId -> page start timestamp (to track active duration)
let tabStartTimes = {};

// Fetch config from backend
async function fetchConfig() {
  try {
    const response = await fetch(`${BACKEND_URL}/runtime-config`);
    if (response.ok) {
      runtimeConfig = await response.json();
      console.log("Recall AI: Updated runtime config", runtimeConfig);
    }
  } catch (error) {
    console.error("Recall AI: Failed to fetch configuration", error);
  }
}

// Check configuration on startup and periodically
fetchConfig();
setInterval(fetchConfig, 10000);

// Helper: Check if domain is blocked
function isDomainBlocked(url) {
  if (!url) return true;
  try {
    const parsedUrl = new URL(url);
    const domain = parsedUrl.hostname.toLowerCase();
    
    // Check local copy of blocked domains
    for (const blocked of runtimeConfig.blocked_domains) {
      if (domain === blocked.toLowerCase() || domain.endsWith("." + blocked.toLowerCase())) {
        return true;
      }
    }
  } catch (e) {
    return true;
  }
  return false;
}

// Track tab updates (navigations)
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url && tab.url.startsWith('http')) {
    // Reset timers
    tabStartTimes[tabId] = Date.now();
    delete activeCaptures[tabId];
    
    // Check blocklist
    if (!runtimeConfig.capture_enabled) {
      console.log("Recall AI: Capture is paused.");
      return;
    }
    if (isDomainBlocked(tab.url)) {
      console.log("Recall AI: Domain is blocked.", tab.url);
      return;
    }
    
    // Trigger Capture API on backend
    fetch(`${BACKEND_URL}/capture`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: tab.url,
        title: tab.title || "Untitled",
        tab_id: tabId
      })
    })
    .then(res => res.json())
    .then(data => {
      if (data.status === "accepted" && data.event_id) {
        activeCaptures[tabId] = data.event_id;
        console.log(`Recall AI: Capture candidate active for tab ${tabId}: ${data.event_id}`);
      } else {
        console.log("Recall AI: Capture rejected/ignored:", data.reason || data.status);
      }
    })
    .catch(err => console.error("Recall AI: Capture post failed", err));
  }
});

// Clean up tab tracking on close
chrome.tabs.onRemoved.addListener((tabId) => {
  delete activeCaptures[tabId];
  delete tabStartTimes[tabId];
});

// Receive engagement messages from content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "ENGAGEMENT_PING" && sender.tab) {
    const tabId = sender.tab.id;
    const eventId = activeCaptures[tabId];
    
    if (!eventId) {
      sendResponse({ status: "not_captured" });
      return;
    }
    
    // Calculate duration in seconds
    const startTime = tabStartTimes[tabId] || Date.now();
    const duration = Math.floor((Date.now() - startTime) / 1000);
    
    // Send to backend /engagement API
    fetch(`${BACKEND_URL}/engagement`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tab_id: tabId,
        duration: duration,
        scroll_depth: message.scrollDepth
      })
    })
    .then(res => res.json())
    .then(data => {
      console.log(`Recall AI: Tab ${tabId} engagement tracked: status=${data.status}, score=${data.score}`);
      sendResponse({ status: data.status, score: data.score });
    })
    .catch(err => {
      console.error("Recall AI: Failed to submit engagement metrics", err);
      sendResponse({ status: "error" });
    });
    
    return true; // Keep message channel open for async response
  }
  
  // Handle messages from the popup config panel
  if (message.type === "GET_POPUP_STATE") {
    sendResponse({
      config: runtimeConfig,
      activeCaptures: activeCaptures
    });
  }
  
  if (message.type === "REFRESH_CONFIG") {
    fetchConfig().then(() => sendResponse({ status: "refreshed", config: runtimeConfig }));
    return true;
  }
});
