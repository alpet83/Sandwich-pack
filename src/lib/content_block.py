# /lib/content_block.py, updated 2025-07-15 15:43 EEST
import logging
from typing import Optional


class ContentBlock:
    supported_types = [':document', ':post']

    def __init__(self, content_text: str, content_type: str, file_name: Optional[str] = None, timestamp: Optional[str] = None, **kwargs):
        self.content_text = content_text
        self.content_type = content_type
        self.tag = "post" if content_type == ":post" else "document"
        self.file_name = file_name
        self.timestamp = timestamp
        self.post_id = kwargs.get('post_id')
        self.user_id = kwargs.get('user_id')
        self.relevance = kwargs.get('relevance', 0)
        self.file_id = kwargs.get('file_id')
        self.tokens = self.estimate_tokens(content_text)
        logging.debug(f"Initialized ContentBlock with content_type={content_type}, tag={self.tag}, file_name={file_name}")

    def estimate_tokens(self, content: str) -> int:
        return len(content) // 4

    def parse_content(self):
        return {
            "entities": [],
            "dependencies": {
                "imports": [],
                "modules": [],
                "calls": []
            }
        }

    def to_sandwich_block(self):
        attrs = []
        if self.content_type == ":post":
            attrs.append(f'post_id="{self.post_id}"')
            if self.user_id is not None:
                attrs.append(f'user_id="{self.user_id}"')
            if self.timestamp:
                attrs.append(f'mod_time="{self.timestamp}"')
            if self.relevance is not None:
                attrs.append(f'relevance="{self.relevance}"')
        else:
            if self.file_name:
                attrs.append(f'src="{self.file_name}"')
            if self.timestamp:
                attrs.append(f'mod_time="{self.timestamp}"')
            if self.file_id is not None:
                attrs.append(f'file_id="{self.file_id}"')
        attr_str = " ".join(attrs)
        return f"<{self.tag} {attr_str}>\n{self.content_text}\n</{self.tag}>"