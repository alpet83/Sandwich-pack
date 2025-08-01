# /lib/rust_block.py, updated 2025-07-31 15:14 EEST
# Formatted with proper line breaks and indentation for project compliance.

import re
import os
import logging
from pathlib import Path
from lib.content_block import ContentBlock, estimate_tokens
from lib.sandwich_pack import SandwichPack

class ContentCodeRust(ContentBlock):
    supported_types = [".rs"]

    def __init__(self, content_text, content_type, file_name, timestamp, **kwargs):
        super().__init__(content_text, content_type, file_name, timestamp, **kwargs)
        self.tag = "rustc"
        self.entity_map = {}
        self.raw_str_prefix = "r"
        self.open_ml_string = ["r#\""]
        self.close_ml_string = ["\"#"]
        self.module_prefix = kwargs.get("module_prefix", "")  # Tracks current module prefix (e.g., "logger.")
        logging.debug(f"Initialized ContentCodeRust with tag={self.tag}, file_name={file_name}, module_prefix={self.module_prefix}")

    def check_lines_match(self, offset, full_clean_lines):
        """Validates that clean_lines matches full_clean_lines at the given offset."""
        if offset < 1 or offset >= len(self.clean_lines):
            logging.error(f"Invalid offset {offset} for file {self.file_name}")
            return False
        for i, line in enumerate(self.clean_lines[offset:], offset):
            if i >= len(full_clean_lines):
                return False
            if not isinstance(line, str) or not isinstance(full_clean_lines[i], str):
                continue
            if line.strip() and full_clean_lines[i].strip() and line != full_clean_lines[i]:
                logging.warning(f"Line mismatch at {i}: expected '{full_clean_lines[i]}', got '{line}'")
                return False
        return True

    def _parse_traits(self, clean_content, content_offset):
        """Parses Rust traits and their abstract methods."""
        trait_pattern = re.compile(
            r"^(?P<indent>[ \t]*)(?P<vis>pub\s+)?trait\s+(?P<name>\w+)(<.*?>)?\s*{",
            re.MULTILINE
        )
        for match in trait_pattern.finditer(clean_content):
            start_pos = match.start('name')
            line_count = clean_content[:start_pos].count('\n')
            start_line = content_offset + line_count
            trait_name = match.group('name')
            vis = "public" if match.group('vis') else "private"
            full_text = self._extract_full_entity(match.start(), match.end(), clean_content)
            entity = {
                "type": "interface",
                "name": f"{self.module_prefix}{trait_name}",
                "visibility": vis,
                "file_id": self.file_id,
                "first_line": start_line,
                "tokens": estimate_tokens(full_text)
            }
            self.add_entity(start_line, entity)

            # Parse abstract methods within trait
            trait_content = full_text
            trait_offset = start_line
            logging.debug(f"Trait content: '{trait_content[:100]}...', start_pos: {start_pos}")
            fn_trait_pattern = re.compile(
                r"^(?P<indent>[ \t]*)(?:#\[.*?\]\s*)?(?P<vis>pub\s+)?(?:async\s+)?fn\s+(?P<name>\w+)\s*\([\s\S]*?\)\s*(->\s*[\w\s:<,>\[\]]+\s*)?(?:;|\{)",
                re.MULTILINE
            )
            for match_fn in fn_trait_pattern.finditer(trait_content):
                start_pos_fn = match_fn.start('name')
                line_count = trait_content[:start_pos_fn].count('\n')
                method_line = trait_offset + line_count
                name = match_fn.group('name')
                vis = "public" if match_fn.group('vis') else "private"
                full_text_method = match_fn.group(0)
                ent_type = "abstract method" if full_text_method.endswith(';') else "method"
                entity = {
                    "type": ent_type,
                    "name": f"{self.module_prefix}{trait_name}::{name}",
                    "visibility": vis,
                    "file_id": self.file_id,
                    "first_line": method_line,
                    "last_line": method_line,  # Abstract methods are single-line
                    "tokens": estimate_tokens(full_text_method)
                }
                self.add_entity(method_line, entity)

    def _parse_impl(self, clean_content, content_offset):
        """Parses Rust trait implementations and their methods."""
        impl_pattern = re.compile(
            r"^(?P<indent>[ \t]*)(?:#\[.*?\]\s*)?(?P<vis>pub\s+)?impl\s+(?P<trait_name>\w+)\s+"
            r"for\s+(?P<struct_name>\w+)\s*{",
            re.MULTILINE
        )
        fn_pattern = re.compile(
            r"^(?P<indent>[ \t]*)(?:#\[.*?\]\s*)?(?P<vis>pub\s+)?(?:async\s+)?fn\s+(?P<name>\w+)\s*\([\s\S]*?\)\s*(->\s*[\w\s:<,>\[\]]+\s*)?{",
            re.MULTILINE
        )
        for match in impl_pattern.finditer(clean_content):
            start_pos = match.start('trait_name')
            line_count = clean_content[:start_pos].count('\n')
            start_line = content_offset + line_count
            trait_name = match.group('trait_name')
            struct_name = match.group('struct_name')
            vis = "public" if match.group('vis') else "private"
            full_text = self._extract_full_entity(match.start(), match.end(), clean_content)
            entity = {
                "type": "class",
                "name": f"{self.module_prefix}{trait_name}<{struct_name}>",
                "visibility": vis,
                "file_id": self.file_id,
                "first_line": start_line,
                "tokens": estimate_tokens(full_text)
            }
            self.add_entity(start_line, entity)

            # Parse methods within impl
            impl_content = full_text
            impl_offset = start_line
            for match_fn in fn_pattern.finditer(impl_content):
                start_pos_fn = match_fn.start('name')
                line_count = impl_content[:start_pos_fn].count('\n')
                method_line = impl_offset + line_count
                name = match_fn.group('name')
                vis = "public" if match_fn.group('vis') else "private"
                full_text_method = self._extract_full_entity(match_fn.start(), match_fn.end(), impl_content)
                entity = {
                    "type": "method",
                    "name": f"{self.module_prefix}{trait_name}<{struct_name}>::{name}",
                    "visibility": vis,
                    "file_id": self.file_id,
                    "first_line": method_line,
                    "tokens": estimate_tokens(full_text_method)
                }
                self.add_entity(method_line, entity)

    def _parse_structures(self, clean_content, content_offset):
        """Parses Rust structures."""
        struct_pattern = re.compile(
            r"^(?P<indent>[ \t]*)(?P<vis>pub\s+)?struct\s+(?P<name>\w+)(<.*?>)?\s*{",
            re.MULTILINE
        )
        for match in struct_pattern.finditer(clean_content):
            start_pos = match.start('name')
            line_count = clean_content[:start_pos].count('\n')
            start_line = content_offset + line_count
            struct_name = match.group('name')
            vis = "public" if match.group('vis') else "private"
            full_text = self._extract_full_entity(match.start(), match.end(), clean_content)
            entity = {
                "type": "struct",
                "name": f"{self.module_prefix}{struct_name}",
                "visibility": vis,
                "file_id": self.file_id,
                "first_line": start_line,
                "tokens": estimate_tokens(full_text)
            }
            self.add_entity(start_line, entity)

    def _parse_modules(self, clean_content: str, content_offset: int, local_clean_lines: list, depth: int = 0):
        """Parses Rust modules and their contents recursively."""
        dependencies = {"modules": [], "imports": [], "calls": []}
        module_pattern = re.compile(
            r"^(?P<indent>[ \t]*)(?P<vis>pub\s+)?mod\s+(?P<name>\w+)\s*{",
            re.MULTILINE
        )
        for match in module_pattern.finditer(clean_content):
            start_pos = match.start('name')
            line_count = clean_content[:start_pos].count('\n')
            start_line = content_offset + line_count
            module_name = match.group('name')
            vis = "public" if match.group('vis') else "private"
            full_text = self._extract_full_entity(match.start(), match.end(), clean_content)
            entity = {
                "type": "module",
                "name": f"{self.module_prefix}{module_name}",
                "visibility": vis,
                "file_id": self.file_id,
                "first_line": start_line,
                "tokens": estimate_tokens(full_text)
            }
            self.add_entity(start_line, entity)

            # Extract module content (excluding mod declaration and closing brace)
            module_lines = full_text.splitlines()  # Skip first and last lines
            module_size = len(module_lines)
            # Create a copy of local_clean_lines and replace non-module lines with comments
            sub_clean_lines = local_clean_lines.copy()
            end_line = start_line + module_size

            for i in range(0, len(sub_clean_lines)):
                if i < start_line + 1 or i > end_line - 1:
                    sub_clean_lines[i] = f"// ext. line #{i}"

            masked_content = "\n".join(sub_clean_lines[1:])
            sub_parser = ContentCodeRust(masked_content, self.content_type,
                                         f"{self.file_name}&{module_name}", self.timestamp,
                                         module_prefix=f"{self.module_prefix}{module_name}.")
            sub_result = sub_parser.parse_content(sub_clean_lines, depth + 1)
            logging.debug(f"Sub-parser entities: {sub_result['entities']}")
            for i, sub_entity in enumerate(sub_result["entities"], 1):
                first_line = sub_entity['first_line']
                if first_line in self.entity_map:
                    logging.error(f"Already exists entity {self.entity_map[first_line]}, can't add {sub_entity}")
                    continue
                self.entity_map[first_line] = sub_entity
            dependencies["modules"].extend(sub_result["dependencies"]["modules"])
            dependencies["imports"].extend(sub_result["dependencies"]["imports"])
            dependencies["calls"].extend(sub_result["dependencies"]["calls"])
        return dependencies

    def _parse_functions(self, clean_content, content_offset):
        """Parses Rust functions not belonging to traits or impls."""
        fn_pattern = re.compile(
            r"^(?P<indent>[ \t]*)(?P<vis>pub\s+)?(?:async\s+)?fn\s+(?P<name>\w+)\s*\([\s\S]*?\)\s*(->\s*[\w\s:<,>\[\]]+\s*)?{",
            re.MULTILINE
        )
        for match in fn_pattern.finditer(clean_content):
            start_pos = match.start('name')
            line_count = clean_content[:start_pos].count('\n')
            start_line = content_offset + line_count
            name = match.group('name')
            vis = "public" if match.group('vis') else "private"
            full_text = self._extract_full_entity(match.start(), match.end(), clean_content)
            name_final = f"{self.module_prefix}{name}"
            # Skip if already processed as a trait or impl method
            if any(name_final.startswith(f"{e['name']}::") for e in self.entity_map.values() if e["type"] in ["interface", "class"]):
                logging.debug(f"Skipping {name_final} as it matches a trait or impl method")
                continue
            entity = {
                "type": "function",
                "name": name_final,
                "visibility": vis,
                "file_id": self.file_id,
                "first_line": start_line,
                "tokens": estimate_tokens(full_text)
            }
            self.add_entity(start_line, entity)

    def parse_content(self, clean_lines=None, depth=0):
        """Parses Rust content to extract entities and dependencies."""
        logging.debug(f"Parsing content at depth {depth} for file {self.file_name}")
        if depth >= 2:
            self.parse_warn(f"Maximum recursion depth reached for file {self.file_name}")
            return {"entities": [], "dependencies": {"modules": [], "imports": [], "calls": []}}
        self.entity_map = {}
        dependencies = {"modules": [], "imports": [], "calls": []}
        clean_content = self.get_clean_content() if clean_lines is None else "\n".join(clean_lines[1:])
        local_clean_lines = clean_lines if clean_lines is not None else self.clean_lines
        content_offset = 1  # clean_content starts at line 1 in clean_lines

        # Parse in order: modules -> traits -> impls -> structures -> functions
        module_deps = self._parse_modules(clean_content, content_offset, local_clean_lines, depth)
        # Clear module lines after adding entities
        for entity in self.entity_map.values():
            if entity["type"] == "module":
                start_line, end_line = self.detect_bounds(entity["first_line"], local_clean_lines)
                local_clean_lines[start_line:end_line + 1] = [""] * (end_line + 1 - start_line)

        dependencies["modules"].extend(module_deps["modules"])
        dependencies["imports"].extend(module_deps["imports"])
        dependencies["calls"].extend(module_deps["calls"])
        self._parse_traits(clean_content, content_offset)
        self._parse_impl(clean_content, content_offset)
        self._parse_structures(clean_content, content_offset)
        self._parse_functions(clean_content, content_offset)

        # Add entities in order of first_line
        logging.debug(f"{self.module_prefix} Seen lines before global function search: {set(self.entity_map.keys())}")

        # Sort entities
        entities = self.sorted_entities()
        logging.debug(f"Parsed {len(entities)} entities in {self.file_name}")
        return {"entities": entities, "dependencies": {k: sorted(list(set(v))) for k, v in dependencies.items()}}

    def count_chars(self, line_num, ch, clean_lines=None):
        """Counts occurrences of a character in a specific line of clean code."""
        clean_lines = clean_lines or self.clean_lines
        if line_num < 1 or line_num >= len(clean_lines):
            logging.error(f"Invalid line number {line_num} for file {self.file_name}")
            return 0
        line = clean_lines[line_num]
        if not isinstance(line, str):
            return 0
        return line.count(ch)

    def _extract_full_entity(self, start, end_header, content=None):
        """Extracts the full entity text using clean_lines for brace counting."""
        if len(self.clean_lines) <= 1:
            raise Exception("clean_lines not filled")
        content = content or self.get_clean_content()
        start_pos = start
        lines = content.splitlines()
        start_line = self.find_line(start_pos)
        logging.debug(f"Calculating bounds for start_pos={start_pos}, start_line={start_line}, content preview: {content[start:start + 100]}...")
        logging.debug(f"Entity at line {start_line}: '{self.clean_lines[start_line]}', raw: '{lines[start_line - 1]}'")
        logging.debug(f"Clean lines: {self.clean_lines[start_line-1:start_line+2]}")
        start_line, end_line = self.detect_bounds(start_line, self.clean_lines)
        if start_line == end_line:
            self.parse_warn(f"Incomplete entity in file {self.file_name} at start={start}, using header end")
            return content[start:end_header]
        logging.info(f"Extracted entity from first_line={start_line} to last_line={end_line}")
        return "\n".join(self.clean_lines[start_line:end_line + 1])

    def _estimate_tokens(self, content):
        return estimate_tokens(content)

SandwichPack.register_block_class(ContentCodeRust)