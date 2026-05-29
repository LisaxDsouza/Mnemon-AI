// Keep track of scroll depth
let maxScrollDepth = 0;

function calculateScrollDepth() {
  const scrollTop = window.scrollY || document.documentElement.scrollTop;
  const windowHeight = window.innerHeight;
  const docHeight = document.documentElement.scrollHeight - windowHeight;
  
  if (docHeight <= 0) return 100; // Single page with no scrolling
  
  const scrollPercent = Math.round((scrollTop / docHeight) * 100);
  return Math.min(Math.max(scrollPercent, 0), 100);
}

// Listen to scroll events
window.addEventListener("scroll", () => {
  const currentDepth = calculateScrollDepth();
  if (currentDepth > maxScrollDepth) {
    maxScrollDepth = currentDepth;
  }
});

// Periodic ping to background script if the page is visible
setInterval(() => {
  if (document.visibilityState === "visible") {
    const currentDepth = calculateScrollDepth();
    if (currentDepth > maxScrollDepth) {
      maxScrollDepth = currentDepth;
    }
    
    chrome.runtime.sendMessage({
      type: "ENGAGEMENT_PING",
      scrollDepth: maxScrollDepth
    }, (response) => {
      if (chrome.runtime.lastError) {
        // Suppress runtime channel errors when background is sleeping
        return;
      }
      if (response && response.status === "extracting") {
        console.log("Recall AI: Page has crossed extraction threshold!");
      }
    });
  }
}, 5000); // Send engagement data every 5 seconds
