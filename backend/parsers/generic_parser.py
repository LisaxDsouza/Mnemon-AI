from bs4 import BeautifulSoup
from typing import List, Dict, Any
from .base_parser import BaseParser

class GenericParser(BaseParser):
    def parse(self, url: str, html: str) -> List[Dict[str, Any]]:
        """Extracts meaningful paragraphs and sections from generic webpages/blogs."""
        if not html:
            return []
        soup = BeautifulSoup(html, 'html.parser')
        
        # Strip script, style, navigation, footer, header, aside
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()
            
        text_content = []
        current_section = "General Overview"
        
        for element in soup.find_all(['h1', 'h2', 'h3', 'p', 'li']):
            text = self.clean(element.get_text())
            if not text:
                continue
                
            if element.name.startswith('h'):
                current_section = text
                
            text_content.append({
                "text": text,
                "metadata": {"location": f"Section: {current_section}"}
            })
            
        return text_content
