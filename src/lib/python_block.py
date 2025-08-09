# /lib/python_block.py, updated 2025-08-08 15:27 EEST
# Formatted with proper line breaks and indentation for project compliance.

import re
import os
import logging
import traceback
from pathlib import Path
from lib.content_block import ContentBlock, estimate_tokens
from lib.sandwich_pack import SandwichPack
from lib.entity_parser import EntityParser, match_value
from lib.deps_builder import DepsParser
from lib.iter_regex import IterativeRegex


BASE_REGEX_PATTERN = r"^(?P<indent>[ \t]*)(?P<spec>@classmethod\s+|@staticmethod\s+)?(?:@[\w\s()]+)?(?P<async>async\s+)?"
FN_REGEX_PATTERN = r"def\s+(?P<name>\w+)"
CLASS_REGEX_PATTERN = r"class\s+(?P<name>\w+)"


class ClassParser(EntityParser):
    """Parser for Python classes."""
    def __init__(self, entity_type, owner):
        outer_regex = IterativeRegex()
        outer_regex.add_token(BASE_REGEX_PATTERN + CLASS_REGEX_PATTERN, ["indent", "spec", "async", "name"], 2)
        outer_regex.add_token(r"\s*\((?P<parent>\w+)\)", ["parent"], 1)
        outer_regex.add_token(r"\s*:", ["head_end"], 1)
        super().__init__(entity_type, owner, outer_regex, r"\bclass\b", default_visibility="public")

    def parse(self):
        content = self.owner.get_clean_content()
        for base_match in self.outer_regex.all_matches(content):
            start_pos = base_match.start()
            start_line = self.owner.find_line(start_pos)
            validation = self.outer_regex.validate_match(content, start_pos)
            if validation['hit_rate'] < 0.5:
                logging.debug(f"Skipping low hit_rate {validation['hit_rate']} for match at {start_line}")
                continue
            match = validation['match']
            if not match:
                continue
            name = match.group('name')
            vis = "public" if not name.startswith('_') else "private" if name.startswith('__') else "protected"
            full_text = self.owner.extract_entity_text(match.start(), match.end())
            parent = match_value(match, 'parent', '')
            indent = match_value(match, 'indent', '')
            extra_fields = {"indent": len(indent), "parent": parent}
            self.make_add_entity(self.entity_type, self.owner.module_prefix + name, vis, start_line, full_text, extra_fields)
        return True


class FunctionParser(EntityParser):
    """Parser for Python functions and methods."""
    def __init__(self, entity_type, owner):
        outer_regex = IterativeRegex()
        outer_regex.add_token(BASE_REGEX_PATTERN + FN_REGEX_PATTERN, ["indent", "spec", "async", "name"], 2)
        outer_regex.add_token(r"\s*\([^)]*\)\s*", ["args"], 1)
        outer_regex.add_token(r"(?::\s*[\w\s\[\],]+)?\s*:", ["return"], 1)
        super().__init__(entity_type, owner, outer_regex, r"\bdef\b", default_visibility="public")

    def _format_entity_name(self, match):
        return match.group('name')

    def parse(self):
        content = self.owner.get_clean_content()
        for base_match in self.outer_regex.all_matches(content):
            start_pos = base_match.start()
            start_line = self.owner.find_line(start_pos)
            validation = self.outer_regex.validate_match(content, start_pos)
            if validation['hit_rate'] < 0.5:
                logging.debug(f"Skipping low hit_rate {validation['hit_rate']} for match at {start_line}")
                continue
            match = validation['match']
            if not match:
                continue
            name = self._format_entity_name(match)
            indent = len(match.group('indent'))
            vis = "public" if not name.startswith('_') else "private" if name.startswith('__') else "protected"
            spec = match.group('spec') or ""
            entity_type = self.entity_type
            parent = ""
            for line_num in range(start_line - 1, 0, -1):
                line = self.owner.clean_lines[line_num]
                if not isinstance(line, str) or not line.strip():
                    continue
                line_indent = len(line) - len(line.lstrip())
                if line_indent < indent:
                    line = line.strip()
                    if line.startswith('class '):
                        parent = line.split('class ')[1].split('(')[0].split(':')[0].strip()  # TODO: may be changed to regex
                        entity_type = "class method" if spec == "@classmethod" else "static method" if spec == "@staticmethod" else "method"
                    elif line.startswith('def '):
                        entity_type = 'local_function'
                    break
            if self.owner.include_decorators and spec:
                for i in range(start_line - 1, 0, -1):
                    if self.owner.clean_lines[i].strip().startswith('@'):
                        start_line = i
                        break
            full_text = self.owner.extract_entity_text(match.start(), match.end())
            extra_fields = {"indent": indent, "parent": parent}
            self.make_add_entity(entity_type, self.owner.module_prefix + name, vis, start_line, full_text, extra_fields)
        return True


class DepsParserPython(DepsParser):
    """Parser for Python imports."""
    def __init__(self, owner):
        super().__init__(owner, None)

    def parse(self):
        clean_content = self.owner.get_clean_content()
        import_regex = re.compile(
            r"^(?P<indent>[ \t]*)(?:from\s+([\w.]+)\s+import\s+([\w,\s]+)|import\s+(\w+))\s*$",
            re.MULTILINE
        )
        for match in import_regex.finditer(clean_content):
            module = match.group(2) or match.group(4)
            if module:
                self.add_module(module)
                logging.debug(f"Found module: {module}")
            items = match.group(3)
            if items:
                imports = [item.strip() for item in items.split(",") if item.strip()]
                for item in imports:
                    self.add_import(module, item)
        return True


class ContentCodePython(ContentBlock):
    """Parser for Python content blocks."""
    supported_types = [".py"]

    def __init__(self, content_text: str, content_type: str, file_name: str, timestamp: str, include_decorators: bool = False, **kwargs):
        super().__init__(content_text, content_type, file_name, timestamp, **kwargs)
        self.tag = "python"
        self.include_decorators = include_decorators
        self.open_ml_string = ['"""', "'''"]
        self.close_ml_string = ['"""', "'''"]
        self.open_sl_comment = ["#"]
        self.open_ml_comment = ['"""', "'''"]
        self.close_ml_comment = ['"""', "'''"]
        self.entity_map = {}
        self.module_prefix = kwargs.get("module_prefix", "")
        logging.debug(f"Initialized ContentCodePython with tag={self.tag}, file_name={file_name}, module_prefix={self.module_prefix}, include_decorators={include_decorators}")

    def detect_bounds(self, start_line, clean_lines):
        """Detects the start and end line of an entity using indentation levels.

        Args:
            start_line (int): Initial line number of the entity header.
            clean_lines (list): List of cleaned lines.

        Returns:
            tuple: (start_line, last_line) of the entity.
        """
        if start_line < 1 or start_line >= len(clean_lines) or not clean_lines[start_line] or not clean_lines[start_line].strip():
            logging.error(f"DETECT_BOUNDS: Invalid start line {start_line} for file {self.file_name} module [{self.module_prefix}]")
            return start_line, start_line

        # Search for the line ending with a colon (:) within 8 lines from start_line
        header_last_line = start_line
        for i in range(start_line, min(start_line + 8, len(clean_lines))):
            line = clean_lines[i]
            if not isinstance(line, str) or not line.strip():
                continue
            if line.strip().endswith(':'):
                header_last_line = i
                break

        line = clean_lines[header_last_line]
        indent = len(line) - len(line.lstrip())
        line_num = header_last_line
        last_line = header_last_line
        while line_num < len(clean_lines):
            line = clean_lines[line_num]
            if not isinstance(line, str) or not line.strip():
                line_num += 1
                continue
            line_indent = len(line) - len(line.lstrip())
            for other_entity in self.entity_map.values():
                if other_entity["first_line"] == line_num and other_entity["indent"] <= indent:
                    return header_last_line, last_line
            if line_indent <= indent and line_num > header_last_line:
                logging.debug(f"DETECT_BOUNDS: new indent {line_indent} <= {indent} at @{line_num}")
                return header_last_line, last_line
            if line_indent > indent:
                last_line = line_num
            line_num += 1
        return header_last_line, last_line

    def parse_content(self, clean_lines=None, depth=0):
        """Parses Python content to extract entities and dependencies."""
        logging.debug(f"Parsing content at depth {depth} for file {self.file_name}")
        if depth >= 2:
            self.parse_warn(f"Maximum recursion depth reached for file {self.file_name}")
            return {"entities": [], "dependencies": {"modules": [], "imports": {}}}
        self.entity_map = {}
        self.dependencies = {"modules": [], "imports": {}}
        self.clean_lines = clean_lines if clean_lines is not None else ([""] + self.content_text.splitlines())
        self.strip_strings()
        self.strip_comments()

        parsers = [
            ClassParser("class", self),
            FunctionParser("function", self),
            DepsParserPython(self)
        ]
        self.parsers = parsers

        original_clean_lines = self.clean_lines.copy()
        for parser in parsers:
            try:
                self.clean_lines = original_clean_lines.copy()
                if parser.parse():
                    self.extend_deps(parser)
                    self.clean_lines = parser.masquerade()
                    logging.debug(f"Applied {parser.__class__.__name__} parser, new clean_lines[1:10]: {self.clean_lines[1:10]}")
            except Exception as e:
                logging.error(f"Error in {parser.__class__.__name__} parser for {self.file_name}: {str(e)}")
                traceback.print_exc()
                break

        self.clean_lines = original_clean_lines
        entities = self.sorted_entities()
        logging.debug(f"Parsed {len(entities)} entities in {self.file_name}")
        return {"entities": entities, "dependencies": self.dependencies}


SandwichPack.register_block_class(ContentCodePython)