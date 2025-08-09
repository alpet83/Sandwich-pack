# /tests/test_php_parse.py, updated 2025-08-02 14:05 EEST
# Formatted with proper line breaks and indentation for project compliance.

import unittest
import json
import logging
from pathlib import Path
from lib.php_block import ContentCodePHP

logging.basicConfig(level=logging.DEBUG)


def entity_dump(ent_list):
    return "\n\t".join(str(e) for e in ent_list)


def code_block(file_name: str, content: str):
    block = ContentCodePHP(
        content_text=content,
        content_type=".php",
        file_name=file_name,
        timestamp="2025-08-02 12:42:00Z",
        file_id=0
    )
    logging.debug(f" =================================== Stripping block {file_name} ====================================== ")
    block.strip_strings()
    block.strip_comments()
    logging.debug(" Clean_lines:\n" + "\n".join(block.clean_lines))
    logging.debug(f"Strip log: " + "\n".join(block.strip_log))
    block.save_clean(file_name + '.cln')
    logging.debug(f" =================================== Parsing block {file_name} ====================================== ")
    return block

class TestPhpParse(unittest.TestCase):
    def setUp(self):
        self.test_file = "test.php"
        self.ref_file = "php_parse_ref.json"
        self.maxDiff = None
        with open(self.test_file, "r", encoding="utf-8-sig") as f:
            content = f.read()
        self.block = code_block(self.test_file, content)

    def test_parse_content(self):
        """Test parsing of test.php content."""
        with open(self.ref_file, "r", encoding="utf-8") as f:
            ref_data = json.load(f)

        result = self.block.parse_content()

        expected_entities = ref_data["entities"]
        expected_deps = ref_data["dependencies"]
        found_entities = result["entities"]
        found_deps = result["dependencies"]
        logging.debug(f" =================================== Checking entities ====================================== ")
        logging.debug(f"Found entities:\n" + entity_dump(found_entities))
        logging.debug(f"Expected entities:\n" + entity_dump(expected_entities))

        fails = []
        for i, (exp, found) in enumerate(zip(expected_entities, found_entities), 1):
            if exp != found:
                for k in exp:
                    if exp[k] != found.get(k):
                        fails.append(f"E{i} `{exp['name']}` unmatched {k}: expected `{exp[k]}`, got `{found.get(k)}`  ")
        self.assertEqual(len(fails), 0, f"Not found entities:\n" + "\n".join(fails))

        logging.debug(f"Found dependencies: {found_deps}")
        logging.debug(f"Expected dependencies: {expected_deps}")
        self.assertEqual(found_deps, expected_deps, f"Dependencies mismatch: expected {expected_deps}, got {found_deps}")

if __name__ == "__main__":
    unittest.main()