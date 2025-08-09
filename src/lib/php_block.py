# /lib/php_block.py, updated 2025-08-08 18:30 EEST
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

BASE_REGEX_PATTERN = r"^(?P<indent>[ \t]*)(?P<vis>public\s+|protected\s+|private\s+)?"
ARGS_REGEX_PATTERN = r"(?P<args>[\^)]*)"


callable_regex = IterativeRegex()
callable_regex.add_token(
    BASE_REGEX_PATTERN + r"function\s+(?P<name>\w+)\s*\(",
    ["indent", "vis", "name"], 2
).add_token(
    ARGS_REGEX_PATTERN + r"\)", ["args"], 1
).add_token(
    r"\s*(?P<ending>{|;)", ["head_end"], 1
)


class ClassParser(EntityParser):
    """Parser for PHP classes and their methods."""
    def __init__(self, entity_type, owner):
        outer_regex = IterativeRegex()
        outer_regex.add_token(
            BASE_REGEX_PATTERN + r"class\s+(?P<name>\w+)(?P<parent>\s+extends\s+\w+)?",
            ["indent", "vis", "name"], 2
        ).add_token(
            r"\s*:", ["head_end"], 1
        )
        super().__init__(entity_type, owner, outer_regex, r"\bclass\b", inner_regex=callable_regex, default_visibility="public")


class FunctionParser(EntityParser):
    """Parser for PHP functions."""
    def __init__(self, entity_type, owner):
        super().__init__(entity_type, owner, callable_regex, r"\bfunction\b", default_visibility="public")


class DepsParserPHP(DepsParser):
    """Parser for PHP imports."""
    def __init__(self, owner):
        outer_regex = IterativeRegex()
        outer_regex.add_token(
            r"^(?P<indent>[ \t]*)(require|include|require_once|include_once)\s+",
            ["indent", "base"], 2
        ).add_token(
            r"\(*\s*['\"]+(?P<module>\w+).php['\"]+\)*", ["module"], 1
        )
        super().__init__(owner, outer_regex)

    def _process_match(self, match):
        validation = self.outer_regex.validate_match(self.content, match.start())
        hit_rate = validation['hit_rate']
        if hit_rate < 0.5:
            return
        module = match_value(validation["match"], 'module')
        if module:
            self.add_module(module)

class ContentCodePHP(ContentBlock):
    """Parser for PHP content blocks."""
    supported_types = [".php"]

    def __init__(self, content_text: str, content_type: str, file_name: str, timestamp: str, **kwargs):
        super().__init__(content_text, content_type, file_name, timestamp, **kwargs)
        self.tag = "php"
        self.raw_quote_char = "'"
        self.string_quote_chars = "\"'"
        self.open_ml_string = []
        self.close_ml_string = []
        self.open_sl_comment = ["//", "#"]
        self.open_ml_comment.append(r"\?>")
        self.close_ml_comment.append(r"<\?php")
        self.escape_char = "\\"
        self.entity_map = {}
        self.module_prefix = kwargs.get("module_prefix", "")
        logging.debug(f"Initialized ContentCodePHP with tag={self.tag}, file_name={file_name}, module_prefix={self.module_prefix}")



    def strip_strings(self):
        """Strips string literals from PHP content, preserving module names in require/include."""
        if len(self.clean_lines) <= 1:
            raise Exception("clean_lines not filled")
        content = self.content_text

        #  Very matter quotes duplication for import lines
        protected_content = re.sub(
            r"^(?P<indent>[ \t]*)(require|include|require_once|include_once)\s+\(*['\"]([^'^\"]+)['\"]\)*",
            r'\g<indent>\g<2> ""\g<3>"" // import preserved',
            content,
            flags=re.MULTILINE
        )
        self.clean_lines = [''] + protected_content.splitlines()
        super().strip_strings()


    def check_raw_escape(self, line: str, position: int, quote_char: str) -> bool:
        """Checks if the character at position is part of a PHP raw string escape sequence."""
        if position + 1 < len(line) and line[position] == self.escape_char:
            next_char = line[position + 1]
            return next_char == quote_char or next_char == self.escape_char
        return False

    def parse_content(self, clean_lines=None, depth=0):
        """Parses PHP content to extract entities and dependencies."""
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
            DepsParserPHP(self)
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


SandwichPack.register_block_class(ContentCodePHP)