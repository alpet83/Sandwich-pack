# /lib/document_block.py, created 2025-07-15 15:53 EEST
import logging
from typing import Dict
from lib.content_block import ContentBlock
from lib.sandwich_pack import SandwichPack

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s #%(levelname)s: %(message)s')

class DocumentBlock(ContentBlock):
    supported_types = ['.md', '.conf', '.toml', '.rulz']

    def __init__(self, content_text: str, content_type: str, file_name: str, timestamp: str, **kwargs):
        super().__init__(content_text, content_type, file_name, timestamp, **kwargs)
        self.tag = {
            '.md': 'markdown',
            '.conf': 'conf',
            '.toml': 'toml',
            '.rulz': 'rules'
        }.get(content_type, 'document')
        logging.debug(f"Initialized DocumentBlock with tag={self.tag}, content_type={content_type}, file_name={file_name}")

    def parse_content(self) -> Dict:
        return {
            "entities": [],
            "dependencies": {
                "imports": [],
                "modules": [],
                "calls": []
            }
        }

SandwichPack.register_block_class(DocumentBlock)