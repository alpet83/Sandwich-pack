// /tests/test.js, updated 2025-08-01 21:00 EEST
// JavaScript test file with various entities

// Regular function
function simpleFunction() {
    console.log("");
}

// Arrow function
const arrowFunction = () => {
    console.log("");
}

// Function expression
const exprFunction = function expr() {
    console.log("");
}

// Object with methods
const myObject = {
    methods: {
        myMethod() {
            console.log("");
        }
    }
}

// Export default object
export default {
    computed: {
        myComputed() {
            console.log("");
        }
    }
}

// Import statements
import { lib } from "library";
const module = require("module");

// Incomplete string (trap)
function incompleteString() {
    const s = "unclosed { string;
    console.log(s);
}

// TypeScript-specific constructs (for ContentCodeTypeScript)
interface MyInterface {
    method(): void;
}

class MyClass {
    method() {
        console.log("");
    }
}