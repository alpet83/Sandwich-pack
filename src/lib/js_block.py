# /lib/js_block.py, updated 2025-08-02 12:45 EEST
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
    """Generate and compile a regex pattern for parsing JavaScript/TypeScript entities.

    Args:
        token (str): The primary token for the entity (e.g., 'function', 'const', 'interface', 'class').
        extra (str, optional): Additional regex pattern to append (e.g., for parameters, generics, or block endings).

    Returns:
        re.Pattern: Compiled regex pattern.

    Raises:
        re.error: If the pattern is invalid, logs the error with token and extra.
    """
    base = r"^(?P<indent>[ \t]*)(?:export\s+(?:default\s+)?)?(?:@[\w\s()]+)?(?P<vis>const\s+|var\s+|let\s+)?%s\s+(?P<name>\w+)" % token
    pattern = base + (extra if isinstance(extra, str) else r"\s*{")
    try:
        return re.compile(pattern, re.MULTILINE)
    except re.error as e:
        logging.error(f"Failed to compile regex for token={token}, extra={extra}: {str(e)}")
        raise

# Regular expression constants
OBJECT_REGEX = re.compile(
    r"^(?P<indent>[ \t]*(?!import\s+))(?:(?P<vis>const\s+|var\s+|let\s+)(?P<name>\w+)\s*=\s*{|export\s+default\s*{)",
    re.MULTILINE
)
METHOD_REGEX = re.compile(r"^(?P<indent>[ \t]*)(?:methods|computed|watch)\s*:\s*{\s*[^}]*\b(?P<name>\w+)\s*\(\s*\)\s*{", re.MULTILINE)
FUNCTION_REGEX = re.compile(
    r"^(?P<indent>[ \t]*)(?P<vis>const\s+|var\s+|let\s+)?(?:function\s+(?P<name>\w+)\s*\(\s*\)\s*\{|const\s+(?P<name2>\w+)\s*=\s*(?:async\s+)?function\s*\w*\s*\(\s*\)\s*\{|const\s+(?P<name3>\w+)\s*=\s*\([^)]*\)\s*=>\s*\{)",
    re.MULTILINE
)
IMPORT_REGEX = re.compile(r"^(?P<indent>[ \t]*)import\s+{?([\w,\s]+)}?\s+from\s+['\"]([^'\"]+)['\"]|require\s*\(['\"]([^'\"]+)['\"]\)", re.MULTILINE)
INTERFACE_REGEX = build_regex("interface", r"(?:\s+extends\s+\w+)?\s*{")
CLASS_REGEX = build_regex("class", r"(?:\s+extends\s+\w+)?\s*{")


class ObjectParser(EntityParser):
    """Parser for JavaScript object declarations."""
    def __init__(self, entity_type, owner):
        super().__init__(entity_type, owner, OBJECT_REGEX, r"\bconst\b|\bexport\b", default_visibility="public")

    def _format_entity_name(self, match):
        name = match.group('name') or "default"
        return self.owner.module_prefix + name


class MethodParser(EntityParser):
    """Parser for JavaScript methods inside objects."""
    def __init__(self, entity_type, owner):
        super().__init__(entity_type, owner, METHOD_REGEX, r"\bmethods\b|\bcomputed\b|\bwatch\b|\bfn\b", inner_regex=None, default_visibility="public")


class FunctionParser(EntityParser):
    """Parser for JavaScript functions."""
    def __init__(self, entity_type, owner):
        super().__init__(entity_type, owner, FUNCTION_REGEX, r"\bfunction\b|\b=>\b", default_visibility="public")

    def _format_entity_name(self, match):
        name = match.group('name') or match.group('name2') or match.group('name3')
        return self.owner.module_prefix + name


class ImportParser:
    """Parser for JavaScript/TypeScript imports."""
    def __init__(self, owner):
        self.owner = owner
        self.pattern = IMPORT_REGEX
        self.dependencies = {"modules": [], "imports": [], "calls": []}

    def parse(self):
        clean_content = self.owner.get_clean_content()
        for match in self.pattern.finditer(clean_content):
            items = [item.strip() for item in match.group(2).split(",")] if match.group(2) else []
            module = match.group(3) or match.group(4)
            for item in items:
                self.dependencies["imports"].append(item)
            if module:
                self.dependencies["modules"].append(module)
        return True

    def masquerade(self):
        return self.owner.clean_lines.copy()


class InterfaceParser(EntityParser):
    """Parser for TypeScript interfaces."""
    def __init__(self, entity_type, owner):
        super().__init__(entity_type, owner, INTERFACE_REGEX, r"\binterface\b", default_visibility="public")


class ClassParser(EntityParser):
    """Parser for TypeScript classes."""
    def __init__(self, entity_type, owner):
        super().__init__(entity_type, owner, CLASS_REGEX, r"\bclass\b", default_visibility="public")


class ContentCodeJs(ContentBlock):
    """Parser for JavaScript content blocks."""
    supported_types = [".js"]

    def __init__(self, content_text: str, content_type: str, file_name: str, timestamp: str, **kwargs):
        super().__init__(content_text, content_type, file_name, timestamp, **kwargs)
        self.tag = "jss"
        self.string_quote_chars = "\"'`"
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
            return {"entities": [], "dependencies": {"modules": [], "imports": [], "calls": []}}
        self.entity_map = {}
        dependencies = {"modules": [], "imports": [], "calls": []}
        self.clean_lines = clean_lines if clean_lines is not None else ([""] + self.content_text.splitlines())
        self.strip_strings()
        self.strip_comments()

        # Process parsers in order to ensure stable clean_lines
        parsers = [
            FunctionParser("function", self),
            ObjectParser("object", self),
            MethodParser("method", self),
            ImportParser(self)
        ]

        original_clean_lines = self.clean_lines.copy()
        for parser in parsers:
            try:
                self.clean_lines = original_clean_lines.copy()
                if parser.parse():
                    parser_deps = getattr(parser, "dependencies", {"modules": [], "imports": [], "calls": []})
                    dependencies["modules"].extend(parser_deps["modules"])
                    dependencies["imports"].extend(parser_deps["imports"])
                    dependencies["calls"].extend(parser_deps["calls"])
                    logging.debug(f"Applied {parser.__class__.__name__} parser, new clean_lines[1:10]: {self.clean_lines[1:10]}")
                    if isinstance(parser, ObjectParser):
                        for line_num in parser.new_entities_lines:
                            entity = self.entity_map[line_num]
                            object_context = entity["name"]
                            object_indent = len(self.clean_lines[line_num]) - len(self.clean_lines[line_num].lstrip())
            except Exception as e:
                logging.error(f"Error in {parser.__class__.__name__} parser for {self.file_name}: {str(e)}")
                traceback.print_exc()
                break

        self.clean_lines = original_clean_lines
        entities = self.sorted_entities()
        logging.debug(f"Parsed {len(entities)} entities in {self.file_name}")
        return {"entities": entities, "dependencies": {k: sorted(list(set(v))) for k, v in dependencies.items()}}


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
            return {"entities": [], "dependencies": {"modules": [], "imports": [], "calls": []}}
        self.entity_map = {}
        dependencies = {"modules": [], "imports": [], "calls": []}
        self.clean_lines = clean_lines if clean_lines is not None else ([""] + self.content_text.splitlines())
        self.strip_strings()
        self.strip_comments()

        parsers = [
            FunctionParser("function", self),
            ObjectParser("object", self),
            MethodParser("method", self),
            InterfaceParser("interface", self),
            ClassParser("class", self),
            ImportParser(self)
        ]

        original_clean_lines = self.clean_lines.copy()
        for parser in parsers:
            try:
                self.clean_lines = original_clean_lines.copy()
                if parser.parse():
                    parser_deps = getattr(parser, "dependencies", {"modules": [], "imports": [], "calls": []})
                    dependencies["modules"].extend(parser_deps["modules"])
                    dependencies["imports"].extend(parser_deps["imports"])
                    dependencies["calls"].extend(parser_deps["calls"])
                    logging.debug(f"Applied {parser.__class__.__name__} parser, new clean_lines[1:10]: {self.clean_lines[1:10]}")
                    if isinstance(parser, ObjectParser):
                        for line_num in parser.new_entities_lines:
                            entity = self.entity_map[line_num]
                            object_context = entity["name"]
                            object_indent = len(self.clean_lines[line_num]) - len(self.clean_lines[line_num].lstrip())
            except Exception as e:
                logging.error(f"Error in {parser.__class__.__name__} parser for {self.file_name}: {str(e)}")
                traceback.print_exc()
                break

        self.clean_lines = original_clean_lines
        entities = self.sorted_entities()
        logging.debug(f"Parsed {len(entities)} entities in {self.file_name}")
        return {"entities": entities, "dependencies": {k: sorted(list(set(v))) for k, v in dependencies.items()}}

SandwichPack.register_block_class(ContentCodeJs)
SandwichPack.register_block_class(ContentCodeTypeScript)