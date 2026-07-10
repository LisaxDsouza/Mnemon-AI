const BACKEND_URL = "http://localhost:8000";
const DASHBOARD_URL = "http://localhost:3000";

let activeTab = null;
let activeDomain = "";
let isCurrentDomainBlocked = false;
let blockId = null;
let selectedPauseMinutes = 10;

document.addEventListener("DOMContentLoaded", async () => {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs && tabs.length > 0) {
      activeTab = tabs[0];
      document.getElementById("pageTitle").textContent = activeTab.title || "Unknown tab";

      try {
        const urlObj = new URL(activeTab.url);
        activeDomain = urlObj.hostname;
        document.getElementById("pageDomain").textContent = classifySource(activeDomain);
        updatePopupState();
      } catch (e) {
        document.getElementById("pageTitle").textContent = "Browser tab";
        document.getElementById("pageDomain").textContent = "Not tracked";
        document.getElementById("blockToggleBtn").style.display = "none";
        setStatus("Not tracked", "status-blocked");
      }
    }
  });

  document.getElementById("blockToggleBtn").addEventListener("click", toggleDomainBlock);

  document.querySelectorAll(".dur-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".dur-btn").forEach(b => b.classList.remove("sel"));
      btn.classList.add("sel");
      selectedPauseMinutes = parseInt(btn.dataset.min, 10);
    });
  });

  document.getElementById("haltBtn").addEventListener("click", handleHaltToggle);

  document.querySelectorAll(".tg-item").forEach(item => {
    item.addEventListener("click", () => toggleCategory(item.dataset.cat, item));
  });

  document.getElementById("dashboardBtn").addEventListener("click", () => {
    chrome.tabs.create({ url: DASHBOARD_URL });
  });
  document.getElementById("viewPrefs").addEventListener("click", (e) => {
    e.preventDefault();
    chrome.tabs.create({ url: `${DASHBOARD_URL}#privacy` });
  });
});

function classifySource(domain) {
  if (domain.includes("youtube.com")) return "YouTube";
  if (domain.includes("github.com")) return "GitHub";
  if (domain.includes("stackoverflow.com")) return "Stack Overflow";
  return "Article";
}

function setStatus(text, className) {
  const badge = document.getElementById("statusBadge");
  badge.className = "status-badge " + className;
  document.getElementById("statusText").textContent = text;
}

let isPausedGlobal = false;

async function updatePopupState() {
  if (!activeDomain) return;

  try {
    chrome.runtime.sendMessage({ type: "GET_POPUP_STATE" }, async (response) => {
      if (!response) return;

      const config = response.config;
      renderCategories(config.allowed_categories || {});

      const blockedList = config.blocked_domains || [];
      document.getElementById("blockedCount").textContent =
        `${blockedList.length} site${blockedList.length === 1 ? "" : "s"} always excluded`;

      isPausedGlobal = !config.capture_enabled;
      updateHaltButton();

      if (isPausedGlobal) {
        setStatus("Paused", "status-paused");
        document.getElementById("blockToggleBtn").disabled = true;
        return;
      }
      document.getElementById("blockToggleBtn").disabled = false;

      // Fetch full blocked-domain records to resolve the id for this exact domain
      const blockedRes = await fetch(`${BACKEND_URL}/privacy/blocked-domains`);
      const blockedFull = await blockedRes.json();

      const matchedBlock = blockedFull.find(b =>
        activeDomain === b.domain || activeDomain.endsWith("." + b.domain)
      );

      if (matchedBlock) {
        isCurrentDomainBlocked = true;
        blockId = matchedBlock.id;
        document.getElementById("blockToggleBtn").textContent = "Unblock this site";
        document.getElementById("blockToggleBtn").classList.add("is-blocked");
        setStatus("Blocked", "status-blocked");
      } else {
        isCurrentDomainBlocked = false;
        blockId = null;
        document.getElementById("blockToggleBtn").textContent = "Block this site";
        document.getElementById("blockToggleBtn").classList.remove("is-blocked");
        setStatus("Active", "status-active");
      }
    });
  } catch (error) {
    console.error("Popup: Failed to fetch state", error);
  }
}

function renderCategories(allowedCategories) {
  document.querySelectorAll(".tg-item").forEach(item => {
    const cat = item.dataset.cat;
    const enabled = !!allowedCategories[cat];
    item.classList.toggle("on", enabled);
  });
}

function updateHaltButton() {
  const btn = document.getElementById("haltBtn");
  btn.classList.toggle("is-paused", isPausedGlobal);
  btn.textContent = isPausedGlobal ? "Resume capture" : "Pause capture";
}

async function toggleCategory(category, itemEl) {
  const willEnable = !itemEl.classList.contains("on");
  try {
    const res = await fetch(`${BACKEND_URL}/privacy/category-toggle`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category, enabled: willEnable })
    });
    if (res.ok) {
      itemEl.classList.toggle("on", willEnable);
      chrome.runtime.sendMessage({ type: "REFRESH_CONFIG" });
    }
  } catch (e) {
    console.error("Popup: Failed to toggle category", e);
  }
}

async function toggleDomainBlock() {
  if (!activeDomain) return;

  if (isCurrentDomainBlocked && blockId) {
    try {
      const res = await fetch(`${BACKEND_URL}/privacy/blocked-domains/${blockId}`, { method: "DELETE" });
      if (res.ok) {
        chrome.runtime.sendMessage({ type: "REFRESH_CONFIG" }, () => updatePopupState());
      }
    } catch (e) {
      console.error("Popup: Failed to delete blocked domain", e);
    }
  } else {
    try {
      const res = await fetch(`${BACKEND_URL}/privacy/blocked-domains`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domain: activeDomain, wildcard: true })
      });
      if (res.ok) {
        chrome.runtime.sendMessage({ type: "REFRESH_CONFIG" }, () => updatePopupState());
      }
    } catch (e) {
      console.error("Popup: Failed to create blocked domain", e);
    }
  }
}

function handleHaltToggle() {
  pauseCapture(isPausedGlobal ? 0 : selectedPauseMinutes);
}

async function pauseCapture(minutes) {
  try {
    const res = await fetch(`${BACKEND_URL}/privacy/pause`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ duration_minutes: minutes })
    });
    if (res.ok) {
      chrome.runtime.sendMessage({ type: "REFRESH_CONFIG" }, () => updatePopupState());
    }
  } catch (e) {
    console.error("Popup: Failed to pause capture", e);
  }
}
