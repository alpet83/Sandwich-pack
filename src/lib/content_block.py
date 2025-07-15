# /lib/content_block.py, updated 2025-07-15 09:09 EEST
from typing import List, Dict, Optional

class ContentBlock:
    supported_types = [".toml", ".md", ".markdown", ":rules", ""]
    def __init__(self, content_text: str, content_type: str, file_name: Optional[str] = None, timestamp: Optional[str] = None, post_id: Optional[int] = None, chat_id: Optional[int] = None, user_id: Optional[int] = None, relevance: Optional[int] = 0):
        self.content_text = content_text
        self.content_type = content_type
        self.file_name = file_name or f"content_{id(self)}"
        self.timestamp = timestamp or "1970-01-01 00:00:00Z"
        self.length = len(content_text.encode("utf-8"))
        self.tokens = self.length // 4
        self.post_id = post_id
        self.chat_id = chat_id
        self.user_id = user_id
        self.relevance = relevance

    def parse_content(self) -> Dict:
        return {"entities": [], "dependencies": {"modules": [], "imports": [], "calls": []}}

    def to_sandwich_block(self) -> str:
        tag_map = {
            ".rs": "rustc",
            ".vue": "vue",
            ".js": "jss",
            ".py": "python",
            ".toml": "document",
            ".md": "document",
            ".markdown": "document",
            ":post": "post",
            ":rules": "rules"
        }
        tag = tag_map.get(self.content_type, "document")
        attributes = f'src="{self.file_name}" mod_time="{self.timestamp}"'
        if self.content_type == ":post":
            attributes += f' post_id="{self.post_id or 0}" chat_id="{self.chat_id or 0}" user_id="{self.user_id or 0}" relevance="{self.relevance}"'
        return f'<{tag} {attributes}>\n{self.content_text}\n</{tag}>\n'