// /tests/test.rs, updated 2025-07-31 16:59 EEST
// Однострочная строка с фигурными скобками
pub fn simple_function() {
    let s = "";
    println!("{}", s);
}

// Многострочная RAW-строка
pub fn raw_string_function() {
    let raw = r#"struct Inner { x: i32 }"#;
    println!("{}", raw);
}

// Многострочный комментарий
pub fn comment_function() {
    /* let s = ""; */
    println!("");
}

// Однострочный комментарий
pub fn single_comment_function() {
    // let s = "";
    println!("");
}

// Вложенная структура
pub struct Outer {
    inner: Inner,
}

struct Inner {
    x: i32,
}

// Незакрытая строка (ловушка)
pub fn incomplete_string() {
    let s = "unclosed { string;
    println!("{}", s);
}

// Трейт и его реализация (ловушка)
pub trait ExampleTrait {
    fn trait_method(&self);
}

impl ExampleTrait for Outer {
    fn trait_method(&self) {
        println!("");
    }
}

// Модуль с функцией
pub mod logger {
    pub fn logger_function() {
        println!("");
    }
}

// Дополнительный модуль для тестирования
pub mod extra_module {
    pub struct ExtraStruct {
        value: i32,
    }
    pub fn extra_function() {
        println!("");
    }
}

// Незакрытый многострочный комментарий (ловушка)
pub fn incomplete_comment() {
    /* let s = "";
    println!("{}", s);
}