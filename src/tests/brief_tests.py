# /tests/brief_tests.py, updated 2025-08-05 16:00 EEST
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


def dump_entities(ent_list: list):
    dump = []
    for e in ent_list:
        dump.append(str(e))
    logging.info("Found entities " + "\n\t".join(dump))


class TestParsersBrief(unittest.TestCase):
    def setUp(self):
        self.timestamp = "2025-08-01T11:00:00Z"

    def entity_check(self, entity, ent_type: str, ent_name: str):
        self.assertEqual(entity["type"], ent_type, f"Expected valid type `{ent_type}`")
        self.assertEqual(entity["name"], ent_name, f"Expected valid name `{ent_name}`")

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
        ent_list = result["entities"]
        dump_entities(ent_list)
        self.assertEqual(len(ent_list), 2, f"Expected 2 entities, got {len(result['entities'])}")
        self.assertEqual(ent_list[0]["type"], "function", "Expected function entity")
        self.assertEqual(ent_list[0]["name"], "test_function", "Expected function name test_function")

        self.assertEqual(ent_list[1]["type"], "structure", "Expected structure entity")
        self.assertEqual(ent_list[1]["name"], "TestStruct", "Expected structure name TestStruct")


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
        ent_list = result["entities"]
        dump_entities(ent_list)
        self.assertEqual(len(ent_list), 2, f"Expected 2 entities, got {len(result['entities'])}")
        self.entity_check(ent_list[0], "component", "App")
        self.entity_check(ent_list[1], "method", "testFunction")

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
        ent_list = result["entities"]
        dump_entities(ent_list)
        self.assertEqual(len(ent_list), 1, f"Expected 1 entity, got {len(result['entities'])}")
        self.entity_check(ent_list[0], "function", "test_function")

    def test_python_parser(self):
        """Test Python parser for one function and one class."""
        logging.info("---------------- test python parsing -------------")
        content = """
def test_function():
    print("")

class TestClass:
    def test_method(self):
        print("")
"""
        block = ContentCodePython(content, ".py", "test.py", self.timestamp)
        block.strip_strings()
        block.strip_comments()
        logging.info(f"Python clean_lines:\n{block.clean_lines[1:]}")
        result = block.parse_content()
        ent_list = result["entities"]
        dump_entities(ent_list)
        self.assertEqual(len(ent_list), 3, f"Expected some entities, got {len(result['entities'])}")
        self.entity_check(ent_list[0], "function", "test_function")
        self.entity_check(ent_list[1], "class", "TestClass")
        self.entity_check(ent_list[2], "method", "test_method")

    def test_js_parser(self):
        """Test JavaScript parser for one function and one object."""
        logging.info("---------------- test js parsing -------------")
        content = """
function testFunction() {
    console.log("");
}

const testFunction2 = function() {
}
 const testFunction3 = (value: int) => {
 }

const TestObject = {
    methods: {
        testMethod() {
            console.log("");
        }
    }
};
"""
        block = ContentCodeJs(content, ".js", "test.js", self.timestamp)
        block.strip_strings()
        block.strip_comments()
        logging.info(f"JS clean_lines:\n{block.clean_lines[1:]}")
        result = block.parse_content()
        ent_list = result["entities"]
        dump_entities(ent_list)
        self.assertEqual(len(ent_list), 5, f"Expected some entities, got {len(result['entities'])}")
        self.entity_check(ent_list[0], "function", "testFunction")
        self.entity_check(ent_list[1], "function", "testFunction2")
        self.entity_check(ent_list[2], "function", "testFunction3")
        self.entity_check(ent_list[3], "object", "TestObject")
        self.entity_check(ent_list[4], "method", "testMethod")

    def test_php_parser(self):
        """Test PHP parser for one function and one class."""
        logging.info("---------------- test php parsing -------------")
        content = """
<?php
function testFunction() {
    echo "";
}

class TestClass {
    public function testMethod() {
        echo "";
    }
}
"""
        block = ContentCodePHP(content, ".php", "test.php", self.timestamp)
        block.strip_strings()
        block.strip_comments()
        logging.info(f"PHP clean_lines:\n{block.clean_lines[1:]}")
        result = block.parse_content()
        ent_list = result["entities"]
        dump_entities(ent_list)
        self.assertEqual(len(ent_list), 3, f"Expected count entities, got {len(result['entities'])}")
        self.entity_check(ent_list[0], "function", "testFunction")
        self.entity_check(ent_list[1], "class", "TestClass")
        self.entity_check(ent_list[2], "method", "testMethod")


if __name__ == "__main__":
    unittest.main()