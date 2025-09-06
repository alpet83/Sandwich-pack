# /lib/document_block.py, created 2025-07-15 15:53 EEST
import logging
from typing import Dict
from lib.content_block import ContentBlock
from lib.sandwich_pack import SandwichPack

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s #%(levelname)s: %(message)s')


# Под документами подразумеваются текстовые файлы, для которых не требуется парсинг кода
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


SandwichPack.register_block_class(DocumentBlock)


class TextDataBlock(ContentBlock):
    supported_types = ['.env', '.json', '.xml']

    def __init__(self, content_text: str, content_type: str, file_name: str, timestamp: str, **kwargs):
        super().__init__(content_text, content_type, file_name, timestamp, **kwargs)
        self.tag = {
            '.env': 'env',
            '.json': 'json',
            '.xml': 'xml'
        }.get(content_type, 'text_data')
        logging.debug(f"Initialized TextDataBlock with tag={self.tag}, content_type={content_type}, file_name={file_name}")


SandwichPack.register_block_class(TextDataBlock)
