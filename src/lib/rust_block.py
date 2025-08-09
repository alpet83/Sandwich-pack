# /lib/rust_block.py, updated 2025-08-08 12:29 EEST
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


BASE_REGEX_PATTERN = r"^(?:#\[(?P<spec>.*)?\]\s*)?(?P<indent>[ \t]*)(?P<vis>pub\s+)?"
FN_REGEX_PATTERN = r"(?P<async>async\s+)?fn\s+(?P<name>\w+)"
ARGS_REGEX_PATTERN = r"\s*\((?P<args>([^;^\{]+)\)?)\s*"
RET_REGEX_PATTERN = r"(?:->\s*(?P<return>[^;^\{]+))?"


class ModuleParser(EntityParser):
    """Parser for Rust modules with recursive parsing."""
    def __init__(self, entity_type, owner):
        outer_regex = IterativeRegex()
        outer_regex.add_token(BASE_REGEX_PATTERN + r"mod\s+(?P<name>\w+)", ["indent", "vis", "name"], 2)
        outer_regex.add_token(r"\s*{", ["head_end"], 1)
        super().__init__(entity_type, owner, outer_regex, r"\bmod\b", default_visibility="private")

    def _process_match(self, match):
        """Process a module match and perform recursive parsing."""
        start_pos = match.start('name')
        start_line = self.owner.find_line(start_pos)
        module_name = match.group('name')
        vis = "public" if match.groupdict().get('vis') else "private"
        name_final = f"{self.owner.module_prefix}{module_name}"
        full_text = self.owner.extract_entity_text(match.start(), match.end())
        logging.debug(f"Processing module {name_final} at line {start_line}, text: {full_text!r}")
        if not self.make_add_entity(self.entity_type, name_final, vis, start_line, full_text, {"parent": ""}):
            return False

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

        self.owner.extend_deps(sub_result["dependencies"])
        return True


class TraitParser(EntityParser):
    def __init__(self, entity_type, owner):
        self.current_struct = ""
        outer_regex = IterativeRegex()
        outer_regex\
            .add_token(BASE_REGEX_PATTERN + r"trait\s+(?P<name>\w+)", ["indent", "vis", "name"], 2)\
            .add_token(r"(?:\:\s*(?P<parent>[\+\w\s]+))?", ["parent"], 1)\
            .add_token(r"\s*{", ["head_end"], 1)
        inner_regex = IterativeRegex()   # abstract method
        inner_regex\
            .add_token(BASE_REGEX_PATTERN + FN_REGEX_PATTERN, ["indent", "vis", "async", "name"], 2)\
            .add_token(ARGS_REGEX_PATTERN, ["args"], 1)\
            .add_token(RET_REGEX_PATTERN, ["return"], 1)\
            .add_token(r";", ["head_end"], 1)
        super().__init__(entity_type, owner, outer_regex, r"\btrait\b|\bfn\b", inner_regex, default_visibility="private"),


class TraitImplParser(EntityParser):
    """Parser for Rust trait implementations and their methods."""
    def __init__(self, entity_type, owner):
        self.current_struct = ""
        outer_regex = IterativeRegex()
        # possible very simple impl definition, without "for Struct"
        outer_regex\
            .add_token(BASE_REGEX_PATTERN + r"impl\s+(?P<name>\w+)", ["indent", "vis", "name"], 2)\
            .add_token(r"\s+(?:for\s+(?P<struct_name>\w+))?", ["struct_name"], 1)\
            .add_token(r"\s*{", ["head_end"], 1)
        inner_regex = IterativeRegex()
        inner_regex\
            .add_token(BASE_REGEX_PATTERN + FN_REGEX_PATTERN, ["indent", "vis", "async", "name"], 2)\
            .add_token(ARGS_REGEX_PATTERN, ["args"], 1)\
            .add_token(RET_REGEX_PATTERN, ["return"], 1)\
            .add_token(r"{", ["head_end"], 1)
        super().__init__(entity_type, owner, outer_regex, r"\bimpl\b|\bfn\b", inner_regex, default_visibility="private")

    def _format_entity_name(self, match):
        name = match.group("name")
        struct_name = match.group('struct_name')
        if struct_name is not None:
            return f"{self.owner.module_prefix}{name}<{struct_name}>"
        return name


class FunctionParser(EntityParser):
    """Parser for Rust functions."""
    def __init__(self, entity_type, owner):
        outer_regex = IterativeRegex()
        outer_regex.add_token(BASE_REGEX_PATTERN + r"(?P<async>async\s+)?fn\s+(?P<name>\w+)", ["indent", "vis", "async", "name"], 2)\
            .add_token(ARGS_REGEX_PATTERN, ["args"], 1)\
            .add_token(RET_REGEX_PATTERN, ["return"], 1)\
            .add_token(r"{", ["head_end"], 1)
        super().__init__(entity_type, owner, outer_regex, r"\bfn\b", default_visibility="private")


class DepsParserRust(DepsParser):
    """Parser for Rust imports."""
    def __init__(self, owner):
        outer_regex = IterativeRegex()
        outer_regex.add_token(
            r"^(?P<indent>[ \t]*)use\s+(?:crate::{)?(?P<imports>([^;]+))?",
            ["indent", "imports"], 2
        ).add_token(
            ';', ['head_end'], 1
        )
        inner_regex = IterativeRegex()
        inner_regex.add_token(
            r"\s*(?P<module>[\w:]+)\s*", ["module"], 2
        ).add_token(
            r"(?:{\s*(?P<items>[^}]+)})?", ["items"], 1
        ).add_token(
            r"(?:,|$)", ["breaker"], 1
        )
        super().__init__(owner, outer_regex)
        # "^[ \t]*use[ \t]+",\
        self.inner_regex = inner_regex

    def process_imports(self, imports, parent_module=''):
        if len(imports) < 3:
            return False
        limit = imports.find(';')
        if limit > 0:
            imports = imports[:limit]  # always need cutout between use and ;
        modules = self.inner_regex.all_matches(imports)
        for module in modules:  # single line use xx::yy
            validation = self.inner_regex.validate_match(imports, module.start())
            logging.debug(f" checking modules import from: `{module.group(0)}`")
            if validation['hit_rate'] < 0.1:
                logging.warning(" hit_rate too small")
                continue
            inner_match = validation['match']
            items = match_value(inner_match, 'items')
            mod_chain = match_value(inner_match, 'module', '').strip(':')
            if parent_module:
                mod_chain = parent_module + "::" + mod_chain

            if items:
                logging.debug(f" detected multiply items: {items} in {mod_chain}")
                if "::" in items:
                    logging.debug(" recursion processing scan...")
                    return self.process_imports(items, mod_chain)
                elif mod_chain:
                    self.add_module(mod_chain)
                    for ent_name in items.split(','):
                        self.add_import(mod_chain, ent_name.strip())
                return True

            elif mod_chain:
                logging.debug(f"Single line import detected: {mod_chain}")
                chain = mod_chain.split('::')
                name = chain.pop()
                module = '::'.join(chain)
                self.add_module(module)
                self.add_import(module, name)
            return True
        return False

    def _process_match(self, match):
        """Process a 'use' statement to add modules and imports."""
        imports = match.group('imports')  # e.g., async_trait, chrono, crate
        if not imports:
            logging.warning(f"No `imports` match in group at {match.start()}, detected crate?")
            return False
        logging.debug(f"Global processing imports:\n {imports}")
        for line in imports.splitlines():
            self.process_imports(line.strip())
        return True




class ContentCodeRust(ContentBlock):
    """Parser for Rust content blocks."""
    supported_types = [".rs"]

    def __init__(self, content_text: str, content_type: str, file_name: str, timestamp: str, **kwargs):
        super().__init__(content_text, content_type, file_name, timestamp, **kwargs)
        self.tag = "rustc"
        self.entity_map = {}
        self.string_quote_chars = "\""  # одинарные кавычки для символов, их затирать нет смысла
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
            return {"entities": [], "dependencies": {"modules": [], "imports": {}}}
        self.entity_map = {}
        self.clean_lines = clean_lines if clean_lines is not None else ([""] + self.content_text.splitlines())
        self.strip_strings()
        self.strip_comments()

        struct_regex = IterativeRegex()
        struct_regex\
            .add_token(BASE_REGEX_PATTERN + r"struct\s+(?P<name>\w+)", ["indent", "vis", "name"], 2)\
            .add_token(r"(?:<.*?>)?\s*{", ["head_end"], 1)

        parsers = [
            DepsParserRust(self),
            ModuleParser("module", self),
            EntityParser("structure", self, struct_regex, r"\bstruct\b", default_visibility="private"),
            TraitParser("interface", self),
            TraitImplParser("class", self),
            FunctionParser("function", self)
        ]
        # Initialize structure and interface regexes

        for parser in parsers:
            try:
                if parser.parse():
                    self.extend_deps(parser)
                    self.clean_lines = parser.masquerade()
                    
            except Exception as e:
                logging.error(f"Error in {parser.__class__.__name__} parser for {self.file_name}: {str(e)}")
                traceback.print_exc()
                break

        entities = self.sorted_entities()
        logging.debug(f"Parsed {len(entities)} entities in {self.file_name}")
        return {"entities": entities, "dependencies": self.dependencies}


SandwichPack.register_block_class(ContentCodeRust)