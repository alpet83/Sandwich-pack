# /tests/brief_tests.py, updated 2025-08-01 11:53 EEST
# Formatted with proper line breaks and indentation for project compliance.

import unittest
import os
import logging
from lib.content_block import ContentBlock, estimate_tokens
from lib.rust_block import ContentCodeRust
from lib.vue_block import ContentCodeVue
from lib.shellscript_block import ContentShellScript
from lib.python_block import ContentCodePython
from lib.js_block import ContentCodeJs
from lib.php_block import ContentCodePHP

logging.basicConfig(
    level=os.environ.get('LOGLEVEL', 'INFO').upper()
)

class TestParsersBrief(unittest.TestCase):
    def setUp(self):
        self.timestamp = "2025-08-01T11:00:00Z"

    def test_rust_parser(self):
        """Test Rust parser for one function and one struct."""
        logging.info("---------------- test rust parsing -------------")
        content = """
pub fn test_function() {
    println!("");
}

pub struct TestStruct {
    field: i32,
}
"""
        block = ContentCodeRust(content, ".rs", "test.rs", self.timestamp)
        block.strip_strings()
        block.strip_comments()
        logging.info(f"Rust clean_lines:\n{block.clean_lines[1:]}")
        result = block.parse_content()
        self.assertEqual(len(result["entities"]), 2, f"Expected 2 entities, got {len(result['entities'])}")

    def test_vue_parser(self):
        """Test Vue parser for one function and one component."""
        logging.info("---------------- test vue parsing -------------")
        content = """
import { defineComponent } from 'vue';

const App = defineComponent({
    methods: {
        testFunction() {
            console.log('');
        }
    }
});
"""
        block = ContentCodeVue(content, ".vue", "test.vue", self.timestamp)
        block.strip_strings()
        block.strip_comments()
        logging.info(f"Vue clean_lines:\n{block.clean_lines[1:]}")
        result = block.parse_content()
        self.assertEqual(len(result["entities"]), 2, f"Expected 2 entities, got {len(result['entities'])}")

    def test_shell_parser(self):
        """Test Shell parser for one function (no structs in shell)."""
        logging.info("---------------- test shell parsing -------------")
        content = """
# Test struct-like comment for consistency
function test_function() {
    echo ""
}
export -f test_function
"""
        block = ContentShellScript(content, ".sh", "test.sh", self.timestamp)
        block.strip_strings()
        block.strip_comments()
        logging.info(f"Shell clean_lines:\n{block.clean_lines[1:]}")
        result = block.parse_content()
        self.assertEqual(len(result["entities"]), 1, f"Expected 1 entity, got {len(result['entities'])}")

    def test_python_parser(self):
        """Test Python parser for one function and one class."""
        logging.info("---------------- test python parsing -------------")
        content = """
def test_function():
    print("")

class TestClass:
    value = 0
"""
        block = ContentCodePython(content, ".py", "test.py", self.timestamp)
        block.strip_strings()
        block.strip_comments()
        logging.info(f"Python clean_lines:\n{block.clean_lines[1:]}")
        result = block.parse_content()
        self.assertEqual(len(result["entities"]), 2, f"Expected 2 entities, got {len(result['entities'])}")

    def test_js_parser(self):
        """Test JavaScript parser for one function and one object."""
        logging.info("---------------- test js parsing -------------")
        content = """
function testFunction() {
    console.log("");
}

const TestObject = {
    value: 0
};
"""
        block = ContentCodeJs(content, ".js", "test.js", self.timestamp)
        block.strip_strings()
        block.strip_comments()
        logging.info(f"JS clean_lines:\n{block.clean_lines[1:]}")
        result = block.parse_content()
        self.assertEqual(len(result["entities"]), 2, f"Expected 2 entities, got {len(result['entities'])}")

    def test_php_parser(self):
        """Test PHP parser for one function and one class."""
        logging.info("---------------- test php parsing -------------")
        content = """
<?php
function testFunction() {
    echo "";
}

class TestClass {
    public $value = 0;
}
"""
        block = ContentCodePHP(content, ".php", "test.php", self.timestamp)
        block.strip_strings()
        block.strip_comments()
        logging.info(f"PHP clean_lines:\n{block.clean_lines[1:]}")
        result = block.parse_content()
        self.assertEqual(len(result["entities"]), 2, f"Expected 2 entities, got {len(result['entities'])}")

if __name__ == "__main__":
    unittest.main()