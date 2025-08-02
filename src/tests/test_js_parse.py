# /tests/test_js_parse.py, updated 2025-08-01 23:45 EEST
# Formatted with proper line breaks and indentation for project compliance.

import unittest
import os
import json
import logging
from lib.content_block import ContentBlock, estimate_tokens
from lib.js_block import ContentCodeJs, ContentCodeTypeScript

logging.basicConfig(
    level=os.environ.get('LOGLEVEL', 'INFO').upper()
)

g_blocks = {}

def code_block(file_name: str, content: str, is_typescript=False):
    keys = g_blocks.keys()
    if g_blocks.get(file_name,  False):
        return g_blocks[file_name]
    logging.debug(f" Creating block for {file_name}, exists {keys}")
    block_class = ContentCodeTypeScript if is_typescript else ContentCodeJs
    block = block_class(content, ".ts" if is_typescript else ".js", file_name, "2025-08-01T21:00:00Z")
    logging.debug(f" =================================== Stripping block {file_name} ====================================== ")
    block.strip_strings()
    block.strip_comments()
    logging.debug(f" =================================== Parsing block {file_name} ====================================== ")
    block.parse_content()
    g_blocks[file_name] = block
    return block


def _scan_log(log, sub_str):
    found = any(sub_str in msg for msg in log.output)
    print("Log output:", log.output)
    return found


class TestJsParse(unittest.TestCase):
    def setUp(self):
        self.file_path = "test.js"
        self.ref_path = "js_parse_ref.json"
        with open(self.file_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.clean_file = "/app/tests/test.js.cln"
        self.block = code_block(self.file_path, content, is_typescript=self.file_path.endswith(".ts"))
        self.block.save_clean(self.clean_file)
        with open(self.ref_path, "r", encoding="utf-8") as f:
            self.reference = json.load(f)["entities"]

    def test_parse_content(self):
        print("------------------------- test parse content ----------------------")
        _b = self.block
        entities = _b.sorted_entities()
        print("Detected entities:")
        for i, e in enumerate(entities):
            print(f" E{i + 1} \t{e}")
        self.assertEqual(len(entities), len(self.reference), f"Expected {len(self.reference)} entities, got {len(entities)}")
        fields = ['name', 'type', 'first_line', 'last_line', 'visibility', 'tokens']
        fails = []

        for i, ref_entity in enumerate(self.reference):
            if i >= len(entities):
                fails.append(f"Entities detected less than {len(self.reference)}")
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
        print("----------------------- TEST PASSED ---------------------------------------")

    def test_incomplete_cases(self):
        print("------------------------- Incomplete cases test ----------------------")
        _b = self.block
        _warns = ";\t".join(_b.warnings)
        for _must in ["Incomplete string literal"]:
            self.assertIn(_must, _warns, f"Warning '{_must}' was expected")
        print("Incomplete cases warnings:\n\t", "\n\t".join(_b.warnings))
        print("Incomplete cases strip log:\n\t", "\n\t".join(_b.strip_log))
        print("----------------------- TEST PASSED ---------------------------------------")

    def test_js_template_string_no_escape(self):
        print("------------------------- template string no escape ----------------------")
        os.environ['LOGLEVEL'] = 'WARNING'  # Suppress DEBUG logs for stable test
        test_content = '''
        function testTemplate() {
            const s = `test \\ string`;
            const t = `test \\ string ${variable}`;
        }
        '''
        _b = code_block("test_template.js", test_content, is_typescript=False)
        clean_lines = _b.clean_lines
        print("Template string strip log:\n\t", "\n\t".join(_b.strip_log))
        print(f"Clean lines: {clean_lines}")
        self.assertEqual(clean_lines[3].strip(), 'const s = ``;')  # `...`
        self.assertEqual(clean_lines[4].strip(), 'const t = ``;')  # `...${...}`
        print("----------------------- TEST PASSED ---------------------------------------")


    def test_typescript_specific(self):
        print("------------------------- TypeScript specific tests ----------------------")
        os.environ['LOGLEVEL'] = 'WARNING'  # Suppress DEBUG logs for stable test
        self.file_path = "test.ts"
        with open(self.file_path, "r", encoding="utf-8") as f:
            test_content = f.read()
        _b = code_block("test_typescript.ts", test_content, is_typescript=True)
        entities = list(_b.entity_map.values())
        self.assertEqual(len(entities), 2, f"Expected 2 entities, got {len(entities)}")
        self.assertEqual(entities[0]["type"], "interface", "Expected interface entity")
        self.assertEqual(entities[0]["name"], "MyInterface", "Expected interface name MyInterface")
        self.assertEqual(entities[1]["type"], "class", "Expected class entity")
        self.assertEqual(entities[1]["name"], "MyClass", "Expected class name MyClass")
        print("TypeScript entities:\n\t", "\n\t".join([str(e) for e in entities]))
        print("TypeScript strip log:\n\t", "\n\t".join(_b.strip_log))
        print("----------------------- TEST PASSED ---------------------------------------")

if __name__ == "__main__":
    unittest.main()