# /lib/shellscript_block.py, created 2025-07-25 08:32 EEST
import re
import os
import logging
from typing import Dict
from pathlib import Path
from lib.content_block import ContentBlock
from lib.sandwich_pack import SandwichPack

class ContentShellScript(ContentBlock):
    supported_types = [".sh"]

    def __init__(self, content_text: str, content_type: str, file_name: str, timestamp: str, **kwargs):
        super().__init__(content_text, content_type, file_name, timestamp, **kwargs)
        self.tag = "shell"
        logging.debug(f"Initialized ContentShellScript with tag={self.tag}, file_name={file_name}")

    def parse_content(self) -> Dict:
        entities = []
        dependencies = {"modules": [], "imports": [], "calls": []}
        lines = self.content_text.splitlines()
        file_base = Path(self.file_name).stem

        # Найти экспортируемые функции
        export_pattern = re.compile(r"^\s*export\s+-f\s+(?P<name>\w+)", re.MULTILINE)
        exported_functions = {match.group('name') for match in export_pattern.finditer(self.content_text)}

        # Найти функции
        fn_pattern = re.compile(r"^(?P<indent>\s*)(?:function\s+)?(?P<name>\w+)\s*\(\)\s*{", re.MULTILINE)
        for match in fn_pattern.finditer(self.content_text):
            fn_name = match.group('name')
            vis = "public" if fn_name in exported_functions else "private"
            start_line = self.content_text[:match.start()].count('\n') + 1
            full_text = self._extract_full_entity(match.start(), match.end())
            entities.append({
                "type": "function",
                "name": f"{file_base}::{fn_name}",
                "visibility": vis,
                "file_id": self.file_id,
                "line_num": start_line,
                "tokens": self._estimate_tokens(full_text)
            })
            logging.debug(f"Parsed function {file_base}::{fn_name} at line {start_line}")

        # Найти зависимости (команды и скрипты)
        cmd_pattern = re.compile(r"^\s*(\w+)\s+[^|>\s]", re.MULTILINE)
        for match in cmd_pattern.finditer(self.content_text):
            cmd = match.group(1)
            if cmd not in ["if", "while", "for", "function", "case", "esac", "fi", "done"]:
                dependencies["calls"].append(cmd)

        script_pattern = re.compile(r"^\s*(?:\.|source|\./)\s+([^\s]+)", re.MULTILINE)
        for match in script_pattern.finditer(self.content_text):
            script = match.group(1)
            script_path = f"{os.path.dirname(self.file_name)}/{script}".replace("\\", "/")
            if not script_path.startswith("/"):
                script_path = f"/{script_path}"
            dependencies["modules"].append(script_path)

        return {"entities": entities, "dependencies": {k: sorted(list(set(v))) for k, v in dependencies.items()}}

    def _extract_full_entity(self, start: int, end_header: int, content: str = None) -> str:
        content = content or self.content_text
        brace_count = 1
        i = end_header
        while i < len(content) and brace_count > 0:
            if content[i] == '{':
                brace_count += 1
            elif content[i] == '}':
                brace_count -= 1
            i += 1
        return content[start:i] if brace_count == 0 else content[start:end_header]

    def _estimate_tokens(self, content: str) -> int:
        return len(content) // 4

SandwichPack.register_block_class(ContentShellScript)