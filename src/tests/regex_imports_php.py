# /tests/regex_imports.py, created 2025-08-03 10:22 EEST
# Tests IMPORT_REGEX and string replacement for require/include variants

import re
import logging

logging.basicConfig(level=logging.DEBUG)

# Regular expression for imports
IMPORT_REGEX = re.compile(r"^(?P<indent>[ \t]*)(require|include|require_once|include_once)\s+\(*['\"](\S+)['\"]\)*", re.MULTILINE)

# Test content with various import statements
TEST_CONTENT = """\
require "module1.php";
include 'module2.php';
require_once "module3.php";
include_once 'module4.php';
  require "indented_module.php";
require "nested/module.php";
require "";
invalid_require "module5.php"
"""

# Test 1: Parse modules
def test_parse_modules():
    modules = []
    mcount = 0
    for match in IMPORT_REGEX.finditer(TEST_CONTENT):
        module = match.group(3)
        mcount += 1
        if module:
            modules.append(module)
            logging.debug(f"Found module: {module}")
        else:
            logging.debug(f"Strange match: {match.group(0)}")
            
    assert mcount == 6, f"Detected not all imports"
    expected = ["module1.php", "module2.php", "module3.php", "module4.php", "indented_module.php", "nested/module.php"]
    assert modules == expected, f"Expected modules {expected}, got {mcount} = {modules}"
    logging.info(f"Parsed modules: {modules}")

# Test 2: Protect module names
def test_protect_modules():
    protected_content = re.sub(
        r"^(?P<indent>[ \t]*)(require|include|require_once|include_once)\s+\(*['\"]([^'^\"]+)['\"]\)*",
        r'\g<indent>\g<2> ""\g<3>""',
        TEST_CONTENT,
        flags=re.MULTILINE
    )
    expected_lines = [
        'require ""module1.php"";',
        "include \"\"module2.php\"\";",
        'require_once ""module3.php"";',
        'include_once ""module4.php"";',
        '  require ""indented_module.php"";',
        'require ""nested/module.php"";',
        'require "";',
        'invalid_require "module5.php"'
    ]
    result_lines = protected_content.splitlines()
    assert result_lines == expected_lines, f"Expected lines {expected_lines}, got {result_lines}"
    logging.info(f"Protected content:\n{protected_content}")

if __name__ == "__main__":
    test_parse_modules()
    test_protect_modules()
    logging.info("All tests passed!")