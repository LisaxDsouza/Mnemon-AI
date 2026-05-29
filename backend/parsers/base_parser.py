import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any

class BaseParser:
    def fetch(self, url: str) -> str:
        """Fetches the HTML content of the page. Falls back to Playwright if challenged or empty."""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        try:
            response = requests.get(url, timeout=10, headers=headers, allow_redirects=True)
            if response.status_code == 200:
                html = response.text
                if not ("Just a moment..." in html or "Attention Required!" in html or "cloudflare" in html.lower()):
                    return html
        except Exception as e:
            print(f"BaseParser: Static fetch failed/timed out for {url}: {e}")
            
        return self._fetch_playwright(url)

    def _fetch_playwright(self, url: str) -> str:
        from playwright.sync_api import sync_playwright
        try:
            print(f"BaseParser: Launching Playwright to scrape {url}...")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                page = context.new_page()
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)
                html = page.content()
                browser.close()
                return html
        except Exception as e:
            print(f"BaseParser: Playwright fetching failed for {url}: {e}")
            return ""

    def parse(self, url: str, html: str) -> List[Dict[str, Any]]:
        """Parses the HTML and returns a standardized list of dicts: [{'text': str, 'metadata': dict}]"""
        raise NotImplementedError

    def clean(self, text: str) -> str:
        """Cleans extracted text strings."""
        if not text:
            return ""
        return text.strip()
