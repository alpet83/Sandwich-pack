# /lib/rust_block.py, updated 2025-07-15 09:35 EEST
import re
import os
from typing import Dict
from lib.content_block import ContentBlock
from lib.sandwich_pack import SandwichPack

class ContentCodeRust(ContentBlock):
    supported_types = [".rs"]

    def __init__(self, content_text: str, content_type: str, file_name: str, timestamp: str):
        super().__init__(content_text, content_type, file_name, timestamp)

    def parse_content(self) -> Dict:
        entities = []
        dependencies = {"modules": [], "imports": [], "calls": []}
        struct_pattern = re.compile(r"(?P<vis>pub\s+)?struct\s+(?P<name>\w+)(<.*?>)?\s*{", re.DOTALL | re.MULTILINE)
        for match in struct_pattern.finditer(self.content_text):
            full_text = self._extract_full_entity(match.start(), match.end())
            vis = "public" if match.group('vis') else "private"
            entities.append({"type": "struct", "name": match.group('name'), "visibility": vis, "tokens": self._estimate_tokens(full_text)})
        trait_pattern = re.compile(r"(?P<vis>pub\s+)?trait\s+(?P<name>\w+)(<.*?>)?\s*{", re.DOTALL | re.MULTILINE)
        for match in trait_pattern.finditer(self.content_text):
            full_text = self._extract_full_entity(match.start(), match.end())
            vis = "public" if match.group('vis') else "private"
            entities.append({"type": "trait", "name": match.group('name'), "visibility": vis, "tokens": self._estimate_tokens(full_text)})
        fn_pattern = re.compile(r"(?P<vis>pub\s+)?(?:async\s+)?fn\s+(?P<name>\w+)\s*\((.*?)\)\s*(->\s*[^ {]+)?\s*{", re.DOTALL | re.MULTILINE)
        for match in fn_pattern.finditer(self.content_text):
            full_text = self._extract_full_entity(match.start(), match.end())
            vis = "public" if match.group('vis') else "private"
            entities.append({"type": "function", "name": match.group('name'), "visibility": vis, "tokens": self._estimate_tokens(full_text)})
        module_pattern = re.compile(r"pub\s+mod\s+(\w+);")
        for match in module_pattern.finditer(self.content_text):
            module_name = match.group(1)
            module_path = f"{os.path.dirname(self.file_name)}/{module_name}/mod.rs".replace("\\", "/")
            if not module_path.startswith("/"):
                module_path = f"/{module_path}"
            dependencies["modules"].append(module_name)
        import_pattern = re.compile(r"use\s+crate::([\w:]+)(?:\{([\w,: ]+)\})?;")
        for match in import_pattern.finditer(self.content_text):
            path = match.group(1).replace("::", "/")
            if match.group(2):
                for item in match.group(2).split(","):
                    dependencies["imports"].append(item.strip())
            else:
                dependencies["imports"].append(path.split("/")[-1])
        call_pattern = re.compile(r"\b(\w+)\s*\(")
        for match in call_pattern.finditer(self.content_text):
            dependencies["calls"].append(match.group(1))
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

SandwichPack.register_block_class(ContentCodeRust)