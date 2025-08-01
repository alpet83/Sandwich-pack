# /lib/vue_block.py, updated 2025-08-01 13:10 EEST
# Formatted with proper line breaks and indentation for project compliance.

import re
import os
import logging
from typing import Optional
from lib.content_block import ContentBlock, estimate_tokens
from lib.sandwich_pack import SandwichPack

class ContentCodeVue(ContentBlock):
    supported_types = [".vue"]

    def __init__(self, content_text: str, content_type: str, file_name: str, timestamp: str, **kwargs):
        super().__init__(content_text, content_type, file_name, timestamp, **kwargs)
        self.tag = "vue"
        self.string_quote_chars = "\"'`"
        self.open_ml_string = ["`"]
        self.close_ml_string = ["`"]
        self.entity_map = {}  # Use entity_map for consistency with Rust
        logging.debug(f"Initialized ContentCodeVue with tag={self.tag}, file_name={file_name}")

    def parse_content(self) -> dict:
        """Parses Vue content to extract entities and dependencies using clean_lines."""
        self.entity_map = {}
        dependencies = {"modules": [], "imports": [], "calls": []}
        clean_content = self.get_clean_content()
        lines = self.clean_lines
        content_offset = 1  # clean_content starts at line 1 in clean_lines
        component_context = None
        component_indent = None
        component_context_line = 0

        # Find components
        component_pattern = re.compile(
            r"^(?P<indent>[ \t]*)(?:const\s+(?P<name>\w+)\s*=\s*)?defineComponent\s*\(\s*{",
            re.DOTALL | re.MULTILINE
        )
        for match in component_pattern.finditer(clean_content):
            start_pos = match.start('indent')  # Use indent to get correct line
            line_count = clean_content[:start_pos].count('\n')
            start_line = content_offset + line_count
            if start_line in self.entity_map:
                continue
            component_name = match.group('name') or "VueComponent"  # Use captured name or default
            full_text = self._extract_full_entity(match.start(), match.end(), clean_content)
            entity = {
                "type": "component",
                "name": component_name,
                "visibility": "public",
                "file_id": self.file_id,
                "first_line": start_line,
                "tokens": estimate_tokens(full_text)
            }
            self.add_entity(start_line, entity)
            component_indent = len(match.group('indent'))
            component_context = component_name
            component_context_line = start_line
            logging.debug(f"Parsed component {component_name} at line {start_line}")

        # Find methods
        method_pattern = re.compile(
            r"^(?P<indent>[ \t]*)(?:methods|computed|watch)\s*:\s*{\s*[^}]*\b(?P<name>\w+)\s*\(\s*\)\s*{",
            re.DOTALL | re.MULTILINE
        )
        for match in method_pattern.finditer(clean_content):
            start_pos = match.start('name')
            line_count = clean_content[:start_pos].count('\n')
            start_line = content_offset + line_count
            if start_line in self.entity_map:
                continue
            indent = len(match.group('indent'))
            name = match.group('name')
            vis = "public"
            full_text = self._extract_full_entity(match.start(), match.end(), clean_content)
            is_method = component_context and indent > component_indent and start_line > component_context_line
            ent_type = "method" if is_method else "function"
            name_final = f"{component_context}::{name}" if is_method else name
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

        # Find functions
        fn_pattern = re.compile(
            r"^(?P<indent>[ \t]*)(?:function\s+|const\s+\w+\s*=\s*(?:async\s+)?function\s*|const\s+\w+\s*=\s*\([^)]*\)\s*=>)\s*(?P<name>\w+)\s*\(\s*\)\s*{",
            re.DOTALL | re.MULTILINE
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
            is_method = component_context and indent > component_indent and start_line > component_context_line
            ent_type = "method" if is_method else "function"
            name_final = f"{component_context}::{name}" if is_method else name
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

        # Check component end
        for i, line in enumerate(lines[1:], 1):
            if not isinstance(line, str) or not line.strip():
                continue
            indent = len(line) - len(line.lstrip())
            if component_context and indent <= component_indent:
                component_context = None
                component_indent = None
                component_context_line = 0

        # Parse imports
        import_pattern = re.compile(
            r"import\s+{?([\w,\s]+)}?\s+from\s+['\"]([^'\"]+)['\"]",
            re.MULTILINE
        )
        for match in import_pattern.finditer(clean_content):
            items = [item.strip() for item in match.group(1).split(",")]
            for item in items:
                if item:
                    dependencies["imports"].append(item)
            dependencies["modules"].append(match.group(2))
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

SandwichPack.register_block_class(ContentCodeVue)