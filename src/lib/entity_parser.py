# /lib/entity_parser.py, updated 2025-08-08 12:01 EEST
# Formatted with proper line breaks and indentation for project compliance.

import logging
import re
import traceback
from .llm_tools import estimate_tokens
from .iter_regex import IterativeRegex


def match_value(match, field: str, default=None):
    if field in match.groupdict() and match.group(field):
        return match.group(field)
    return default


def get_start_pos(match, field: str = "name"):
    return match.start(field) if field in match.groupdict() and match.group(field) else match.start()


class EntityParser:
    """Base class for parsing entities in content blocks."""

    def __init__(self, entity_type, owner, outer_regex: IterativeRegex, mask_pattern, inner_regex: IterativeRegex = None, default_visibility="public"):
        """Initialize parser with entity type, owner block, and iterative regex objects.

        Args:
            entity_type (str): Type of entity to parse (e.g., 'module', 'function').
            owner: ContentBlock or derivative instance (e.g., ContentCodeRust).
            outer_regex (IterativeRegex): Iterative regex for outer entities.
            mask_pattern (str): Regex pattern for masking entity tokens.
            inner_regex (IterativeRegex, optional): Iterative regex for inner entities.
            default_visibility (str): Default visibility if 'vis' group is absent ('public' or 'private').
        """
        self.entity_type = entity_type
        self.owner = owner
        self.content = owner.get_clean_content()
        self.outer_regex = outer_regex
        self.mask_pattern = mask_pattern
        self.inner_regex = inner_regex
        self.default_visibility = default_visibility
        self.new_entities_lines = []  # List of first_line numbers for new entities
        self.modules = []
        self.imports = {}  # Dict[entity_name: module_name]

        logging.debug(f"Initialized EntityParser for entity_type={entity_type}, file={owner.file_name}, default_visibility={default_visibility}")

    def _format_entity_name(self, match):
        name = match.group('name')
        prefix = self.owner.module_prefix
        if prefix and prefix in name:
            stack = "\t".join(traceback.format_stack(limit=5)).strip()
            logging.warning(f"module prefix {prefix} already included in {name}, stack:\n{stack}")
            return name
        return prefix + name

    def _format_inner_name(self, match, parent: str):
        return match.group('name')  # Default format for inner entity names

    def make_entity(self, e_type: str, name: str, vis: str, first_line: int, full_text: str, extra_fields: dict = None) -> dict:
        """Create an entity dictionary with bounds and token count.

        Args:
            e_type (str): Entity type (e.g., 'function', 'class', 'local_function').
            name (str): Entity name (e.g., 'my_function', 'MyClass::my_method').
            vis (str): Visibility ('public' or 'private').
            first_line (int): Starting line number.
            full_text (str): Full text of the entity.
            extra_fields (dict, optional): Additional fields to include (e.g., 'indent').

        Returns:
            dict: Entity dictionary with computed fields.
        """
        start_line = first_line
        last_line = start_line
        if not ("abstract" in e_type):
            start_line, last_line = self.owner.detect_bounds(first_line, self.owner.clean_lines)

        entity = {
            "type": e_type,
            "name": name,
            "visibility": vis,
            "file_id": self.owner.file_id,
            "first_line": start_line,
            "last_line": last_line,
            "tokens": estimate_tokens(full_text)
        }
        if extra_fields:
            entity.update(extra_fields)
        return entity

    def make_add_entity(self, e_type: str, name: str, vis: str, first_line: int, full_text: str, extra_fields: dict = None) -> bool:
        """Create and add an entity to entity_map.

        Args:
            e_type (str): Entity type.
            name (str): Entity name.
            vis (str): Visibility.
            first_line (int): Starting line number.
            full_text (str): Full text of the entity.
            extra_fields (dict, optional): Additional fields.

        Returns:
            bool: True if entity was added, False otherwise.
        """
        prev = self.owner.entity_map.get(first_line)
        if prev:
            logging.warning(f"Failed to add entity {name} at line {first_line}: already exists {prev} ")
            return False
        entity = self.make_entity(e_type, name, vis, first_line, full_text, extra_fields)
        if self.owner.add_entity(first_line, entity):
            self.new_entities_lines.append(first_line)
            return True
        logging.error(" add_entity failed")
        return False

    def detect_abstract(self, match):
        ending = match_value(match, 'ending', '')
        if ';' in ending or 'abstract' in match.group(0):
            return True if self else False
        return False

    def detect_visibility(self, match):
        return match_value(match, 'vis', self.default_visibility).strip()

    def _process_match(self, base_match):
        """Process a regex match to create and add an entity.

        Args:
            match: Regex match object with 'name' and optional 'vis' groups.
            start_line (int): Starting line number.
            full_text (str): Full text of the entity.

        Returns:
            bool: True if entity was added, False otherwise.
        """
        def_start = base_match.start()  # may include some lines before name location
        if def_start < 0:
            logging.warning(f"base match started at {def_start}")
            return
        start_pos = get_start_pos(base_match)  # name start for start_line (formal entity location)
        start_line = self.owner.find_line(start_pos)
        if start_line in self.owner.entity_map:
            logging.debug(f" Skipping line {start_line} for {self.entity_type} as it is already processed: {self.owner.entity_map[start_line]}")
            return

        clean_content = self.content
        validation = self.outer_regex.validate_match(clean_content, def_start)
        hit_rate = validation['hit_rate']
        if hit_rate < 0.5:
            logging.debug(f" Skipping low hit_rate {hit_rate} for match at {start_line}, offset{def_start}")
            return

        match = validation['match']
        def_end = match.end()
        full_text = self.owner.extract_entity_text(def_start, def_end)
        ent_lines = len(full_text.splitlines())
        vis = self.detect_visibility(match)
        name_final = self._format_entity_name(match)
        logging.debug(f"Processing entity {name_final} at line {start_line}, text lines {ent_lines}")
        spec = ''
        extra_fields = {"hit_rate": hit_rate}
        if match_value(match, "async"):
            spec += "async "
        if parent := match_value(match, "parent"):
            extra_fields["parent"] = parent.strip()

        if self.make_add_entity(spec + self.entity_type, name_final, vis, start_line, full_text, extra_fields):
            if self.inner_regex:
                self.parse_inner(full_text, start_line, name_final)
            return True
        return False

    def parse(self):
        """Parse clean_lines to extract entities and dependencies.

        Uses self.outer_regex to find entities and calls _process_match.
        Skips lines already processed by other parsers.

        Returns:
            bool: True if parsing was successful.
        """
        self.content = self.owner.get_clean_content()  # refresh, due masquerade acting
        if not self.content.strip():
            logging.debug("Attempt parsing void content")
            return False

        logging.debug(f"====================== Start parsing {self.entity_type} ======================= ")
        for base_match in self.outer_regex.all_matches(self.content):
            self._process_match(base_match)
        return True

    def parse_inner(self, content: str, offset: int, parent_name: str):
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
        found = 0
        for base_match in self.inner_regex.all_matches(content):
            start_pos = base_match.start()  # initial start
            line_count = content[:start_pos].count('\n')
            method_line = offset + line_count

            validation = self.inner_regex.validate_match(content, start_pos)
            hit_rate = validation['hit_rate']
            if hit_rate < 0.4:
                logging.debug(f"Skipping low hit_rate {hit_rate} for inner match at {method_line}")
                continue
            match = validation['match']
            full_text_method = match.group(0).strip()
            head_len = len(full_text_method.splitlines())
            vis = self.detect_visibility(match)
            ent_type = "method"
            if self.detect_abstract(match):
                ent_type = "abstract " + ent_type
                logging.debug(f" detected abstract method {full_text_method}, {head_len} lines")

            if match_value(match, 'async'):
                ent_type = "async " + ent_type
            name = self._format_inner_name(match, parent_name)
            spec = match_value(match, 'spec')
            spec = spec + ' ' if spec else ''
            extra_fields = {"parent": parent_name, "hit_rate": hit_rate}

            entity = self.make_entity(spec + ent_type, name, vis, method_line, full_text_method, extra_fields=extra_fields)
            entity["last_line"] = max(entity["last_line"], method_line + head_len - 1)  # multi-line declaration of abstract method
            if self.owner.add_entity(method_line, entity):
                self.new_entities_lines.append(method_line)
                found += 1
            else:
                logging.warning(f"Failed to add inner entity {name} for {parent_name}")
        if found > 0:
            logging.debug(f" found inner {found} entities with parent {parent_name}")
        elif len(content) > 100:
            logging.debug(f" not found inner entities in:\n {content}")

    def masquerade(self):
        """Masquerade parsed entities in clean_lines.

        Replaces self.mask_pattern with entity['type'] for entity lines.

        Returns:
            list: Modified clean_lines.
        """
        clean_lines = self.owner.clean_lines.copy()
        if getattr(self, 'new_entities_lines', False):
            for line_num in self.new_entities_lines:
                e = self.owner.entity_map[line_num]
                clean_lines[line_num] = re.sub(self.mask_pattern, e['type'], clean_lines[line_num])
        return clean_lines
