# /lib/js_block.py, updated 2025-08-08 18:45 EEST
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

INDENT_PART = r"^(?P<indent>[ \t]*)(?:import\s+)?"
EXPORT_PART = r"(?:export\s+(?:default\s+)?)?"
BASE_REGEX_PATTERN = INDENT_PART + EXPORT_PART
FN_VARIANTS = [r"(?:function\s+(?P<name>\w+)\s*\((?P<args>[^\)]*)\)",
               r"const\s+(?P<name2>\w+)\s*=\s*(?:async\s+)?function\s*\w*\s*\((?P<args2>[^\)]*)\)",
               r"const\s+(?P<name3>\w+)\s*=\s*\((?P<args3>[^\)]*)\)\s*=>)"]

FN_REGEX_PATTERN = r"(?:const\s+(?P<name>\w+)\s*=\s*)?(?P<async>async\s+)?(?:function\s*(?P<name2>\w+)?)?\("
CLASS_REGEX_PATTERN = r"class\s+(?P<name>\w+)"
INTERFACE_REGEX_PATTERN = r"interface\s+(?P<name>\w+)"
OBJECT_REGEX_PATTERN = r"const\s+(?P<name>\w+)\s*="
METHODS_REGEX_PATTERN = r"(?:methods|computed|watch)\s*:"

class ObjectParser(EntityParser):
    """Parser for JavaScript object declarations."""
    def __init__(self, entity_type, owner):
        outer_regex = IterativeRegex()
        outer_regex.add_token(BASE_REGEX_PATTERN + OBJECT_REGEX_PATTERN, ["indent", "name"], 2)
        outer_regex.add_token(r"\s*{", ["head_end"], 1)
        super().__init__(entity_type, owner, outer_regex, r"\bconst\b|\bexport\b", default_visibility="public")

    def _format_entity_name(self, match):
        name = match.group('name') or "default"
        return self.owner.module_prefix + name

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
            vis = self.default_visibility
            full_text = self.owner.extract_entity_text(match.start(), match.end())
            extra_fields = {"parent": ""}
            self.make_add_entity(self.entity_type, name, vis, start_line, full_text, extra_fields)
        return True


class MethodParser(EntityParser):
    """Parser for JavaScript methods inside objects."""
    def __init__(self, entity_type, owner):
        outer_regex = IterativeRegex()
        outer_regex.add_token(
            r"^(?P<indent>[ \t]*)(?P<spec>" + METHODS_REGEX_PATTERN + r")", ["indent", "spec", "name", "args"], 2
        ).add_token(r"\s*{", ["head_end"], 1)
        super().__init__(entity_type, owner, outer_regex, r"\bmethods\b|\bcomputed\b|\bwatch\b|\bfn\b", default_visibility="public")
        self.inner_regex = IterativeRegex()
        self.inner_regex.add_token(
            r"^\s*(?P<name>\w+)\s*\((?P<args>[^)]*)\)", ["name", "args"], 2
        ).add_token(
            r"\s*{", ['head_end'], 1
        )

    def _format_entity_name(self, match):
        return "methods" if self else "trash"

    def parse(self):
        # TODO: AI generated strange code, need reintegration to ObjectParser
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
            indent = len(match_value(match, 'indent', ''))
            parent = ""
            for line_num in range(start_line - 1, 0, -1):
                line = self.owner.clean_lines[line_num]
                if not isinstance(line, str) or not line.strip():
                    continue
                line_indent = len(line) - len(line.lstrip())
                if line_indent < indent and '{' in line:
                    parent_entity = self.owner.entity_map.get(line_num, {})
                    if parent_entity.get('type') == 'object':
                        parent = parent_entity['name']
                        break

            full_text = self.owner.extract_entity_text(match.start(), match.end())
            logging.debug(f"Methods part: {full_text}")
            self.parse_inner(full_text, start_line, parent)
            # self.make_add_entity(self.entity_type, name, vis, start_line, full_text, extra_fields)
        return True


class FunctionParser(EntityParser):
    """Parser for JavaScript functions."""
    def __init__(self, entity_type, owner):
        outer_regex = IterativeRegex()
        outer_regex.add_token(
            BASE_REGEX_PATTERN + FN_REGEX_PATTERN, ["indent", "async", "name", "name2"], 2
        ).add_token(
            r"(?P<args>[^\)]*)\)(?:\s*=>)?\s*{", ["args"], 1
        ).add_token(r"\s*{", ["head_end"], 1)
        super().__init__(entity_type, owner, outer_regex, r"\bfunction\b|\bconst\b", default_visibility="public")

    def _format_entity_name(self, match):
        return match.group('name') or match.group('name2') or match.group('name3')

    def parse(self):
        content = self.owner.get_clean_content()
        for base_match in self.outer_regex.all_matches(content):
            start_pos = base_match.start()   # begin of declaration
            start_line = self.owner.find_line(start_pos)
            validation = self.outer_regex.validate_match(content, start_pos)
            if validation['hit_rate'] < 0.5:
                logging.debug(f"Skipping low hit_rate {validation['hit_rate']} for match at {start_line}")
                continue
            match = validation['match']
            if not match:
                continue
            name = self._format_entity_name(match)
            full_text = self.owner.extract_entity_text(match.start(), match.end())
            extra_fields = {"parent": ""}
            self.make_add_entity(self.entity_type, self.owner.module_prefix + name, self.default_visibility, start_line, full_text, extra_fields)
        return True


class InterfaceParser(EntityParser):
    """Parser for TypeScript interfaces."""
    def __init__(self, entity_type, owner):
        outer_regex = IterativeRegex()
        outer_regex.add_token(BASE_REGEX_PATTERN + INTERFACE_REGEX_PATTERN, ["indent", "vis", "name"], 2)
        outer_regex.add_token(r"\s+extends\s+(?P<parent>\w+)", ["parent"], 1)
        outer_regex.add_token(r"\s*{", ["head_end"], 1)
        super().__init__(entity_type, owner, outer_regex, r"\binterface\b", default_visibility="public")


class ClassParser(EntityParser):
    """Parser for JavaScript/TypeScript classes."""
    def __init__(self, entity_type, owner):
        outer_regex = IterativeRegex()
        outer_regex.add_token(BASE_REGEX_PATTERN + CLASS_REGEX_PATTERN, ["indent", "vis", "name"], 2)
        outer_regex.add_token(r"\s+extends\s+(?P<parent>\w+)", ["parent"], 1)
        outer_regex.add_token(r"\s*{", ["head_end"], 1)
        super().__init__(entity_type, owner, outer_regex, r"\bclass\b", default_visibility="public")


class DepsParserJs(DepsParser):
    """Parser for JavaScript/TypeScript imports."""
    def __init__(self, owner):
        outer_regex = IterativeRegex()
        outer_regex.add_token(r"^(?P<indent>[ \t]*)import\s+{?(?P<items>[\w,\s]+)}?\s+from\s+['\"](?P<module>[^'\"]+)['\"]", ["indent", "items", "module"], 2)
        inner_regex = IterativeRegex()
        inner_regex.add_token(r"(?P<name>\w+)\s*(?:,|$)", ["name"], 1)
        super().__init__(owner, outer_regex)
        self.inner_regex = inner_regex

    def _process_match(self, match):
        module = match.group('module')
        if module:
            self.add_module(module)
        items = match.group('items')
        if items:
            content = items.strip()
            for inner_match in self.inner_regex.all_matches(content):
                validation = self.inner_regex.validate_match(content, inner_match.start())
                if validation['hit_rate'] < 0.5:
                    continue
                inner_match = validation['match']
                if inner_match:
                    item = inner_match.group('name')
                    self.add_import(module, item)


class ContentCodeJs(ContentBlock):
    """Parser for JavaScript content blocks."""
    supported_types = [".js"]

    def __init__(self, content_text: str, content_type: str, file_name: str, timestamp: str, **kwargs):
        super().__init__(content_text, content_type, file_name, timestamp, **kwargs)
        self.tag = "js"
        self.open_ml_string = ["`"]
        self.close_ml_string = ["`"]
        self.entity_map = {}
        self.module_prefix = kwargs.get("module_prefix", "")
        logging.debug(f"Initialized ContentCodeJs with tag={self.tag}, file_name={file_name}, module_prefix={self.module_prefix}")

    def parse_content(self, clean_lines=None, depth=0):
        """Parses JavaScript content to extract entities and dependencies."""
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
            FunctionParser("function", self),
            ObjectParser("object", self),
            MethodParser("method", self),
            DepsParserJs(self)
        ]

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


class ContentCodeTypeScript(ContentCodeJs):
    """Parser for TypeScript content blocks."""
    supported_types = [".ts"]

    def __init__(self, content_text: str, content_type: str, file_name: str, timestamp: str, **kwargs):
        super().__init__(content_text, content_type, file_name, timestamp, **kwargs)
        self.tag = "tss"
        logging.debug(f"Initialized ContentCodeTypeScript with tag={self.tag}, file_name={file_name}, module_prefix={self.module_prefix}")

    def parse_content(self, clean_lines=None, depth=0):
        """Parses TypeScript content to extract entities and dependencies."""
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
            FunctionParser("function", self),
            ObjectParser("object", self),
            MethodParser("method", self),
            InterfaceParser("interface", self),
            ClassParser("class", self),
            DepsParserJs(self)
        ]

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


SandwichPack.register_block_class(ContentCodeJs)
SandwichPack.register_block_class(ContentCodeTypeScript)