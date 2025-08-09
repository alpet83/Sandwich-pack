# /tests/test_py_parse.py, created 2025-08-03 14:42 EEST
# Formatted with proper line breaks and indentation for project compliance.

import unittest
import os
import json
import logging
from lib.content_block import ContentBlock, estimate_tokens
from lib.python_block import ContentCodePython

logging.basicConfig(
    level=os.environ.get('LOGLEVEL', 'INFO').upper()
)

g_blocks = {}

def code_block(file_name: str, content: str):
    keys = g_blocks.keys()
    if g_blocks.get(file_name, False):
        return g_blocks[file_name]
    logging.debug(f" Creating block for {file_name}, exists {keys}")
    block = ContentCodePython(content, ".py", file_name, "2025-08-03T14:00:00Z")
    logging.debug(f" =================================== Stripping block {file_name} ====================================== ")
    block.strip_strings()
    block.strip_comments()
    logging.debug(f" Clean_lines:\n" + "\n".join(block.clean_lines))
    logging.debug(f" =================================== Parsing block {file_name} ====================================== ")
    block.parse_content()
    g_blocks[file_name] = block
    return block

class TestPyParse(unittest.TestCase):
    def setUp(self):
        self.file_path = "test.py"
        self.ref_path = "py_parse_ref.json"
        with open(self.file_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.clean_file = "/app/tests/test.py.cln"
        self.block = code_block(self.file_path, content)
        self.block.save_clean(self.clean_file)
        with open(self.ref_path, "r", encoding="utf-8") as f:
            self.reference = json.load(f)

    def test_parse_content(self):
        print("------------------------- test parse content ----------------------")
        _b = self.block
        result = _b.parse_content()
        entities = result["entities"]
        dependencies = result["dependencies"]
        print("Detected entities:")
        for i, e in enumerate(entities):
            print(f" E{i + 1} \t{e}")
        expected_entities = self.reference["entities"]
        expected_deps = self.reference["dependencies"]
        self.assertEqual(len(entities), len(expected_entities), f"Expected {len(expected_entities)} entities, got {len(entities)}")
        fields = ['name', 'type', 'first_line', 'last_line', 'visibility', 'tokens']
        fails = []

        for i, ref_entity in enumerate(expected_entities):
            if i >= len(entities):
                fails.append(f"Entities detected less than {len(expected_entities)}")
                break
            best = []
            best_i = i
            name = ref_entity['name']
            for j, entity in enumerate(entities):
                matches = []
                for field in fields:
                    if entity.get(field) == ref_entity.get(field):
                        matches.append(field)
                        continue
                    elif i == j:
                        logging.warning(f"\t for entity {name} field {field} = `{entity.get(field)}` vs expected `{ref_entity.get(field)}` ")
                    break
                if ('name' in matches) and len(matches) > len(best):
                    best_i = j
                    best = matches
                if len(matches) == len(fields):
                    break
            if len(best) == len(fields):
                continue
            elif len(best) > 0:
                fails.append(f"\tE{i + 1} `{name}` only matched " + ",".join(best))
            else:
                fails.append(f"\tE{i + 1} for `{name}` nothing detected. Expected at index '{entities[best_i]}' ")

        self.assertEqual(len(fails), 0, f"Not found entities:\n" + "\n".join(fails))
        print("Parse content strip log:\n\t", "\n\t".join(_b.strip_log))
        print("Detected dependencies:", dependencies)
        print("Expected dependencies:", expected_deps)
        self.assertEqual(dependencies, expected_deps, f"Dependencies mismatch: expected {expected_deps}, got {dependencies}")
        print("----------------------- TEST PASSED ---------------------------------------")

if __name__ == "__main__":
    unittest.main()