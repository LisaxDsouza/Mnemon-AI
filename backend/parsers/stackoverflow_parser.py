from bs4 import BeautifulSoup
from typing import List, Dict, Any
from .base_parser import BaseParser

class StackOverflowParser(BaseParser):
    def parse(self, url: str, html: str) -> List[Dict[str, Any]]:
        """Parses StackOverflow pages: extracts question title, body, tags, comments, answers and code snippets."""
        if not html:
            return []
        soup = BeautifulSoup(html, 'html.parser')
        
        # 1. Title and tags extraction
        title_elem = soup.find('h1', id='question-header') or soup.find(class_='question-hyperlink')
        title = self.clean(title_elem.get_text()) if title_elem else "StackOverflow Question"
        tags = [self.clean(tag.get_text()) for tag in soup.find_all('a', class_='post-tag')]
        tags_str = ", ".join(tags) if tags else "None"
        
        text_content = []
        text_content.append({
            "text": f"StackOverflow Question: {title}\nTags: {tags_str}",
            "metadata": {"location": "Question Title", "tags": tags}
        })
        
        # 2. Question Body & Comments
        question_post = soup.find('div', class_='question')
        if question_post:
            body_elem = question_post.find('div', class_='js-post-body')
            if body_elem:
                text_content.extend(self._extract_body_and_code(body_elem, "Question Body"))
            
            # Extract question comments
            comments_container = question_post.find('div', class_='comments')
            if comments_container:
                q_comments = []
                for comment in comments_container.find_all('span', class_='comment-copy'):
                    comm_text = self.clean(comment.get_text())
                    if comm_text:
                        q_comments.append(comm_text)
                if q_comments:
                    text_content.append({
                        "text": "Question Comments:\n" + "\n".join(f"- {c}" for c in q_comments),
                        "metadata": {"location": "Question Comments"}
                    })
                
        # 3. Answers & Answer Comments
        answers = soup.find_all('div', class_='answer')
        for i, answer in enumerate(answers):
            is_accepted = "accepted-answer" in answer.get('class', [])
            vote_elem = answer.find('div', class_='js-vote-count')
            score = self.clean(vote_elem.get_text()) if vote_elem else "0"
            
            body_elem = answer.find('div', class_='js-post-body')
            if body_elem:
                loc_name = f"Answer {i+1}{' (Accepted)' if is_accepted else ''} [Score: {score}]"
                text_content.extend(self._extract_body_and_code(body_elem, loc_name))
                
            # Extract answer comments
            comments_container = answer.find('div', class_='comments')
            if comments_container:
                a_comments = []
                for comment in comments_container.find_all('span', class_='comment-copy'):
                    comm_text = self.clean(comment.get_text())
                    if comm_text:
                        a_comments.append(comm_text)
                if a_comments:
                    text_content.append({
                        "text": f"Answer {i+1} Comments:\n" + "\n".join(f"- {c}" for c in a_comments),
                        "metadata": {"location": f"Answer {i+1} Comments"}
                    })
                
        return text_content

    def _extract_body_and_code(self, body_elem, location_name: str) -> List[Dict[str, Any]]:
        """Helper to extract paragraphs, lists, and pre/code blocks separately."""
        extracted = []
        for child in body_elem.find_all(['p', 'pre', 'ul', 'ol', 'h2', 'h3']):
            if child.name == 'pre':
                code_elem = child.find('code')
                if code_elem:
                    code_text = code_elem.get_text()
                    if code_text.strip():
                        extracted.append({
                            "text": f"Code Snippet:\n```\n{code_text.strip()}\n```",
                            "metadata": {"location": f"{location_name} - Code"}
                        })
            else:
                text = self.clean(child.get_text())
                if text:
                    extracted.append({
                        "text": text,
                        "metadata": {"location": location_name}
                    })
        return extracted
