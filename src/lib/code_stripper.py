# /lib/code_stripper.py, updated 2025-08-06 13:00 EEST
# Formatted with proper line breaks and indentation for project compliance.
# Proposed: 2025-08-06
# Changes: Added start_offset to detect_single, updated strip to process single-line content cyclically until no matches, skip empty lines to avoid redundant processing (CLA Rule 2: Ensure code correctness, CLA Rule 12: Minimize changes).

import logging
import re
from abc import ABC, abstractmethod

class CodeStripper(ABC):
    """Base class for stripping content (strings or comments) from code lines."""
    def __init__(self, owner):
        self.owner = owner
        self.strip_log = []
        self.warnings = []
        self.sl_open = []
        self.ml_open = []
        self.ml_close = []
        logging.debug(f"Initialized {self.__class__.__name__} for file {owner.file_name}")

    @abstractmethod
    def detect_single(self, line: str, line_num: int, start_offset: int) -> tuple:
        """Detects single-line content to strip, returning (start_pos, end_pos)."""
        pass

    @abstractmethod
    def detect_multi_open(self, line: str) -> tuple:
        """Detects multi-line content opening, returning (start_pos, token_index)."""
        pass

    @abstractmethod
    def detect_multi_close(self, line: str, close_token: str, start_offset: int) -> tuple:
        """Detects multi-line content closing, returning (start_pos, token_length)."""
        pass

    def strip(self, lines: list) -> list:
        """Strips content from lines, preserving empty lines."""
        if len(lines) <= 1:
            raise Exception("Lines not initialized")
        result_lines = lines.copy()
        in_multi = False
        close_token = None
        open_line = -1
        total_ml = 0
        multi_start_pos = -1
        log_indent = "\tSTRIP:"

        for line_num, line in enumerate(lines[1:], 1):
            if not isinstance(line, str):
                result_lines[line_num] = f"// NOT AS STRING, LINE {line_num}"
                continue
            if not line.strip():
                result_lines[line_num] = line
                continue
            clean_line = line
            end_pos = 0
            while end_pos < len(clean_line):
                start_pos, end_pos = self.detect_single(clean_line, line_num, end_pos)
                if start_pos < 0:
                    break
                clean_line = clean_line[:start_pos] + clean_line[end_pos:]
                clean_line = clean_line.rstrip()   # после очистки однострочных комментариев, пустые строки должны стать нулевой длины
                self.strip_log.append(f"{log_indent} Single-line content at line {line_num}, pos {start_pos}-{end_pos}, stripped: '{clean_line}', line: '{line}'")
                result_lines[line_num] = clean_line
                end_pos += 1

            left_part = ""
            if not in_multi and clean_line.strip():
                start_pos, token_index = self.detect_multi_open(clean_line)
                if start_pos >= 0:
                    left_part = clean_line[:start_pos]    # здесь нельзя модифицировать clean_line, поскольку запоминается multi_start_pos
                    in_multi = True
                    open_line = line_num
                    multi_start_pos = start_pos
                    close_token = self.ml_close[token_index]
                    self.strip_log.append(f"{log_indent} Multi-line content started at line {line_num}, pos {start_pos}, line: '{line}'")

            if in_multi and close_token:
                same_line = line_num == open_line
                total_ml += 1
                end_pos, token_length = self.detect_multi_close(clean_line, close_token, multi_start_pos if same_line else 0)
                if end_pos >= 0:
                    rest = left_part + clean_line[end_pos + token_length:]
                    result_lines[line_num] = rest
                    in_multi = False
                    close_token = None
                    self.strip_log.append(f"{log_indent} Multi-line content ended at line {line_num}, pos {end_pos}, remaining: '{rest}', line: '{line}'")
                else:
                    if line_num > open_line:
                        self.strip_log.append(f"{log_indent} Multi-line content continued at line {line_num}, line: '{line}'")
                    result_lines[line_num] = left_part
                    continue

            if in_multi and line_num == len(lines) - 1:
                msg = f"{log_indent} Incomplete multi-line content in file {self.owner.file_name} at line {line_num}"
                self.owner.parse_warn(msg)
                self.strip_log.append(msg)
                for j in range(line_num + 1, len(lines)):
                    result_lines[j] = clean_line
                    self.strip_log.append(f"{log_indent} Multi-line unclosed content continued at line {j}, line: '{lines[j]}'")
            result_lines[line_num] = clean_line

        logging.debug(f"{log_indent}Total multi-line content lines: {total_ml} / {len(result_lines)}")
        return result_lines

class CodeStringStripper(CodeStripper):
    """Strips string literals (single-line, raw, and multi-line)."""
    def __init__(self, owner, string_quote_chars, raw_str_prefix, raw_quote_char, open_ml_string, close_ml_string, escape_char):
        super().__init__(owner)
        self.sl_open = list(string_quote_chars)
        self.ml_open = open_ml_string
        self.ml_close = close_ml_string
        self.raw_str_prefix = raw_str_prefix
        self.raw_quote_char = raw_quote_char
        self.escape_char = escape_char

    def detect_single(self, line: str, line_num: int, start_offset: int) -> tuple:
        """Detects single-line string literals, returning positions of content between quotes."""
        in_string = False
        quote_char = None
        start_pos = -1
        end_pos = -1
        _rsq_len = len(self.raw_str_prefix) if self.raw_str_prefix else 0
        i = start_offset
        while i < len(line):
            char = line[i]
            if not in_string:
                prefix_chars = line[i - _rsq_len:i] if i >= _rsq_len else None
                _is_raw_start = self.raw_str_prefix and prefix_chars == self.raw_str_prefix
                _is_quote_char = char in self.sl_open or (self.raw_quote_char and char == self.raw_quote_char)
                if _is_quote_char or (_is_raw_start and _is_quote_char):
                    in_string = True
                    quote_char = char
                    start_pos = i + (_rsq_len if _is_raw_start else 1)
                    i += _rsq_len if _is_raw_start else 1
                    continue
            elif in_string and char == self.escape_char and i + 1 < len(line):
                i += 2
                continue
            elif in_string and char == quote_char:
                in_string = False
                end_pos = i
                quote_char = None
                i += 1
                return start_pos, end_pos
            i += 1
        if in_string:
            self.owner.parse_warn(f"Incomplete string literal in file {self.owner.file_name} at line {line_num}")
            self.strip_log.append(f"Incomplete string at line {line_num}, line: '{line}'")
            return start_pos, len(line)
        return -1, -1

    def detect_multi_open(self, line: str) -> tuple:
        """Detects multi-line string opening."""
        for j, open_quote in enumerate(self.ml_open):
            match = re.search(re.escape(open_quote), line)
            if match:
                return match.start(), j
        return -1, -1

    def detect_multi_close(self, line: str, close_token: str, start_offset: int) -> tuple:
        """Detects multi-line string closing, starting from start_offset."""
        match = re.search(re.escape(close_token), line[start_offset:])
        if match:
            return start_offset + match.start(), len(close_token)
        return -1, -1

class CodeCommentStripper(CodeStripper):
    """Strips comments (single-line and multi-line)."""
    def __init__(self, owner, open_sl_comment: list, open_ml_comment: list, close_ml_comment: list):
        super().__init__(owner)
        self.sl_open = open_sl_comment
        self.ml_open = open_ml_comment
        self.ml_close = close_ml_comment

    def detect_single(self, line: str, line_num: int, start_offset: int) -> tuple:
        """Detects single-line comments."""
        first_comm_pos = -1
        for sl_comment in self.sl_open:
            start_pos = line.find(sl_comment, start_offset)
            if start_pos >= 0 and (first_comm_pos < 0 or start_pos < first_comm_pos):
                first_comm_pos = start_pos
        return first_comm_pos, len(line)

    def detect_multi_open(self, line: str) -> tuple:
        """Detects multi-line comment opening."""
        for j, ml_comment in enumerate(self.ml_open):
            match = re.search(ml_comment, line, re.IGNORECASE)
            if match:
                return match.start(), j
        return -1, -1

    def detect_multi_close(self, line: str, close_token: str, start_offset: int) -> tuple:
        """Detects multi-line comment closing, starting from start_offset."""
        match = re.search(close_token, line[start_offset:], re.IGNORECASE)
        if match:
            return start_offset + match.start(), len(close_token)
        return -1, -1