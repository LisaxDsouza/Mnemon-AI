import re
import requests
from typing import List, Dict, Any
from .base_parser import BaseParser

class GitHubParser(BaseParser):
    def parse(self, url: str, html: str) -> List[Dict[str, Any]]:
        """Parses GitHub repository URLs: extracts metadata, file structure, README sections and code snippets."""
        match = re.match(r"https?://(?:www\.)?github\.com/([^/]+)/([^/]+)", url)
        if not match:
            return []
        owner, repo = match.group(1), match.group(2).split('/')[0]
        
        text_content = []
        
        # 1. Fetch Repository Metadata
        try:
            meta_response = requests.get(f"https://api.github.com/repos/{owner}/{repo}", timeout=10)
            if meta_response.status_code == 200:
                data = meta_response.json()
                meta_text = (
                    f"GitHub Repository: {data.get('full_name')}\n"
                    f"Description: {data.get('description')}\n"
                    f"Language: {data.get('language')}\n"
                    f"Stars: {data.get('stargazers_count')} | Forks: {data.get('forks_count')}\n"
                    f"Open Issues: {data.get('open_issues_count')}"
                )
                text_content.append({
                    "text": meta_text,
                    "metadata": {
                        "location": "Repo Metadata",
                        "repo_name": data.get('full_name'),
                        "stars": data.get('stargazers_count'),
                        "language": data.get('language')
                    }
                })
        except Exception as e:
            print(f"GitHubParser: Metadata API failed: {e}")
            
        # 2. Fetch File Structure
        try:
            contents_response = requests.get(f"https://api.github.com/repos/{owner}/{repo}/contents", timeout=10)
            if contents_response.status_code == 200:
                contents = contents_response.json()
                file_list = []
                for item in contents:
                    type_str = "[DIR]" if item.get("type") == "dir" else "[FILE]"
                    file_list.append(f"{type_str} {item.get('name')}")
                structure_text = f"Repository File Structure (Root):\n" + "\n".join(file_list)
                text_content.append({
                    "text": structure_text,
                    "metadata": {"location": "File Structure"}
                })
        except Exception as e:
            print(f"GitHubParser: Contents API failed: {e}")
            
        # 3. Fetch README
        api_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
        headers = {"Accept": "application/vnd.github.raw+json"}
        has_readme = False
        try:
            response = requests.get(api_url, headers=headers, timeout=10)
            if response.status_code == 200:
                has_readme = True
                readme_text = response.text
                
                # Split README by headers
                sections = re.split(r"(^#+\s+.*$)", readme_text, flags=re.MULTILINE)
                current_section = "Repository Readme"
                for section in sections:
                    if not section.strip():
                        continue
                    if section.startswith('#'):
                        current_section = self.clean(section.strip('#'))
                    else:
                        text_content.extend(self._extract_markdown_and_code(section, f"Readme - {current_section}"))
        except Exception as e:
            print(f"GitHubParser: Readme fetch failed: {e}")
            
        # Fall back to generic scraping if README was not retrieved
        if not has_readme:
            if not html:
                html = self.fetch(url)
            if html:
                from .generic_parser import GenericParser
                text_content.extend(GenericParser().parse(url, html))
                
        return text_content

    def _extract_markdown_and_code(self, section_text: str, location_name: str) -> List[Dict[str, Any]]:
        """Splits text content from markdown code blocks and registers code blocks separately."""
        extracted = []
        code_blocks = re.findall(r"```(.*?)\n(.*?)```", section_text, re.DOTALL)
        
        # Clean text
        clean_text = re.sub(r"```.*?```", "", section_text, flags=re.DOTALL).strip()
        if clean_text:
            extracted.append({
                "text": clean_text,
                "metadata": {"location": location_name}
            })
            
        for lang, code in code_blocks:
            if code.strip():
                extracted.append({
                    "text": f"Code Snippet ({lang.strip() or 'plaintext'}):\n```\n{code.strip()}\n```",
                    "metadata": {"location": f"{location_name} - Code"}
                })
        return extracted
