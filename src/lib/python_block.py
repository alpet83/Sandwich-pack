# /lib/python_block.py, updated 2025-07-15 15:43 EEST
import re
import logging
from typing import Dict
from lib.content_block import ContentBlock
from lib.sandwich_pack import SandwichPack

class ContentCodePython(ContentBlock):
    supported_types = [".py"]

    def __init__(self, content_text: str, content_type: str, file_name: str, timestamp: str, **kwargs):
        super().__init__(content_text, content_type, file_name, timestamp, **kwargs)
        self.tag = "python"
        logging.debug(f"Initialized ContentCodePython with tag={self.tag}, file_name={file_name}")

    def parse_content(self) -> Dict:
        entities = []
        dependencies = {"modules": [], "imports": [], "calls": []}
        fn_pattern = re.compile(r"(?P<vis>@classmethod\s+|@staticmethod\s+)?def\s+(?P<name>\w+)\s*\(", re.DOTALL | re.MULTILINE)
        for match in fn_pattern.finditer(self.content_text):
            full_text = self._extract_full_entity(match.start(), match.end())
            vis = "public" if match.group('vis') else "private"
            entities.append({"type": "function", "name": match.group('name'), "visibility": vis, "tokens": self._estimate_tokens(full_text)})
        class_pattern = re.compile(r"(?P<vis>@classmethod\s+|@staticmethod\s+)?class\s+(?P<name>\w+)\s*(?:\([^)]*\))?\s*:", re.DOTALL | re.MULTILINE)
        for match in class_pattern.finditer(self.content_text):
            full_text = self._extract_full_entity(match.start(), match.end())
            vis = "public" if match.group('vis') else "private"
            entities.append({"type": "class", "name": match.group('name'), "visibility": vis, "tokens": self._estimate_tokens(full_text)})
        import_pattern = re.compile(r"from\s+([\w.]+)\s+import\s+([\w,\s]+)", re.MULTILINE)
        for match in import_pattern.finditer(self.content_text):
            items = [item.strip() for item in match.group(2).split(",")]
            for item in items:
                dependencies["imports"].append(item)
            dependencies["modules"].append(match.group(1))
        return {"entities": entities, "dependencies": {k: sorted(list(set(v))) for k, v in dependencies.items()}}

    def _extract_full_entity(self, start: int, end_header: int) -> str:
        indent_level = 0
        i = end_header
        while i < len(self.content_text):
            if self.content_text[i] == ':':
                indent_level += 1
                i += 1
                while i < len(self.content_text) and self.content_text[i].isspace():
                    i += 1
                while i < len(self.content_text) and indent_level > 0:
                    line = self.content_text[i:].split('\n', 1)[0]
                    if not line.strip() or line.strip().startswith('#'):
                        i += len(line) + 1
                        continue
                    indent = len(line) - len(line.lstrip())
                    if indent == 0 and line.strip():
                        break
                    i += len(line) + 1
                return self.content_text[start:i]
            i += 1
        return self.content_text[start:end_header]

    def _estimate_tokens(self, content: str) -> int:
        return len(content) // 4

SandwichPack.register_block_class(ContentCodePython)