# /lib/content_block.py, updated 2025-07-31 14:11 EEST
# Formatted with proper line breaks and indentation for project compliance.

import logging
import re
import os
import math
from pathlib import Path

# CRITICAL NOTICE: Using content for bounds detection before full cleaning is prohibited to avoid errors from comments/strings.
# PROTECTION CODE DON'T TOUCH!!!
Optional = None
List = None
Dict = None
Tuple = None
assert List is None
assert Dict is None
assert Tuple is None

logging.basicConfig(
    level=os.environ.get('LOGLEVEL', 'DEBUG').upper()
)

def estimate_tokens(content):
    """Estimates tokens by counting words and spaces more accurately."""
    if not content:
        return 0
    tokens = 0
    words = re.findall(r'\S+', content)
    for word in words:
        if len(word) >= 5:
            tokens += math.ceil(len(word) / 4)
        else:
            tokens += 1
    spaces = len(re.findall(r'\s+', content))
    tokens += spaces
    logging.debug("Estimated tokens for content (length=%d): %d tokens (words=%d, spaces=%d)",
                  len(content), tokens, len(words), spaces)
    return tokens

class ContentBlock:
    supported_types = [':document', ':post']

    def __init__(self, content_text, content_type, file_name=None, timestamp=None, **kwargs):
        self.content_text = content_text
        self.content_type = content_type
        self.tag = "post" if content_type == ":post" else "document"
        self.file_name = file_name
        self.timestamp = timestamp
        self.post_id = kwargs.get('post_id')
        self.user_id = kwargs.get('user_id')
        self.relevance = kwargs.get('relevance', 0)
        self.file_id = kwargs.get('file_id')
        self.tokens = estimate_tokens(content_text)
        self.clean_lines = ["Line №0"] + self.content_text.splitlines()  # 1-based indexing, volatile
        self.strip_log = []  # Log of detected comments and strings for debugging
        self.warnings = []  # List of warning messages
        self.entity_map = {}  # Dict[first_line: entity]
        self.string_quote_chars = "\"'"  # Characters for string literals
        self.raw_str_prefix = None  # Prefix for raw strings (e.g., 'r' for Rust)
        self.raw_quote_char = None  # Quote char for raw strings (e.g., "'" for PHP)
        self.open_ml_string = []  # Opening sequences for multi-line strings
        self.close_ml_string = []  # Closing sequences for multi-line strings
        self.open_sl_comment = ["//"]  # Single-line comment starts
        self.open_ml_comment = ["/*"]  # Multi-line comment starts
        self.close_ml_comment = ["*/"]  # Multi-line comment ends
        self.escape_char = "\\"  # Escape character
        self.module_prefix = ""  # Tracks current module prefix (e.g., "logger.")
        self.line_offsets = []  # List of character offsets for each line in clean_content
        logging.debug(f"Initialized ContentBlock with content_type={content_type}, tag={self.tag}, file_name={file_name}")

    def parse_warn(self, msg):
        """Logs a warning and adds it to self.warnings."""
        self.warnings.append(msg)
        logging.warning(msg)

    def check_raw_escape(self, line, position, quote_char):
        """Checks if the character at position is part of a raw string escape sequence."""
        return False  # Default: no escape sequences in raw strings (e.g., Rust)

    def strip_raw_strings(self):
        """Strips raw string literals, preserving empty lines."""
        if len(self.clean_lines) <= 1:
            raise Exception("clean_lines not filled")
        clean_lines = self.clean_lines
        result_lines = [""]
        in_raw_string = False
        quote_char = None
        _rsq_len = len(self.raw_str_prefix) if self.raw_str_prefix else 0
        for line_num, line in enumerate(clean_lines[1:], 1):
            if not isinstance(line, str):
                result_lines.append("")
                continue
            clean_line = ""
            i = 0
            _len = len(line)
            while i < _len:
                char = line[i]
                if not in_raw_string:
                    prefix_chars = line[i - _rsq_len:i] if i >= _rsq_len else None
                    _is_raw_start = self.raw_str_prefix and prefix_chars == self.raw_str_prefix
                    _is_quote_char = char in self.string_quote_chars
                    if (self.raw_quote_char and char == self.raw_quote_char) or (_is_raw_start and _is_quote_char):
                        in_raw_string = True
                        quote_char = char
                        i += _rsq_len if _is_raw_start else 1
                        self.strip_log.append(f"Raw string {'with prefix ' + self.raw_str_prefix if _is_raw_start else ''} started at line {line_num}, pos {i}, quote: '{char}', line: '{line}'")
                    clean_line += char
                elif self.check_raw_escape(line, i, quote_char):
                    i += 1
                elif char == quote_char:
                    in_raw_string = False
                    quote_char = None
                    clean_line += char
                    self.strip_log.append(f"Raw string ended at line {line_num}, pos {i + 1}, line: '{line}'")
                i += 1
            result_lines.append(clean_line)
            if in_raw_string:
                self.parse_warn(f"Incomplete raw string literal in file {self.file_name} at line {line_num}")
                self.strip_log.append(f"Incomplete raw string at line {line_num}, line: '{line}'")
        self.clean_lines = result_lines
        return result_lines

    def strip_strings(self):
        """Strips string literals with full escaping, preserving empty lines."""
        if len(self.clean_lines) <= 1:
            self.clean_lines = [''] + self.content_text.splitlines()
        self.strip_raw_strings()
        self.strip_multiline_strings()
        clean_lines = self.clean_lines
        result_lines = [""]
        quote_char = None
        for line_num, line in enumerate(clean_lines[1:], 1):
            in_string = False
            if not isinstance(line, str):
                result_lines.append("")
                continue
            clean_line = ""
            i = 0
            _len = len(line)
            while i < _len:
                char = line[i]
                if not in_string:
                    if char in self.string_quote_chars:
                        in_string = True
                        quote_char = char
                    clean_line += char
                elif char == self.escape_char and i + 1 < _len:
                    i += 1
                elif char == quote_char:
                    in_string = False
                    quote_char = None
                    clean_line += char
                i += 1
            result_lines.append(clean_line)
            if in_string:
                self.parse_warn(f"Incomplete string literal in file {self.file_name} at line {line_num}")
                self.strip_log.append(f"Incomplete string at line {line_num}, line: '{line}'")
        self.clean_lines = result_lines
        return result_lines

    def strip_multiline_strings(self):
        """Strips multi-line string literals, preserving empty lines."""
        if len(self.clean_lines) <= 1:
            raise Exception("clean_lines not filled")
        clean_lines = self.clean_lines
        result_lines = [""]
        in_multi_string = False
        multi_quote = None
        for line_num, line in enumerate(clean_lines[1:], 1):
            if not isinstance(line, str):
                result_lines.append("")
                continue
            clean_line = ""
            i = 0
            _len = len(line)
            while i < _len:
                char = line[i]
                if not in_multi_string:
                    for open_quote in self.open_ml_string:
                        _oq_len = len(open_quote)
                        if i + _oq_len <= _len and line[i:i+_oq_len] == open_quote:
                            in_multi_string = True
                            multi_quote = open_quote
                            clean_line += open_quote
                            i += _oq_len - 1
                            self.strip_log.append(f"Multi-line string started at line {line_num}, pos {i + 1}, quote: '{open_quote}', line: '{line}'")
                            break
                    else:
                        clean_line += char
                elif i + len(self.close_ml_string[self.open_ml_string.index(multi_quote)]) <= _len and \
                     line[i:i+len(self.close_ml_string[self.open_ml_string.index(multi_quote)])] == self.close_ml_string[self.open_ml_string.index(multi_quote)]:
                    close_quote = self.close_ml_string[self.open_ml_string.index(multi_quote)]
                    in_multi_string = False
                    multi_quote = None
                    clean_line += close_quote
                    i += len(close_quote) - 1
                    self.strip_log.append(f"Multi-line string ended at line {line_num}, pos {i + 1}, line: '{line}'")
                i += 1
            result_lines.append(clean_line)
            if in_multi_string:
                self.parse_warn(f"Incomplete multi-line string in file {self.file_name} at line {line_num}")
                self.strip_log.append(f"Incomplete multi-line string at line {line_num}, line: '{line}'")
        self.clean_lines = result_lines
        return result_lines

    def strip_comments(self):
        """Strips comments from content, preserving empty lines."""
        if len(self.clean_lines) <= 1:
            raise Exception("clean_lines not filled")
        clean_lines = self.clean_lines.copy()
        result_lines = [""]
        in_multi_comment = False
        multi_comment_open = None
        for line_num, line in enumerate(clean_lines[1:], 1):
            if not isinstance(line, str):
                result_lines.append("")
                continue
            clean_line = ""
            i = 0
            _len = len(line)
            if in_multi_comment:
                end_pos = line.find(self.close_ml_comment[self.open_ml_comment.index(multi_comment_open)])
                if end_pos >= 0:
                    in_multi_comment = False
                    multi_comment_open = None
                    clean_line = line[end_pos + len(self.close_ml_comment[0]):]
                    self.strip_log.append(f"Multi-line comment ended at line {line_num}, pos {end_pos}, remaining: '{clean_line}', line: '{line}'")
                else:
                    clean_line = ""
                    self.strip_log.append(f"Multi-line comment continued at line {line_num}, line: '{line}'")
                    result_lines.append(clean_line)
                    continue
            while i < _len:
                char = line[i]
                min_start_pos = -1
                min_start_type = None
                min_comment = None
                for sl_comment in self.open_sl_comment:
                    start_pos = line.find(sl_comment, i)
                    if start_pos >= 0 and (min_start_pos < 0 or start_pos < min_start_pos):
                        min_start_pos = start_pos
                        min_start_type = "single"
                        min_comment = sl_comment
                for ml_comment in self.open_ml_comment:
                    multi_pos = line.find(ml_comment, i)
                    if multi_pos >= 0 and (min_start_pos < 0 or multi_pos < min_start_pos):
                        min_start_pos = multi_pos
                        min_start_type = "multi"
                        min_comment = ml_comment
                if min_start_type == "single":
                    clean_line += line[i:min_start_pos]
                    self.strip_log.append(f"Single-line comment at line {line_num}, pos {min_start_pos}, stripped: '{clean_line}', line: '{line}'")
                    break
                elif min_start_type == "multi":
                    clean_line += line[i:min_start_pos]
                    in_multi_comment = True
                    multi_comment_open = min_comment
                    i += len(multi_comment_open)
                    end_pos = line.find(self.close_ml_comment[self.open_ml_comment.index(multi_comment_open)], i)
                    self.strip_log.append(f"Multi-line comment started at line {line_num}, pos {min_start_pos}, line: '{line}'")
                    if end_pos >= 0:
                        in_multi_comment = False
                        multi_comment_open = None
                        clean_line += line[end_pos + len(self.close_ml_comment[0]):]
                        self.strip_log.append(f"Multi-line comment ended at line {line_num}, pos {end_pos}, remaining: '{clean_line}', line: '{line}'")
                        i = end_pos + len(self.close_ml_comment[0])
                    else:
                        break
                else:
                    clean_line += char
                i += 1
            result_lines.append(clean_line)
            if in_multi_comment and line_num == len(clean_lines) - 1:
                self.parse_warn(f"Incomplete multi-line comment in file {self.file_name} at line {line_num}")
                self.strip_log.append(f"Incomplete multi-line comment at line {line_num}, line: '{line}'")
                for j in range(line_num + 1, len(clean_lines)):
                    result_lines.append("")
                    self.strip_log.append(f"Multi-line comment continued at line {j}, line: '{clean_lines[j]}'")
        self.clean_lines = result_lines
        logging.debug(f"After strip_comments, lines 60-70: {self.clean_lines[60:71]}")
        return result_lines

    def save_clean(self, file_name):
        """Saves the cleaned content to a file for debugging, replacing empty lines with line number comments."""
        if len(self.clean_lines) <= 1:
            raise Exception("clean_lines not filled")
        try:
            output_path = Path(file_name)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("w", encoding="utf-8") as f:
                for line_num, line in enumerate(self.clean_lines[1:], 1):
                    f.write((line if line.strip() else f"// Line {line_num}") + "\n")
            logging.debug(f"Saved cleaned content to {file_name}")
        except Exception as e:
            logging.error(f"Failed to save cleaned content to {file_name}: {str(e)}")

    def get_clean_content(self):
        """Returns the cleaned content as a single string and updates line_offsets."""
        if len(self.clean_lines) <= 1:
            raise Exception("clean_lines not initialized")
        content = "\n".join(self.clean_lines[1:])
        self.line_offsets = [0]
        offset = 0
        for line in self.clean_lines[1:]:
            offset += len(line) + 1  # +1 for newline
            self.line_offsets.append(offset)
        logging.debug(f"Updated line_offsets: {self.line_offsets[:10]}... (total {len(self.line_offsets)})")
        logging.debug(f"Line offsets 46-61: {self.line_offsets[46:62]}")
        return content

    def find_line(self, content_offset):
        """Finds the line number for a given content offset."""
        if not self.line_offsets:
            self.get_clean_content()  # Ensure line_offsets is populated
        for i, offset in enumerate(self.line_offsets):
            if content_offset < offset:
                return i
        return len(self.line_offsets) - 1

    def count_chars(self, line_num, ch):
        """Counts occurrences of a character in a specific line of clean code."""
        if len(self.clean_lines) <= 1:
            self.strip_strings()
            self.strip_comments()
        if line_num < 1 or line_num >= len(self.clean_lines):
            logging.error(f"Invalid line number {line_num} for file {self.file_name}")
            return 0
        line = self.clean_lines[line_num]
        if not isinstance(line, str):
            return 0
        return line.count(ch)

    def sorted_entities(self):
        """Sorts entities by their line number."""
        sorted_map = {}
        result = []
        for line_num in sorted(self.entity_map.keys()):
            sorted_map[line_num] = self.entity_map[line_num]
            result.append(self.entity_map[line_num])
        self.entity_map = sorted_map
        return result

    def detect_bounds(self, start_line, clean_lines: list):
        """Detects the start and end line of an entity using brace counting."""
        if start_line < 1 or start_line >= len(clean_lines) or not clean_lines[start_line] or not clean_lines[start_line].strip():
            logging.error(f"Invalid start line {start_line} for file {self.file_name} module [{self.module_prefix}]")
            return start_line, start_line
        brace_count = 0
        line_num = start_line
        while line_num < len(clean_lines):
            line = clean_lines[line_num]
            if not isinstance(line, str) or not line.strip():
                line_num += 1
                continue
            brace_count += line.count('{') - line.count('}')
            logging.debug(f"Line {line_num}: brace_count={brace_count}, line: '{line.strip()}'")
            if brace_count == 0 and line_num >= start_line:
                # Include the line with the closing brace
                return start_line, line_num
            line_num += 1
        self.parse_warn(f"Incomplete entity at line {start_line} in file {self.file_name}, brace_count={brace_count}")
        return start_line, start_line

    def check_entity_placement(self, line_num: int, name: str):
        """Checks if an entity with the given name is correctly placed at line_num."""
        if line_num < 1 or line_num >= len(self.clean_lines) or not self.clean_lines[line_num]:
            return False
        line = self.clean_lines[line_num]
        base_name = name.split(".")[-1]  # Get in module name
        base_name = base_name.split("::")[-1].split("<")[0]  # Extract base name

        pattern = rf"\b{base_name}\b"
        result = bool(re.search(pattern, line))
        if not result:
            # Search for first occurrence of base_name in clean_lines
            for i, search_line in enumerate(self.clean_lines[1:], 1):
                if isinstance(search_line, str) and re.search(pattern, search_line):
                    logging.debug(f"First occurrence of '{base_name}' found at line {i}: '{search_line}'")
                    break
            else:
                logging.debug(f"No occurrence of '{base_name}' found in clean_lines")
        logging.debug(f"Checking entity placement for {name} at line {line_num}: {'Passed' if result else 'Failed'}, line: '{line}'")
        return result

    def check_lines_match(self, offset, full_clean_lines):
        """Validates that clean_lines matches full_clean_lines at the given offset."""
        if offset < 1 or offset >= len(self.clean_lines):
            logging.error(f"Invalid offset {offset} for file {self.file_name}")
            return False
        for i, line in enumerate(self.clean_lines[offset:], offset):
            if i >= len(full_clean_lines):
                return False
            if line != full_clean_lines[i]:
                logging.warning(f"Line mismatch at {i}: expected '{full_clean_lines[i]}', got '{line}'")
                return False
        return True

    def add_entity(self, line_num: int, entity: dict):
        """Adds an entity to entity_map with placement and duplication checks."""
        if line_num in self.entity_map:
            existing = self.entity_map[line_num]
            if existing["name"] != entity["name"] or existing["type"] != entity["type"]:
                logging.warning(f"Duplicate entity at line {line_num}: {entity['name']} ({entity['type']}) conflicts with {existing['name']} ({existing['type']})")
                return False
        if not self.check_entity_placement(line_num, entity["name"]):
            logging.warning(f"Entity {entity['name']} placement check failed at line {line_num}, line: '{self.clean_lines[line_num]}'")
            return False
        entity["first_line"] = line_num
        # Respect last_line for abstract methods, otherwise use detect_bounds
        if entity["type"] != "abstract method" or "last_line" not in entity:
            entity["last_line"] = self.detect_bounds(line_num, self.clean_lines)[1]
        self.entity_map[line_num] = entity
        logging.debug(f"Added entity {entity['name']} at first_line={line_num}, last_line={entity['last_line']}")
        return True

    def _extract_full_entity(self, start, end_header, content=None):
        """Extracts the full entity text using clean_lines for brace counting."""
        if len(self.clean_lines) <= 1:
            raise Exception("clean_lines not filled")
        content = content or self.get_clean_content()
        start_pos = start
        lines = content.splitlines()
        start_line = self.find_line(start_pos)
        logging.debug(f"Calculating bounds for start_pos={start_pos}, start_line={start_line}, content preview: {content[start:start + 100]}...")
        logging.debug(f"Entity at line {start_line}: '{self.clean_lines[start_line]}', raw: '{lines[start_line - 1]}'")
        logging.debug(f"Clean lines: {self.clean_lines[start_line-1:start_line+2]}")
        start_line, end_line = self.detect_bounds(start_line, self.clean_lines)
        if start_line == end_line:
            self.parse_warn(f"Incomplete entity in file {self.file_name} at start={start}, using header end")
            return content[start:end_header]
        logging.info(f"Extracted entity from first_line={start_line} to last_line={end_line}")
        return "\n".join(self.clean_lines[start_line:end_line + 1])

    def to_sandwich_block(self):
        attrs = []
        if self.content_type == ":post":
            attrs.append(f'post_id="{self.post_id}"')
            if self.user_id is not None:
                attrs.append(f'user_id="{self.user_id}"')
            if self.timestamp:
                attrs.append(f'mod_time="{self.timestamp}"')
            if self.relevance is not None:
                attrs.append(f'relevance="{self.relevance}"')
        else:
            if self.file_name:
                attrs.append(f'src="{self.file_name}"')
            if self.timestamp:
                attrs.append(f'mod_time="{self.timestamp}"')
            if self.file_id is not None:
                attrs.append(f'file_id="{self.file_id}"')
        attr_str = " ".join(attrs)
        return f"<{self.tag} {attr_str}>\n{self.content_text}\n</{self.tag}>"