# /lib/vue_block.py, updated 2025-07-24 16:23 EEST
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
        lines = self.content_text.splitlines()
        component_context = None
        component_indent = None

        # Найти компоненты
        component_pattern = re.compile(r"^(?P<indent>\s*)defineComponent\s*\(\s*{", re.DOTALL | re.MULTILINE)
        for match in component_pattern.finditer(self.content_text):
            component_name = "VueComponent"  # Имя по умолчанию, так как defineComponent не всегда имеет name
            start_line = self.content_text[:match.start()].count('\n') + 1
            full_text = self._extract_full_entity(match.start(), match.end())
            entities.append({
                "type": "component",
                "name": component_name,
                "visibility": "public",
                "file_id": self.file_id,
                "line_num": start_line,
                "tokens": self._estimate_tokens(full_text)
            })
            component_indent = len(match.group('indent'))
            component_context = component_name

        # Найти методы и функции
        method_pattern = re.compile(
            r"^(?P<indent>\s*)(?:methods|computed|watch)\s*:\s*{\s*[^}]*\b(\w+)\s*[:=]\s*(?:async\s+)?function\s*\(",
            re.DOTALL | re.MULTILINE
        )
        fn_pattern = re.compile(
            r"^(?P<indent>\s*)(?:function\s+|const\s+\w+\s*=\s*(?:async\s+)?function\s*|const\s+\w+\s*=\s*\([^)]*\)\s*=>)\s*(\w+)\s*\(",
            re.DOTALL | re.MULTILINE
        )
        for match in method_pattern.finditer(self.content_text):
            indent = len(match.group('indent'))
            method_name = match.group(1)
            start_line = self.content_text[:match.start()].count('\n') + 1
            full_text = self._extract_full_entity(match.start(), match.end())
            entities.append({
                "type": "method",
                "name": f"{component_context}::{method_name}" if component_context else method_name,
                "visibility": "public",
                "file_id": self.file_id,
                "line_num": start_line,
                "tokens": self._estimate_tokens(full_text)
            })

        for match in fn_pattern.finditer(self.content_text):
            indent = len(match.group('indent'))
            fn_name = match.group(1)
            start_line = self.content_text[:match.start()].count('\n') + 1
            full_text = self._extract_full_entity(match.start(), match.end())
            ent_type = "method" if component_context and indent > component_indent else "function"
            name = f"{component_context}::{fn_name}" if ent_type == "method" else fn_name
            entities.append({
                "type": ent_type,
                "name": name,
                "visibility": "public",
                "file_id": self.file_id,
                "line_num": start_line,
                "tokens": self._estimate_tokens(full_text)
            })

        # Проверить завершение компонента
        for i, line in enumerate(lines):
            if component_context and line.strip() and not line.strip().startswith('//'):
                indent = len(line) - len(line.lstrip())
                if indent <= component_indent:
                    component_context = None
                    component_indent = None

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
