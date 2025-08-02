# /lib/rust_block.py, updated 2025-08-01 23:00 EEST
# Formatted with proper line breaks and indentation for project compliance.

import re
import os
import logging
import traceback
from pathlib import Path
from lib.content_block import ContentBlock, estimate_tokens
from lib.sandwich_pack import SandwichPack
from lib.entity_parser import EntityParser

def build_regex(token, extra=None):
    """Generate and compile a regex pattern for parsing Rust entities.

    Args:
        token (str): The primary token for the entity (e.g., 'fn', 'mod', 'struct', 'trait', 'impl').
        extra (str, optional): Additional regex pattern to append (e.g., for generics, impl for clause, or method endings).

    Returns:
        re.Pattern: Compiled regex pattern.

    Raises:
        re.error: If the pattern is invalid, logs the error with token and extra.
    """
    base = r"^(?P<indent>[ \t]*)(?:#\[.*?\]\s*)?(?P<vis>pub\s+)?%s\s+(?P<name>\w+)" % token
    pattern = base + (extra if isinstance(extra, str) else r"\s*{")
    try:
        return re.compile(pattern, re.MULTILINE)
    except re.error as e:
        logging.error(f"Failed to compile regex for token={token}, extra={extra}: {str(e)}")
        raise

# Regular expression constants
FN_EXTRA = r"\s*\([\s\S]*?\)"
FN_REGEX = build_regex("fn", FN_EXTRA + r"\s*(->\s*[\w\s:<,>\[\]]+\s*)?{")
MODULE_REGEX = build_regex("mod")
STRUCT_REGEX = build_regex("struct", r"(<.*?>)?\s*{")
TRAIT_REGEX = build_regex("trait", r"(<.*?>)?\s*{")
IMPL_REGEX = build_regex("impl", r"\s+for\s+(?P<struct_name>\w+)\s*{")  # noqa: W605
FN_TRAIT_REGEX = build_regex("fn", FN_EXTRA + r"(?:;|\{)")  # noqa: W605


class ModuleParser(EntityParser):
    """Parser for Rust modules with recursive parsing."""
    def __init__(self, entity_type, owner):
        super().__init__(entity_type, owner, MODULE_REGEX, r"\bmod\b", default_visibility="private")

    def _process_match(self, match, clean_content, content_offset):
        """Process a module match and perform recursive parsing."""
        start_pos = match.start('name')
        line_count = clean_content[:start_pos].count('\n')
        start_line = content_offset + line_count
        module_name = match.group('name')
        vis = "public" if match.groupdict().get('vis') else "private"
        name_final = f"{self.owner.module_prefix}{module_name}"
        full_text = self.owner.extract_entity_text(match.start(), match.end())
        logging.debug(f"Processing entity {name_final} at line {start_line}, text: {full_text!r}")
        entity = {
            "type": self.entity_type,
            "name": name_final,
            "visibility": vis,
            "file_id": self.owner.file_id,
            "first_line": start_line,
            "tokens": estimate_tokens(full_text)
        }
        if not self.owner.add_entity(start_line, entity):
            return False
        self.new_entities_lines.append(start_line)

        # Recursive parsing for module contents
        module_lines = self.owner.extract_entity_text(match.start(), match.end()).splitlines()
        module_size = len(module_lines)
        sub_clean_lines = self.owner.clean_lines.copy()
        end_line = start_line + module_size
        for i in range(0, len(sub_clean_lines)):
            if i < start_line + 1 or i > end_line - 1:
                sub_clean_lines[i] = f"// ext. line #{i}"
        masked_content = "\n".join(sub_clean_lines[1:])
        sub_parser = ContentCodeRust(
            masked_content, self.owner.content_type,
            f"{self.owner.file_name}&{module_name}", self.owner.timestamp,
            module_prefix=f"{self.owner.module_prefix}{module_name}."
        )
        sub_result = sub_parser.parse_content(sub_clean_lines, depth=1)
        for sub_entity in sub_result["entities"]:
            if isinstance(sub_entity, dict):
                first_line = sub_entity['first_line']
                if first_line in self.owner.entity_map:
                    logging.error(f"Already exists entity {self.owner.entity_map[first_line]}, can't add {sub_entity}")
                    continue
                self.owner.entity_map[first_line] = sub_entity
                self.new_entities_lines.append(first_line)
        for d in ['modules', 'imports', 'calls']:
            self.dependencies[d].extend(sub_result["dependencies"][d])
        return True

    def masquerade(self):
        clean_lines = self.owner.clean_lines.copy()
        for line_num in self.new_entities_lines:
            start_line, end_line = self.owner.detect_bounds(line_num, clean_lines)
            e = self.owner.entity_map[line_num]
            clean_lines[line_num] = re.sub(self.mask_pattern, e['type'], clean_lines[line_num])
            for i in range(line_num + 1, end_line):
                clean_lines[i] = f"// module line {i}"
        return clean_lines


class TraitImplParser(EntityParser):
    """Parser for Rust trait implementations and their methods."""
    def __init__(self, entity_type, owner):
        super().__init__(entity_type, owner, IMPL_REGEX, r"\bimpl\b|\bfn\b", FN_REGEX, default_visibility="private")

    def _format_entity_name(self, match):
        name = match.group('name')
        struct_name = match.group('struct_name')
        return self.owner.module_prefix + f"{name}<{struct_name}>"


class ContentCodeRust(ContentBlock):
    """Parser for Rust content blocks."""
    supported_types = [".rs"]

    def __init__(self, content_text: str, content_type: str, file_name: str, timestamp: str, **kwargs):
        super().__init__(content_text, content_type, file_name, timestamp, **kwargs)
        self.tag = "rustc"
        self.entity_map = {}
        self.raw_str_prefix = "r"
        self.open_ml_string = ["r#\""]
        self.close_ml_string = ["\"#"]
        self.module_prefix = kwargs.get("module_prefix", "")
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

    def parse_content(self, clean_lines=None, depth=0):
        """Parses Rust content to extract entities and dependencies."""
        logging.debug(f"Parsing content at depth {depth} for file {self.file_name}")
        if depth >= 2:
            self.parse_warn(f"Maximum recursion depth reached for file {self.file_name}")
            return {"entities": [], "dependencies": {"modules": [], "imports": [], "calls": []}}
        self.entity_map = {}
        dependencies = {"modules": [], "imports": [], "calls": []}
        self.clean_lines = clean_lines if clean_lines is not None else ([""] + self.content_text.splitlines())
        self.strip_strings()
        self.strip_comments()

        parsers = [
            ModuleParser("module", self),
            EntityParser("structure", self, STRUCT_REGEX, r"\bstruct\b", default_visibility="private"),
            EntityParser("interface", self, TRAIT_REGEX, r"\btrait\b|\bfn\b", FN_TRAIT_REGEX, default_visibility="private"),
            TraitImplParser("class", self),
            EntityParser("function", self, FN_REGEX, r"\bfn\b", default_visibility="private")
        ]

        for parser in parsers:
            try:
                if parser.parse():
                    parser_deps = getattr(parser, "dependencies", {"modules": [], "imports": [], "calls": []})
                    dependencies["modules"].extend(parser_deps["modules"])
                    dependencies["imports"].extend(parser_deps["imports"])
                    dependencies["calls"].extend(parser_deps["calls"])
                    self.clean_lines = parser.masquerade()
                    logging.debug(f"Applied {parser.__class__.__name__} parser, new clean_lines[1:10]: {self.clean_lines[1:10]}")
            except Exception as e:
                logging.error(f"Error in {parser.__class__.__name__} parser for {self.file_name}: {str(e)}")
                traceback.print_exc()
                break

        entities = self.sorted_entities()
        logging.debug(f"Parsed {len(entities)} entities in {self.file_name}")
        return {"entities": entities, "dependencies": {k: sorted(list(set(v))) for k, v in dependencies.items()}}

SandwichPack.register_block_class(ContentCodeRust)