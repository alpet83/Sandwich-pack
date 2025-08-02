# /lib/shellscript_block.py, updated 2025-08-01 11:37 EEST
# Formatted with proper line breaks and indentation for project compliance.

import re
import os
import logging
from typing import Dict
from pathlib import Path
from lib.content_block import ContentBlock, estimate_tokens
from lib.sandwich_pack import SandwichPack

class ContentShellScript(ContentBlock):
    supported_types = [".sh"]

    def __init__(self, content_text: str, content_type: str, file_name: str, timestamp: str, **kwargs):
        super().__init__(content_text, content_type, file_name, timestamp, **kwargs)
        self.tag = "shell"
        self.entity_map = {}  # Use entity_map for consistency with Rust
        logging.debug(f"Initialized ContentShellScript with tag={self.tag}, file_name={file_name}")

    def parse_content(self) -> Dict:
        """Parses shell script content to extract entities and dependencies."""
        self.entity_map = {}
        dependencies = {"modules": [], "imports": [], "calls": []}
        lines = self.content_text.splitlines()
        file_base = Path(self.file_name).stem

        # Find exported functions
        export_pattern = re.compile(r"^\s*export\s+-f\s+(?P<name>\w+)", re.MULTILINE)
        exported_functions = {match.group('name') for match in export_pattern.finditer(self.content_text)}

        # Find functions
        fn_pattern = re.compile(r"^(?P<indent>\s*)(?:function\s+)?(?P<name>\w+)\s*\(\)\s*{", re.MULTILINE)
        for match in fn_pattern.finditer(self.content_text):
            fn_name = match.group('name')
            vis = "public" if fn_name in exported_functions else "private"
            start_line = self.content_text[:match.start()].count('\n') + 1
            full_text = self._extract_full_entity(match.start(), match.end())
            entity = {
                "type": "function",
                "name": f"{file_base}::{fn_name}",
                "visibility": vis,
                "file_id": self.file_id,
                "first_line": start_line,
                "tokens": estimate_tokens(full_text)
            }
            self.add_entity(start_line, entity)
            logging.debug(f"Parsed function {file_base}::{fn_name} at line {start_line}")

        # Find dependencies (commands and scripts)
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

        return {"entities": self.sorted_entities(), "dependencies": {k: sorted(list(set(v))) for k, v in dependencies.items()}}

    def _extract_full_entity(self, start: int, end_header: int, content: str = None) -> str:
        """Extracts the full entity text using clean_lines for brace counting."""
        if len(self.clean_lines) <= 1:
            raise Exception("clean_lines not filled")
        content = content or self.get_clean_content()
        start_pos = start
        lines = content.splitlines()
        start_line = self.find_line(start_pos)
        start_line, end_line = self.detect_bounds(start_line, self.clean_lines)
        if start_line == end_line:
            self.parse_warn(f"Incomplete entity in file {self.file_name} at start={start}, using header end")
            return content[start:end_header]
        logging.info(f"Extracted entity from first_line={start_line} to last_line={end_line}")
        return "\n".join(self.clean_lines[start_line:end_line + 1])


SandwichPack.register_block_class(ContentShellScript)