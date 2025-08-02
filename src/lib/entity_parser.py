# /lib/entity_parser.py, updated 2025-08-02 12:45 EEST
# Formatted with proper line breaks and indentation for project compliance.

import logging
import re
import traceback
from lib.content_block import estimate_tokens

class EntityParser:
    """Base class for parsing entities in content blocks."""

    def __init__(self, entity_type, owner, outer_regex, mask_pattern, inner_regex=None, default_visibility="public"):
        """Initialize parser with entity type, owner block, and compiled regex patterns.

        Args:
            entity_type (str): Type of entity to parse (e.g., 'module', 'function').
            owner: ContentBlock or derivative instance (e.g., ContentCodeRust).
            outer_regex (re.Pattern): Compiled regex pattern for parsing entities.
            mask_pattern (str): Regex pattern for masking entity tokens.
            inner_regex (re.Pattern, optional): Compiled regex pattern for parsing inner entities (e.g., methods).
            default_visibility (str): Default visibility if 'vis' group is absent ('public' or 'private').
        """
        self.entity_type = entity_type
        self.owner = owner
        self.outer_regex = outer_regex
        self.mask_pattern = mask_pattern
        self.inner_regex = inner_regex
        self.default_visibility = default_visibility
        self.new_entities_lines = []  # List of first_line numbers for new entities
        self.dependencies = {"modules": [], "imports": [], "calls": []}
        logging.debug(f"Initialized EntityParser for entity_type={entity_type}, owner={owner.file_name}, default_visibility={default_visibility}")

    def _format_entity_name(self, match):
        name = match.group('name')
        return self.owner.module_prefix + name

    def _format_inner_name(self, match, parent: str):
        name = match.group('name')
        return f"{parent}::{name}"  # Default format for inner entity names

    def _process_match(self, match, clean_content, content_offset):
        """Process a regex match to create and add an entity.

        Args:
            match: Regex match object with 'name' and optional 'vis' groups.
            clean_content (str): Cleaned content for token estimation.
            content_offset (int): Line offset for clean_lines.

        Returns:
            bool: True if entity was added, False otherwise.
        """
        start_pos = match.start('name') if 'name' in match.groupdict() and match.group('name') else match.start()
        start_line = self.owner.find_line(start_pos)
        vis = "public" if match.groupdict().get('vis') else self.default_visibility
        full_text = self.owner.extract_entity_text(match.start(), match.end())

        name_final = self._format_entity_name(match)
        logging.debug(f"Processing entity {name_final} at line {start_line}, text: {full_text!r}")
        entity = {
            "type": self.entity_type,
            "name": name_final,
            "visibility": vis,
            "file_id": self.owner.file_id,
            "first_line": start_line,
            "tokens": estimate_tokens(full_text)
        }
        if self.owner.add_entity(start_line, entity):
            self.new_entities_lines.append(start_line)
            if self.inner_regex:
                content = self.owner.extract_entity_text(match.start(), match.end())
                self.parse_inner(content, start_line, name_final)
            return True
        return False

    def parse(self):
        """Parse clean_lines to extract entities and dependencies.

        Uses self.outer_regex to find entities and calls _process_match.
        Skips lines already processed by other parsers.

        Returns:
            bool: True if parsing was successful.
        """
        clean_content = self.owner.get_clean_content()
        for match in self.outer_regex.finditer(clean_content):
            start_pos = match.start('name') if 'name' in match.groupdict() and match.group('name') else match.start()
            start_line = self.owner.find_line(start_pos)
            if start_line in self.owner.entity_map:
                logging.debug(f"Skipping line {start_line} for {self.entity_type} as it is already processed: {self.owner.entity_map[start_line]}")
                continue
            self._process_match(match, clean_content, 1)
        return True

    def parse_inner(self, content, offset, parent_name):
        """Parse inner entities (e.g., methods in traits or impls).

        Args:
            content (str): Content to parse (e.g., trait or impl block).
            offset (int): Line offset for inner entities.
            parent_name (str): Name of the parent entity (e.g., trait or impl name).

        Returns:
            None
        """
        if not self.inner_regex:
            return
        for match in self.inner_regex.finditer(content):
            start_pos = match.start('name')
            line_count = content[:start_pos].count('\n')
            method_line = offset + line_count
            vis = "public" if match.groupdict().get('vis') else self.default_visibility
            full_text_method = match.group(0)
            ent_type = "abstract method" if full_text_method.endswith(';') else "method"
            entity = {
                "type": ent_type,
                "name": self._format_inner_name(match, parent_name),
                "visibility": vis,
                "file_id": self.owner.file_id,
                "first_line": method_line,
                "last_line": method_line if ent_type == "abstract method" else None,
                "tokens": estimate_tokens(full_text_method)
            }
            if self.owner.add_entity(method_line, entity):
                self.new_entities_lines.append(method_line)

    def masquerade(self):
        """Masquerade parsed entities in clean_lines.

        Replaces self.mask_pattern with entity['type'] for entity lines.

        Returns:
            list: Modified clean_lines.
        """
        clean_lines = self.owner.clean_lines.copy()
        for line_num in self.new_entities_lines:
            e = self.owner.entity_map[line_num]
            clean_lines[line_num] = re.sub(self.mask_pattern, e['type'], clean_lines[line_num])
        return clean_lines
