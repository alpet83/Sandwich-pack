# /tests/test_rust_parse.py, updated 2025-08-01 09:08 EEST
# Formatted with proper line breaks and indentation for project compliance.

import unittest
import os
import json
import logging
from lib.content_block import ContentBlock, estimate_tokens
from lib.rust_block import ContentCodeRust

logging.basicConfig(
    level=os.environ.get('LOGLEVEL', 'INFO').upper()
)

g_block = None

def code_block(file_name, content):
    global g_block
    if g_block is None:
        block = ContentCodeRust(content, ".rs", file_name, "2025-07-29T18:00:00Z")
        block.strip_strings()
        block.strip_comments()
        block.parse_content()
        g_block = block
    return g_block

def _scan_log(log, sub_str):
    found = any(sub_str in msg for msg in log.output)
    print("Log output:", log.output)
    return found

class TestRustParse(unittest.TestCase):
    def setUp(self):
        self.file_path = "test.rs"
        self.ref_path = "rust_parse_ref.json"
        with open(self.file_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.clean_file = "/app/tests/test.rs.cln"
        self.block = code_block(self.file_path, content)
        self.block.save_clean(self.clean_file)
        with open(self.ref_path, "r", encoding="utf-8") as f:
            self.reference = json.load(f)["entities"]

    def test_parse_content(self):
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
                    if entity[field] == ref_entity[field]:
                        # logging.debug(f"\t matched {field} => {entity[field]}, total {len(matches)}")
                        matches.append(field)
                        continue
                    elif i == j:
                        logging.warning(f"\t for entity {name} field {field} = `{entity[field]}` vs expected `{ref_entity[field]}` ")
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

    def test_incomplete_cases(self):
        _b = self.block
        _warns = ";\t".join(_b.warnings)
        for _must in ["Incomplete string literal", "Incomplete entity at line 70"]:
            self.assertIn(_must, _warns, f"Warning '{_must}' was expected")
        print("Incomplete cases warnings:\n\t", "\n\t".join(_b.warnings))
        print("Incomplete cases strip log:\n\t", "\n\t".join(_b.strip_log))

    def test_rust_raw_string_no_escape(self):
        os.environ['LOGLEVEL'] = 'WARNING'  # Suppress DEBUG logs for stable test
        test_content = '''
        fn test_raw() {
            let s = r"test \\ string";
            let t = r#"test \\ string"#;
        }
        '''
        _b = ContentCodeRust(test_content, ".rs", "test_raw.rs", "2025-07-29T18:00:00Z")
        _b.strip_strings()
        _b.strip_comments()
        clean_lines = _b.clean_lines
        self.assertEqual(clean_lines[3].strip(), 'let s = r"";')  # r"..."
        self.assertEqual(clean_lines[4].strip(), 'let t = r#""#;')  # r#...#
        print("Raw string strip log:\n\t", "\n\t".join(_b.strip_log))

if __name__ == "__main__":
    unittest.main()