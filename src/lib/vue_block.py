# /lib/vue_block.py, updated 2025-07-15 15:43 EEST
import re
import logging
from typing import Dict
from lib.content_block import ContentBlock
from lib.sandwich_pack import SandwichPack

class ContentCodeVue(ContentBlock):
    supported_types = [".vue"]

    def __init__(self, content_text: str, content_type: str, file_name: str, timestamp: str, **kwargs):
        super().__init__(content_text, content_type, file_name, timestamp, **kwargs)
        self.tag = "vue"
        logging.debug(f"Initialized ContentCodeVue with tag={self.tag}, file_name={file_name}")

    def parse_content(self) -> Dict:
        entities = []
        dependencies = {"modules": [], "imports": [], "calls": []}
        component_pattern = re.compile(r"defineComponent\s*\(\s*{", re.DOTALL | re.MULTILINE)
        for match in component_pattern.finditer(self.content_text):
            full_text = self._extract_full_entity(match.start(), match.end())
            entities.append({"type": "component", "name": "VueComponent", "visibility": "public", "tokens": self._estimate_tokens(full_text)})
        import_pattern = re.compile(r"import\s+{?([\w,\s]+)}?\s+from\s+['\"]([^'\"]+)['\"]", re.MULTILINE)
        for match in import_pattern.finditer(self.content_text):
            items = [item.strip() for item in match.group(1).split(",")]
            for item in items:
                dependencies["imports"].append(item)
        return {"entities": entities, "dependencies": {k: sorted(list(set(v))) for k, v in dependencies.items()}}

    def _extract_full_entity(self, start: int, end_header: int) -> str:
        brace_count = 1
        i = end_header
        while i < len(self.content_text) and brace_count > 0:
            if self.content_text[i] == '{':
                brace_count += 1
            elif self.content_text[i] == '}':
                brace_count -= 1
            i += 1
        return self.content_text[start:i] if brace_count == 0 else self.content_text[start:end_header]

    def _estimate_tokens(self, content: str) -> int:
        return len(content) // 4

SandwichPack.register_block_class(ContentCodeVue)