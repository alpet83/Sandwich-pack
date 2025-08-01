# /lib/python_block.py, updated 2025-08-01 13:10 EEST
# Formatted with proper line breaks and indentation for project compliance.

import re
import os
import logging
from typing import Optional
from lib.content_block import ContentBlock, estimate_tokens
from lib.sandwich_pack import SandwichPack

class ContentCodePython(ContentBlock):
    supported_types = [".py"]

    def __init__(self, content_text: str, content_type: str, file_name: str, timestamp: str, **kwargs):
        super().__init__(content_text, content_type, file_name, timestamp, **kwargs)
        self.tag = "python"
        self.open_ml_string = ['"""', "'''"]
        self.close_ml_string = ['"""', "'''"]
        self.open_sl_comment = ["#"]
        self.open_ml_comment = ['"""', "'''"]
        self.close_ml_comment = ['"""', "'''"]
        self.entity_map = {}  # Use entity_map for consistency with Rust
        logging.debug(f"Initialized ContentCodePython with tag={self.tag}, file_name={file_name}")

    def detect_bounds(self, start_line, clean_lines):
        """Detects the start and end line of an entity using indentation for Python."""
        if start_line < 1 or start_line >= len(clean_lines) or not clean_lines[start_line] or not clean_lines[start_line].strip():
            logging.error(f"Invalid start line {start_line} for file {self.file_name} module [{self.module_prefix}]")
            return start_line, start_line
        initial_indent = len(clean_lines[start_line]) - len(clean_lines[start_line].lstrip())
        line_num = start_line
        while line_num < len(clean_lines):
            line = clean_lines[line_num]
            if not isinstance(line, str) or not line.strip():
                line_num += 1
                continue
            current_indent = len(line) - len(line.lstrip())
            if current_indent <= initial_indent and line_num > start_line:
                return start_line, line_num - 1
            line_num += 1
        logging.info(f"Reached end of file for entity at line {start_line} in file {self.file_name}")
        return start_line, line_num - 1

    def parse_content(self) -> dict:
        """Parses Python content to extract entities and dependencies using clean_lines."""
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
            r"^(?P<indent>[ \t]*)(?P<vis>@classmethod\s+|@staticmethod\s+)?class\s+(?P<name>\w+)\s*(?:\([^)]*\))?\s*:",
            re.MULTILINE
        )
        for match in class_pattern.finditer(clean_content):
            start_pos = match.start('name')
            line_count = clean_content[:start_pos].count('\n')
            start_line = content_offset + line_count
            if start_line in self.entity_map:
                continue
            class_name = match.group('name')
            vis = "public" if match.group('vis') else "private"
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
            r"^(?P<indent>[ \t]*)(?P<vis>@classmethod\s+|@staticmethod\s+)?def\s+(?P<name>\w+)\s*\(",
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
            vis = "public" if match.group('vis') else "private"
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

        # Parse imports
        import_pattern = re.compile(r"from\s+([\w.]+)\s+import\s+([\w\s,]+?)(?=\s*(?:$|\n|;))", re.MULTILINE)
        for match in import_pattern.finditer(clean_content):
            items = [item.strip() for item in match.group(2).split(",")]
            for item in items:
                if item:
                    dependencies["imports"].append(item)
            dependencies["modules"].append(match.group(1))
        logging.debug(f"Parsed {len(self.entity_map)} entities in {self.file_name}")
        return {"entities": self.sorted_entities(), "dependencies": {k: sorted(list(set(v))) for k, v in dependencies.items()}}

    def _extract_full_entity(self, start: int, end_header: int, content: str = None) -> str:
        """Extracts the full entity text using clean_lines for colon counting."""
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

SandwichPack.register_block_class(ContentCodePython)
import re
import os
import logging
from typing import Optional
from lib.content_block import ContentBlock, estimate_tokens
from lib.sandwich_pack import SandwichPack

class ContentCodePython(ContentBlock):
    supported_types = [".py"]

    def __init__(self, content_text: str, content_type: str, file_name: str, timestamp: str, **kwargs):
        super().__init__(content_text, content_type, file_name, timestamp, **kwargs)
        self.tag = "python"
        self.open_ml_string = ['"""', "'''"]
        self.close_ml_string = ['"""', "'''"]
        self.open_sl_comment = ["#"]
        self.open_ml_comment = ['"""', "'''"]
        self.close_ml_comment = ['"""', "'''"]
        self.entity_map = {}  # Use entity_map for consistency with Rust
        logging.debug(f"Initialized ContentCodePython with tag={self.tag}, file_name={file_name}")

    def detect_bounds(self, start_line, clean_lines):
        """Detects the start and end line of an entity using indentation for Python."""
        if start_line < 1 or start_line >= len(clean_lines) or not clean_lines[start_line] or not clean_lines[start_line].strip():
            logging.error(f"Invalid start line {start_line} for file {self.file_name} module [{self.module_prefix}]")
            return start_line, start_line
        initial_indent = len(clean_lines[start_line]) - len(clean_lines[start_line].lstrip())
        line_num = start_line
        while line_num < len(clean_lines):
            line = clean_lines[line_num]
            if not isinstance(line, str) or not line.strip():
                line_num += 1
                continue
            current_indent = len(line) - len(line.lstrip())
            if current_indent <= initial_indent and line_num > start_line:
                return start_line, line_num - 1
            line_num += 1
        logging.info(f"Reached end of file for entity at line {start_line} in file {self.file_name}")
        return start_line, line_num - 1

    def parse_content(self) -> dict:
        """Parses Python content to extract entities and dependencies using clean_lines."""
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
            r"^(?P<indent>[ \t]*)(?P<vis>@classmethod\s+|@staticmethod\s+)?class\s+(?P<name>\w+)\s*(?:\([^)]*\))?\s*:",
            re.MULTILINE
        )
        for match in class_pattern.finditer(clean_content):
            start_pos = match.start('name')
            line_count = clean_content[:start_pos].count('\n')
            start_line = content_offset + line_count
            if start_line in self.entity_map:
                continue
            class_name = match.group('name')
            vis = "public" if match.group('vis') else "private"
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
            r"^(?P<indent>[ \t]*)(?P<vis>@classmethod\s+|@staticmethod\s+)?def\s+(?P<name>\w+)\s*\(",
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
            vis = "public" if match.group('vis') else "private"
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

        # Parse imports
        import_pattern = re.compile(r"from\s+([\w.]+)\s+import\s+([\w,\s]+)", re.MULTILINE)
        for match in import_pattern.finditer(clean_content):
            items = [item.strip() for item in match.group(2).split(",")]
            for item in items:
                dependencies["imports"].append(item)
            dependencies["modules"].append(match.group(1))
        logging.debug(f"Parsed {len(self.entity_map)} entities in {self.file_name}")
        return {"entities": self.sorted_entities(), "dependencies": {k: sorted(list(set(v))) for k, v in dependencies.items()}}

    def _extract_full_entity(self, start: int, end_header: int, content: str = None) -> str:
        """Extracts the full entity text using clean_lines for colon counting."""
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

SandwichPack.register_block_class(ContentCodePython)