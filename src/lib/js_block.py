# /lib/js_block.py, updated 2025-08-01 13:10 EEST
# Formatted with proper line breaks and indentation for project compliance.

import re
import logging
from typing import Dict, List
from lib.content_block import ContentBlock, estimate_tokens
from lib.sandwich_pack import SandwichPack

class ContentCodeJs(ContentBlock):
    supported_types = [".js"]

    def __init__(self, content_text: str, content_type: str, file_name: str, timestamp: str, **kwargs):
        super().__init__(content_text, content_type, file_name, timestamp, **kwargs)
        self.tag = "jss"
        self.string_quote_chars = "\"'`"
        self.open_ml_string = ["`"]
        self.close_ml_string = ["`"]
        self.entity_map = {}  # Use entity_map for consistency with Rust
        logging.debug(f"Initialized ContentCodeJs with tag={self.tag}, file_name={file_name}")

    def parse_content(self) -> Dict:
        """Parses JavaScript content to extract entities and dependencies."""
        self.entity_map = {}
        dependencies = {"modules": [], "imports": [], "calls": []}
        clean_content = self.get_clean_content()
        lines = self.clean_lines
        content_offset = 1
        object_context = None
        object_indent = None

        # Initialize clean_lines
        self.strip_strings()
        self.strip_comments()

        # Find objects (e.g., export default { ... })
        object_pattern = re.compile(
            r"^(?P<indent>[ \t]*)(?:export\s+default\s+|const\s+(?P<name>\w+)\s*=\s*)\s*{\s*",
            re.MULTILINE
        )
        for match in object_pattern.finditer(clean_content):
            start_pos = match.start()  # Use start of match for correct line
            line_count = clean_content[:start_pos].count('\n')
            start_line = content_offset + line_count
            if start_line in self.entity_map:
                continue
            object_name = match.group('name')  # Use captured name
            if not object_name:
                logging.warning(f"No name captured for object at line {start_line}, skipping")
                continue
            full_text = self._extract_full_entity(match.start(), match.end(), clean_content)
            entity = {
                "type": "object",
                "name": object_name,
                "visibility": "public",
                "file_id": self.file_id,
                "first_line": start_line,
                "tokens": estimate_tokens(full_text)
            }
            self.add_entity(start_line, entity)
            object_indent = len(match.group('indent'))
            object_context = object_name
            logging.debug(f"Parsed object {object_name} at line {start_line}")

        # Find methods and functions
        method_pattern = re.compile(
            r"^(?P<indent>[ \t]*)(?:methods|computed|watch)\s*:\s*{\s*[^}]*\b(?P<name>\w+)\s*\(\s*\)\s*{",
            re.DOTALL | re.MULTILINE
        )
        fn_pattern = re.compile(
            r"^(?P<indent>[ \t]*)(?:function\s+(?P<name>\w+)\s*\(\s*\)\s*{|const\s+\w+\s*=\s*(?:async\s+)?function\s*\w+\s*\(\s*\)\s*{|const\s+\w+\s*=\s*\([^)]*\)\s*=>\s*{)",
            re.DOTALL | re.MULTILINE
        )
        for match in method_pattern.finditer(clean_content):
            indent = len(match.group('indent'))
            method_name = match.group('name')
            start_line = clean_content[:match.start('name')].count('\n') + content_offset
            if start_line in self.entity_map:
                continue
            full_text = self._extract_full_entity(match.start(), match.end(), clean_content)
            entity = {
                "type": "method",
                "name": f"{object_context}::{method_name}" if object_context else method_name,
                "visibility": "public",
                "file_id": self.file_id,
                "first_line": start_line,
                "tokens": estimate_tokens(full_text)
            }
            self.add_entity(start_line, entity)
            logging.debug(f"Parsed method {method_name} at line {start_line}")

        for match in fn_pattern.finditer(clean_content):
            indent = len(match.group('indent'))
            fn_name = match.group('name')
            start_line = clean_content[:match.start('name')].count('\n') + content_offset
            if start_line in self.entity_map:
                continue
            full_text = self._extract_full_entity(match.start(), match.end(), clean_content)
            ent_type = "method" if object_context and indent > object_indent else "function"
            name = f"{object_context}::{fn_name}" if ent_type == "method" else fn_name
            entity = {
                "type": ent_type,
                "name": name,
                "visibility": "public",
                "file_id": self.file_id,
                "first_line": start_line,
                "tokens": estimate_tokens(full_text)
            }
            self.add_entity(start_line, entity)
            logging.debug(f"Parsed {ent_type} {name} at line {start_line}")

        # Check object end
        for i, line in enumerate(lines[1:], 1):
            if not isinstance(line, str) or not line.strip():
                continue
            indent = len(line) - len(line.lstrip())
            if object_context and indent <= object_indent:
                object_context = None
                object_indent = None

        # Parse imports
        import_pattern = re.compile(
            r"import\s+{?([\w,\s]+)}?\s+from\s+['\"]([^'\"]+)['\"]|require\s*\(['\"]([^'\"]+)['\"]\)",
            re.MULTILINE
        )
        for match in import_pattern.finditer(clean_content):
            items = [item.strip() for item in match.group(1).split(",")] if match.group(1) else []
            module = match.group(2) or match.group(3)
            for item in items:
                dependencies["imports"].append(item)
            if module:
                dependencies["modules"].append(module)
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

SandwichPack.register_block_class(ContentCodeJs)