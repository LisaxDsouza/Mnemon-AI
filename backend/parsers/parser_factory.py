import os
import urllib.parse
import PyPDF2
from youtube_transcript_api import YouTubeTranscriptApi
from typing import List, Dict, Any

from .base_parser import BaseParser
from .generic_parser import GenericParser
from .stackoverflow_parser import StackOverflowParser
from .github_parser import GitHubParser

# --- YouTube, PDF, and Search Engine Parsers as BaseParser Subclasses ---

class YouTubeParser(BaseParser):
    def fetch(self, url: str) -> str:
        return url  # No HTML fetch needed

    def parse(self, url: str, html: str) -> List[Dict[str, Any]]:
        video_id = None
        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.hostname in ('youtu.be', 'www.youtu.be'):
            video_id = parsed_url.path[1:]
        elif parsed_url.hostname in ('youtube.com', 'www.youtube.com'):
            if parsed_url.path == '/watch':
                p = urllib.parse.parse_qs(parsed_url.query)
                video_id = p.get('v', [None])[0]
            elif parsed_url.path.startswith('/embed/'):
                video_id = parsed_url.path.split('/')[2]
            elif parsed_url.path.startswith('/v/'):
                video_id = parsed_url.path.split('/')[2]
                
        if not video_id:
            return []
            
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            text_content = []
            current_segment = []
            current_word_count = 0
            start_time = 0
            
            for entry in transcript_list:
                text = entry['text']
                if current_word_count == 0:
                    start_time = int(entry['start'])
                current_segment.append(text)
                current_word_count += len(text.split())
                
                if current_word_count > 120:
                    mins, secs = divmod(start_time, 60)
                    timestamp_str = f"{mins:02d}:{secs:02d}"
                    text_content.append({
                        "text": " ".join(current_segment),
                        "metadata": {"location": f"Timestamp {timestamp_str}"}
                    })
                    current_segment = []
                    current_word_count = 0
                    
            if current_segment:
                mins, secs = divmod(start_time, 60)
                timestamp_str = f"{mins:02d}:{secs:02d}"
                text_content.append({
                    "text": " ".join(current_segment),
                    "metadata": {"location": f"Timestamp {timestamp_str}"}
                })
            return text_content
        except Exception as e:
            print(f"Parser: YouTube transcript fetch failed for {video_id}: {e}")
            return [{
                "text": f"YouTube Video (ID: {video_id}) was tracked. Transcription was offline or disabled. This placeholder acts as a semantic anchor for video learning at this URL.",
                "metadata": {"location": "Video Summary"}
            }]

class PDFParser(BaseParser):
    def fetch(self, url: str) -> str:
        return url  # Local file path

    def parse(self, url: str, html: str) -> List[Dict[str, Any]]:
        text_content = []
        if not os.path.exists(url) or os.path.getsize(url) == 0:
            return []
        try:
            with open(url, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                if reader.is_encrypted:
                    return []
                for i, page in enumerate(reader.pages):
                    text = page.extract_text()
                    if text and text.strip():
                        text_content.append({
                            "text": text,
                            "metadata": {"location": f"Page {i+1}"}
                        })
        except Exception as e:
            print(f"Parser: Error parsing PDF {url}: {e}")
        return text_content

class SearchParser(BaseParser):
    def fetch(self, url: str) -> str:
        return url

    def parse(self, url: str, html: str) -> List[Dict[str, Any]]:
        parsed_url = urllib.parse.urlparse(url)
        query = ""
        engine = "Search Engine"
        
        if "google" in parsed_url.netloc:
            p = urllib.parse.parse_qs(parsed_url.query)
            query = p.get('q', [None])[0]
            engine = "Google Search"
        elif "bing" in parsed_url.netloc:
            p = urllib.parse.parse_qs(parsed_url.query)
            query = p.get('q', [None])[0]
            engine = "Bing Search"
        elif "yahoo" in parsed_url.netloc:
            p = urllib.parse.parse_qs(parsed_url.query)
            query = p.get('p', [None])[0]
            engine = "Yahoo Search"
            
        if query:
            return [{
                "text": f"User executed a search query: '{query}' on {engine}. This indicates search intent for learning or research.",
                "metadata": {"location": engine, "search_query": query}
            }]
        return []

# --- Factory Routing Engine ---

def get_parser(url: str) -> BaseParser:
    """Routes target URLs to the correct BaseParser implementation class."""
    if url.lower().endswith('.pdf'):
        return PDFParser()
        
    parsed_url = urllib.parse.urlparse(url)
    netloc = parsed_url.netloc.lower()
    path = parsed_url.path.lower()
    
    if "youtube.com" in netloc or "youtu.be" in netloc:
        return YouTubeParser()
    elif "github.com" in netloc:
        return GitHubParser()
    elif "google.com" in netloc and "/search" in path:
        return SearchParser()
    elif "bing.com" in netloc and "/search" in path:
        return SearchParser()
    elif "stackoverflow.com" in netloc:
        return StackOverflowParser()
    else:
        return GenericParser()
