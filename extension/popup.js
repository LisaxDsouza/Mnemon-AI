const BACKEND_URL = "http://localhost:8000";
let activeTab = null;
let activeDomain = "";
let isCurrentDomainBlocked = false;
let blockId = null;

// On popup loaded
document.addEventListener("DOMContentLoaded", async () => {
  // 1. Get active tab
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs && tabs.length > 0) {
      activeTab = tabs[0];
      document.getElementById("pageTitle").textContent = activeTab.title || "Unknown Tab";
      
      try {
        const urlObj = new URL(activeTab.url);
        activeDomain = urlObj.hostname;
        document.getElementById("pageDomain").textContent = activeDomain;
        
        // Update popup display
        updatePopupState();
      } catch (e) {
        document.getElementById("pageTitle").textContent = "Browser Native Tab";
        document.getElementById("pageDomain").textContent = "Non-capture URL";
        document.getElementById("blockToggleBtn").style.display = "none";
        setStatus("Blocked", "status-blocked");
      }
    }
  });

  // 2. Setup button listeners
  document.getElementById("blockToggleBtn").addEventListener("click", toggleDomainBlock);
  document.getElementById("pause10Btn").addEventListener("click", () => pauseCapture(10));
  document.getElementById("pause60Btn").addEventListener("click", () => pauseCapture(60));
  document.getElementById("dashboardBtn").addEventListener("click", () => {
    chrome.tabs.create({ url: "http://localhost:3000" });
  });
  document.getElementById("viewPrefs").addEventListener("click", () => {
    chrome.tabs.create({ url: "http://localhost:3000/privacy" });
  });
});

function setStatus(text, className) {
  const badge = document.getElementById("statusBadge");
  badge.className = "status-badge " + className;
  document.getElementById("statusText").textContent = text;
}

async function updatePopupState() {
  if (!activeDomain) return;
  
  try {
    // Fetch state from background worker
    chrome.runtime.sendMessage({ type: "GET_POPUP_STATE" }, async (response) => {
      if (!response) return;
      
      const config = response.config;
      
      // Check pause state
      if (!config.capture_enabled) {
        setStatus("Paused", "status-paused");
        document.getElementById("blockToggleBtn").disabled = true;
        return;
      }
      
      // Fetch user's custom blocked list to match active domain ID
      const blockedRes = await fetch(`${BACKEND_URL}/privacy/blocked-domains`);
      const blockedList = await blockedRes.json();
      
      const matchedBlock = blockedList.find(b => 
        activeDomain === b.domain || activeDomain.endsWith("." + b.domain)
      );
      
      if (matchedBlock) {
        isCurrentDomainBlocked = true;
        blockId = matchedBlock.id;
        document.getElementById("blockToggleBtn").textContent = "Unblock Domain";
        document.getElementById("blockToggleBtn").className = "btn btn-danger";
        setStatus("Blocked", "status-blocked");
      } else {
        isCurrentDomainBlocked = false;
        blockId = null;
        document.getElementById("blockToggleBtn").textContent = "Block Domain";
        document.getElementById("blockToggleBtn").className = "btn btn-secondary";
        setStatus("Active", "status-active");
      }
    });
  } catch (error) {
    console.error("Popup: Failed to fetch state", error);
  }
}

async function toggleDomainBlock() {
  if (!activeDomain) return;
  
  if (isCurrentDomainBlocked && blockId) {
    // Unblock
    try {
      const res = await fetch(`${BACKEND_URL}/privacy/blocked-domains/${blockId}`, {
        method: "DELETE"
      });
      if (res.ok) {
        chrome.runtime.sendMessage({ type: "REFRESH_CONFIG" }, () => {
          updatePopupState();
        });
      }
    } catch (e) {
      console.error("Popup: Failed to delete blocked domain", e);
    }
  } else {
    // Block
    try {
      const res = await fetch(`${BACKEND_URL}/privacy/blocked-domains`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          domain: activeDomain,
          wildcard: true
        })
      });
      if (res.ok) {
        chrome.runtime.sendMessage({ type: "REFRESH_CONFIG" }, () => {
          updatePopupState();
        });
      }
    } catch (e) {
      console.error("Popup: Failed to create blocked domain", e);
    }
  }
}

async function pauseCapture(minutes) {
  try {
    const res = await fetch(`${BACKEND_URL}/privacy/pause`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        duration_minutes: minutes
      })
    });
    if (res.ok) {
      chrome.runtime.sendMessage({ type: "REFRESH_CONFIG" }, () => {
        updatePopupState();
      });
    }
  } catch (e) {
    console.error("Popup: Failed to pause capture", e);
  }
}
