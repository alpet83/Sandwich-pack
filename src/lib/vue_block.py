# /lib/vue_block.py, updated 2025-08-08 18:45 EEST
# Formatted with proper line breaks and indentation for project compliance.

import re
import os
import logging
import traceback
from lib.content_block import ContentBlock, estimate_tokens
from lib.sandwich_pack import SandwichPack
from lib.entity_parser import EntityParser
from lib.deps_builder import DepsParser
from lib.iter_regex import IterativeRegex
from lib.js_block import MethodParser, FunctionParser, DepsParserJs

METHODS_REGEX_PATTERN = r"^(?P<indent>[ \t]*)(?:methods|computed|watch)\s*:"

class ComponentParser(EntityParser):
    """Parser for Vue components."""
    def __init__(self, entity_type, owner):
        outer_regex = IterativeRegex()
        outer_regex.add_token(r"^(?P<indent>[ \t]*)(?:const\s+(?P<name>\w+)\s*=\s*)?defineComponent\s*\(\s*{", ["indent", "name"], 2)
        super().__init__(entity_type, owner, outer_regex, r"\bdefineComponent\b", default_visibility="public")

    def parse(self):
        content = self.owner.get_clean_content()
        matches = list(self.outer_regex.all_matches(content))
        if not matches:
            logging.warning(f"No VUE components created via defineComponent in {self.owner.file_name}, used content:\n{content}")
        for match in matches:
            name = match.group('name') or "VueComponent"
            start_pos = match.start('name') if match.group('name') else match.start()
            start_line = self.owner.find_line(start_pos)
            vis = self.default_visibility
            full_text = self.owner.extract_entity_text(start_pos, match.end())
            logging.debug(f"Attempting to add component {name} at line {start_line}, text: {full_text!r}")
            extra_fields = {"parent": ""}
            self.make_add_entity(self.entity_type, self.owner.module_prefix + name, vis, start_line, full_text, extra_fields)

        return True


class ContentCodeVue(ContentBlock):
    """Parser for Vue content blocks."""
    supported_types = [".vue"]

    def __init__(self, content_text: str, content_type: str, file_name: str, timestamp: str, **kwargs):
        super().__init__(content_text, content_type, file_name, timestamp, **kwargs)
        self.tag = "vue"
        self.string_quote_chars = "\"'`"
        self.open_ml_string = ["`"]
        self.close_ml_string = ["`"]
        self.entity_map = {}
        self.module_prefix = kwargs.get("module_prefix", "")
        logging.debug(f"Initialized ContentCodeVue with tag={self.tag}, file_name={file_name}, module_prefix={self.module_prefix}")

    def parse_content(self, clean_lines=None, depth=0):
        """Parses Vue content to extract entities and dependencies."""
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
            ComponentParser("component", self),
            MethodParser("method", self),
            FunctionParser("function", self),
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


SandwichPack.register_block_class(ContentCodeVue)