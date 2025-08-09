# /lib/iter_regex.py, updated 2025-08-08 12:25 EEST
# Formatted with proper line breaks and indentation for project compliance.

import re
import logging


class IterativeRegex:
    """Iterative regex parser for modular pattern matching."""

    def __init__(self):
        """Initialize with empty token list."""
        self.tokens = []  # List of (regex_part: str, fields: list, detect_points: int)
        self.max_points = 0

    def add_token(self, regex_part: str, fields: list, detect_points: int):
        """Add a regex token with associated fields and weight.

        Args:
            regex_part (str): Partial regex pattern (e.g., r"impl\s+").
            fields (list): List of group names captured by this token (e.g., ["name"]).
            detect_points (int): Weight for hit_rate calculation.
        """
        try:
            re.compile(regex_part)  # Validate regex
            self.tokens.append((regex_part, fields, detect_points))
            self.max_points += detect_points
        except re.error as e:
            logging.error(f"Failed to compile regex token {regex_part}: {str(e)}")
            raise
        return self

    def all_matches(self, content_text: str):
        """Find all matches starting with the base token.

        Args:
            content_text (str): Text to parse.

        Returns:
            list: List of match objects for the base token.
        """
        if not self.tokens:
            logging.error("No tokens defined for matching")
            return []
        base_regex = self.tokens[0][0]  # First token is base
        try:
            matches = list(re.finditer(base_regex, content_text, re.MULTILINE))
            if matches:
                logging.debug(f"Found {len(matches)} base matches for {base_regex}")
            else:
                logging.debug(f"No base matches for {base_regex} in {content_text.strip()}")
            return matches
        except re.error as e:
            logging.error(f"Failed to match base regex {base_regex}: {str(e)}")
            return []

    def validate_match(self, content_text: str, start_offset: int):
        """Validate a match by applying a full regex from tokens up to the current iteration.

        Args:
            content_text (str): Full text to validate against.
            start_offset (int): Starting position of the base match.

        Returns:
            dict: {'match': match object, 'hit_rate': float, 'end_offset': int}
        """
        if not self.tokens:
            logging.error("No tokens defined for validation")
            return {'match': None, 'hit_rate': 0.0, 'end_offset': start_offset}
        assert start_offset >= 0, f"invalid start offset {start_offset}"
        total_points = 0
        last_match = None
        end_offset = start_offset
        current_points = 0
        full_regex = ""
        best_regex = ""
        line = content_text[start_offset:].splitlines()[0]
        for i, token in enumerate(self.tokens, 1):
            # Build full regex up to current token
            full_regex += token[0]
            current_points += token[2]
            try:
                found = None
                present = []
                matches = list(re.finditer(full_regex, content_text, re.MULTILINE))
                for match in matches:
                    loc = match.start()
                    if loc == start_offset:
                        found = match
                        break
                    else:
                        present.append(loc)
                if found:
                    last_match = found
                    total_points = current_points
                    end_offset = found.end()
                    best_regex = full_regex
                else:
                    logging.debug(f"\t#{i} Failed full regex {full_regex} at offset {start_offset}, line: {line}. Present only at {present}")
                    break
            except re.error as e:
                logging.error(f"Error matching full regex {full_regex}: {str(e)}")
                break

        if best_regex:
            logging.debug(f" \t Matched best regex {best_regex}, points: {total_points}, end_offset: {end_offset}")

        hit_rate = total_points / self.max_points if self.max_points > 0 else 0.0
        return {
            'match': last_match,
            'hit_rate': hit_rate,
            'end_offset': end_offset
        }