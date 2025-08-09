# /lib/shellscript_block.py, updated 2025-08-08 18:30 EEST
# Formatted with proper line breaks and indentation for project compliance.

import re
import os
import logging
import traceback
from pathlib import Path
from lib.content_block import ContentBlock, estimate_tokens
from lib.sandwich_pack import SandwichPack
from lib.entity_parser import EntityParser
from lib.deps_builder import DepsParser
from lib.iter_regex import IterativeRegex


class FunctionParser(EntityParser):
    """Parser for Shell script functions."""
    def __init__(self, entity_type, owner):
        outer_regex = IterativeRegex()
        outer_regex.add_token(
            r"^(?P<indent>\s*)(?:function\s+)?(?P<name>\w+)\s*\(\)", ["indent", "name"], 2
        ).add_token(
            r"\s*{", ["head_end"], 1
        )
        super().__init__(entity_type, owner, outer_regex, r"\bfunction\b", default_visibility="private")

    def parse(self):
        content = self.owner.get_clean_content()
        matches = list(self.outer_regex.all_matches(content))
        exported_functions = set()
        export_regex = IterativeRegex()
        export_regex.add_token(r"^\s*export\s+-f\s+(?P<name>\w+)", ["name"], 1)
        for match in export_regex.all_matches(self.owner.content_text):
            validation = export_regex.validate_match(self.owner.content_text, match.start())
            if validation['hit_rate'] >= 0.5 and validation['match']:
                exported_functions.add(validation['match'].group('name'))

        for match in matches:
            fn_name = match.group('name')
            vis = "public" if fn_name in exported_functions else self.default_visibility
            start_pos = match.start('name')
            start_line = self.owner.find_line(start_pos)
            full_text = self.owner.extract_entity_text(start_pos, match.end())
            self.make_add_entity(self.entity_type, fn_name, vis, start_line, full_text)
        return True


class DepsParserShell(DepsParser):
    """Parser for Shell script dependencies."""
    def __init__(self, owner):
        outer_regex = IterativeRegex()
        outer_regex.add_token(r"^\s*(?:\.|source|\./)\s+(?P<script>[^\s]+)", ["script"], 1)
        super().__init__(owner, outer_regex)

    def _process_match(self, match):
        script = match.group('script')
        if script:
            script_path = f"{Path(self.owner.file_name).parent}/{script}".replace("\\", "/")
            if not script_path.startswith("/"):
                script_path = f"/{script_path}"
            self.add_module(script_path)


class ContentShellScript(ContentBlock):
    """Parser for Shell script content blocks."""
    supported_types = [".sh"]

    def __init__(self, content_text: str, content_type: str, file_name: str, timestamp: str, **kwargs):
        super().__init__(content_text, content_type, file_name, timestamp, **kwargs)
        self.tag = "shell"
        self.entity_map = {}
        self.open_sl_comment = ["#"]
        logging.debug(f"Initialized ContentShellScript with tag={self.tag}, file_name={file_name}")

    def parse_content(self, clean_lines=None, depth=0):
        """Parses shell script content to extract entities and dependencies."""
        logging.debug(f"Parsing content at depth {depth} for file {self.file_name}")
        if depth >= 2:
            self.parse_warn(f"Maximum recursion depth reached for file {self.file_name}")
            return {"entities": [], "dependencies": {"modules": [], "imports": {}}}
        self.entity_map = {}
        self.dependencies = {"modules": [], "imports": {}}
        self.clean_lines = clean_lines if clean_lines is not None else ([""] + self.content_text.splitlines())
        self.strip_strings()
        self.strip_comments()

        parsers = [FunctionParser("function", self), DepsParserShell(self)]
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


SandwichPack.register_block_class(ContentShellScript)