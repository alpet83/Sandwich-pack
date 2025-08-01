# /lib/php_block.py, updated 2025-08-01 13:10 EEST
# Formatted with proper line breaks and indentation for project compliance.

import re
import os
import logging
from typing import Optional
from pathlib import Path
from lib.content_block import ContentBlock, estimate_tokens
from lib.sandwich_pack import SandwichPack

class ContentCodePHP(ContentBlock):
    supported_types = [".php"]

    def __init__(self, content_text: str, content_type: str, file_name: str, timestamp: str, **kwargs):
        super().__init__(content_text, content_type, file_name, timestamp, **kwargs)
        self.tag = "php"
        self.raw_quote_char = "'"
        self.open_sl_comment = ["//", "#"]
        self.entity_map = {}  # Use entity_map for consistency with Rust
        logging.debug(f"Initialized ContentCodePhp with tag={self.tag}, file_name={file_name}")

    def check_raw_escape(self, line: str, position: int, quote_char: str) -> bool:
        """Checks if the character at position is part of a PHP raw string escape sequence."""
        if position + 1 < len(line) and line[position] == self.escape_char:
            next_char = line[position + 1]
            return next_char == quote_char or next_char == self.escape_char
        return False

    def parse_content(self) -> dict:
        """Parses PHP content to extract entities and dependencies using clean_lines."""
        self.entity_map = {}
        dependencies = {"modules": [], "imports": [], "calls": []}
        clean_content = self.get_clean_content()
        lines = self.clean_lines
        content_offset = 1  # clean_content starts at line 1 in clean_lines
        class_context = None
        class_indent = None
        class_context_line = 0

        # Find classes
        class_pattern = re.compile(
            r"^(?P<indent>[ \t]*)(?:public\s+|protected\s+|private\s+)?class\s+(?P<name>\w+)\s*(?:extends\s+\w+)?\s*{",
            re.MULTILINE
        )
        for match in class_pattern.finditer(clean_content):
            start_pos = match.start('name')
            line_count = clean_content[:start_pos].count('\n')
            start_line = content_offset + line_count
            if start_line in self.entity_map:
                continue
            class_name = match.group('name')
            vis = "public"
            full_text = self._extract_full_entity(match.start(), match.end(), clean_content)
            entity = {
                "type": "class",
                "name": class_name,
                "visibility": vis,
                "file_id": self.file_id,
                "first_line": start_line,
                "tokens": estimate_tokens(full_text)
            }
            self.add_entity(start_line, entity)
            class_indent = len(match.group('indent'))
            class_context = class_name
            class_context_line = start_line
            logging.debug(f"Parsed class {class_name} at line {start_line}")

        # Find functions and methods
        fn_pattern = re.compile(
            r"^(?P<indent>[ \t]*)(?:public\s+|protected\s+|private\s+)?function\s+(?P<name>\w+)\s*\(",
            re.MULTILINE
        )
        for match in fn_pattern.finditer(clean_content):
            start_pos = match.start('name')
            line_count = clean_content[:start_pos].count('\n')
            start_line = content_offset + line_count
            if start_line in self.entity_map:
                continue
            indent = len(match.group('indent'))
            name = match.group('name')
            vis = "public"
            full_text = self._extract_full_entity(match.start(), match.end(), clean_content)
            is_method = class_context and indent > class_indent and start_line > class_context_line
            ent_type = "method" if is_method else "function"
            name_final = f"{class_context}::{name}" if is_method else name
            entity = {
                "type": ent_type,
                "name": name_final,
                "visibility": vis,
                "file_id": self.file_id,
                "first_line": start_line,
                "tokens": estimate_tokens(full_text)
            }
            self.add_entity(start_line, entity)
            logging.debug(f"Parsed {ent_type} {name_final} at line {start_line}")

        # Check class end
        for i, line in enumerate(lines[1:], 1):
            if not isinstance(line, str) or not line.strip():
                continue
            indent = len(line) - len(line.lstrip())
            if class_context and indent <= class_indent:
                class_context = None
                class_indent = None
                class_context_line = 0

        # Parse imports and calls
        import_pattern = re.compile(r"require\s*\(['\"]([^'\"]+)['\"]\)|include\s*\(['\"]([^'\"]+)['\"]\)", re.MULTILINE)
        for match in import_pattern.finditer(clean_content):
            module = match.group(1) or match.group(2)
            if module:
                dependencies["modules"].append(module)
        call_pattern = re.compile(r"\b(\w+)\s*\(")
        for match in call_pattern.finditer(clean_content):
            dependencies["calls"].append(match.group(1))
        logging.debug(f"Parsed {len(self.entity_map)} entities in {self.file_name}")
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

SandwichPack.register_block_class(ContentCodePHP)