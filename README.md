Sandwich Pack CLI and Library Documentation
Purpose
The sandwich_pack library and spack CLI utility are designed for client-side analysis and packaging of complex software projects and chat data to enable efficient processing by AI systems, such as large language models (LLMs). They transform source files and chat posts into a structured, compact format called "sandwiches" and generate two JSON indexes (main and deep) with metadata to facilitate AI-driven analysis, modification, or debugging. The library supports Rust, Vue, JavaScript, TypeScript, Python, Shell, PHP, Markdown, TOML, and chat-related content (posts, rules).
Library Usage
The SandwichPack class in /lib/sandwich_pack.py provides a programmatic interface for packing content. It uses a modular structure with a base ContentBlock class and specialized classes for different content types, dynamically loaded from lib/*_block.py.
Example
from lib.sandwich_pack import SandwichPack, ContentBlock

content = [
    ContentBlock("fn main() {}", ".rs", "/main.rs", "2025-07-15 08:00:00Z"),
    ContentBlock("Hello @attach#1", ":post", "chat_1_post_1", "2025-07-15 08:01:00Z", post_id=1, chat_id=1, user_id=1, relevance=0)
]
packer = SandwichPack(max_size=80_000)
result = packer.pack(content)
print(result["index"])  # Main JSON index
print(result["deep_index"])  # Deep JSON index
for i, sandwich in enumerate(result["sandwiches"], 1):
    with open(f"sandwich_{i}.txt", "w") as f:
        f.write(sandwich)

Modules

/lib/content_block.py:

ContentBlock: Base class with fields content_text, content_type (string, e.g., .rs, :post), file_name, timestamp, length, tokens, post_id, chat_id, user_id, relevance. Provides strip_strings and strip_comments for cleaning code from string literals and comments, and detect_bounds for determining entity line ranges. Method parse_content() is a stub for .toml, .md, .markdown, :rules.


/lib/rust_block.py:

ContentCodeRust: Parses .rs files for structs, traits, functions, methods, and modules. Supports module prefixing (e.g., logger.logger_function), string and comment cleaning, and differentiates between global functions and trait methods.


/lib/vue_block.py:

ContentCodeVue: Parses .vue files for components, functions, and methods within methods, computed, or watch blocks. Supports string and comment cleaning, and distinguishes between global functions and component methods (e.g., VueComponent::testFunction).


/lib/js_block.py:

ContentCodeJs: Parses .js files for functions, objects, and methods within methods, computed, or watch blocks. Supports string and comment cleaning, and differentiates between global functions and object methods (e.g., TestObject::methodName). Improved in version 0.5 to accurately determine line numbers for entities using find_line for robust parsing and optimized parser order to prioritize function detection, ensuring stable extraction of entities like arrow functions and default exports.
ContentCodeTypeScript: Parses .ts files, extending ContentCodeJs to support TypeScript-specific constructs (interfaces, classes) alongside functions, objects, and methods. Added in version 0.5 with support for string and comment cleaning, and accurate line number detection for entities like interfaces and classes.


/lib/python_block.py:

ContentCodePython: Parses .py files for functions, classes, and methods (including @classmethod and @staticmethod). Supports string and comment cleaning, and distinguishes between global functions and class methods (e.g., TestClass::methodName).


/lib/shellscript_block.py:

ContentShellScript: Parses .sh files for functions, with visibility based on export -f. Supports string and comment cleaning, and uses file-based prefixing for functions (e.g., test::test_function).


/lib/php_block.py:

ContentCodePhp: Parses .php files for functions and classes. Supports string and comment cleaning, and distinguishes between global functions and class methods (e.g., TestClass::methodName).


/lib/sandwich_pack.py:

SandwichPack: Main class with methods:
load_block_classes(): Loads *_block.py modules.
supported_type(content_type): Checks if content type is supported.
create_block(): Creates a block for a given content type.
pack(blocks): Packs ContentBlock instances into sandwiches and two indexes (main and deep).





Parameters

max_size: Maximum size of a sandwich file in bytes (default: 80,000).
system_prompt: Optional prompt describing content format for LLMs (default: None, set in MCP).
blocks: List of ContentBlock instances with:
content_text: Content string.
content_type: String (e.g., .rs, .vue, .js, .ts, .py, .sh, .php, .toml, .md, .markdown, :post, :rules).
file_name: Optional file name or identifier.
timestamp: Modification time (YYYY-MM-DD HH:MM:SSZ).
post_id, chat_id, user_id, relevance: Optional for :post.



Output

index: JSON string for sandwiches_index.json with project metadata, files, entities, and users.
deep_index: JSON string for sandwiches_structure.json with sandwich structure and block dependencies.
sandwiches: List of strings, each representing a sandwich file, linked to deep_index["sandwiches"].

CLI Usage
Run the CLI utility from the project root:
python spack.py


Input: Scans current directory (.) for source files (.rs, .vue, .js, .ts, .py, .sh, .php, .md, .markdown) and root for configuration files (.toml). Files are assumed to be in UTF-8 (with BOM support via utf-8-sig).
Output:
sandwich_N.txt: Text files with content wrapped in tags (<rustc>, <vue>, <jss>, <tss>, <python>, <shell>, <php>, <document>, <post>, <rules>).
sandwiches_index.json: Main JSON index with project metadata, files, entities, and users.
sandwiches_structure.json: Deep JSON index with sandwich structure and block dependencies.


Behavior: Exits with an error if no files are collected.

Sandwich File Format
Each sandwich_N.txt contains content blocks:

Code:
Rust: <rustc src="/path/to/file.rs" mod_time="YYYY-MM-DD HH:MM:SSZ">...</rustc>
Vue: <vue src="/path/to/file.vue" mod_time="YYYY-MM-DD HH:MM:SSZ">...</vue>
JavaScript: <jss src="/path/to/file.js" mod_time="YYYY-MM-DD HH:MM:SSZ">...</jss>
TypeScript: <tss src="/path/to/file.ts" mod_time="YYYY-MM-DD HH:MM:SSZ">...</tss>
Python: <python src="/path/to/file.py" mod_time="YYYY-MM-DD HH:MM:SSZ">...</python>
Shell: <shell src="/path/to/file.sh" mod_time="YYYY-MM-DD HH:MM:SSZ">...</shell>
PHP: <php src="/path/to/file.php" mod_time="YYYY-MM-DD HH:MM:SSZ">...</php>
TOML/Markdown: <document src="/file.toml" mod_time="YYYY-MM-DD HH:MM:SSZ">...</document>


Posts: <post src="identifier" mod_time="YYYY-MM-DD HH:MM:SSZ" post_id="N" chat_id="N" user_id="N" relevance="N">...</post>
Rules: <rules src="identifier" mod_time="YYYY-MM-DD HH:MM:SSZ">...</rules>

Example
<rustc src="/main.rs" mod_time="2025-07-15 08:00:00Z">
fn main() { ... }
</rustc>
<post src="chat_1_post_1" mod_time="2025-07-15 08:01:00Z" post_id="1" chat_id="1" user_id="1" relevance="0">
Hello @attach#1
</post>

Index File Format
The library generates two index files:

Main Index (sandwiches_index.json):Contains project metadata, file list, entity list, and user metadata.{
  "packer_version": "0.5",
  "context_date": "YYYY-MM-DD HH:MM:SSZ",
  "templates": {
    "filelist": "file_id,file_name,md5,tokens,timestamp",
    "users": "user_id,username,role",
    "entities": "vis(pub/prv),type,name,file_id,start_line-end_line,tokens"
  },
  "project_name": "project_name",
  "datasheet": {
    "project_root": "/app",
    "backend_address": "http://localhost:8080",
    "frontend_address": "http://vps.vpn:8008",
    "resources": {
      "database": "sqlite:///app/data/multichat.db",
      "log_file": "/app/logs/colloquium_core.log"
    }
  },
  "files": ["file_id,file_name,md5,tokens,timestamp"],
  "entities": ["vis,type,name,file_id,start_line-end_line,tokens"],
  "users": ["user_id,username,role"]
}


Deep Index (sandwiches_structure.json):Describes the structure of sandwich files, including block details and dependencies.{
  "templates": {
    "entities": "vis(pub/prv),type,name,file_id,start_line-end_line,tokens"
  },
  "dep_format": "modules: details[:file_id] (str); imports: index (int) or details[:file_id] (str); calls: index (int)",
  "sandwiches": [
    {
      "file": "sandwich_N.txt",
      "blocks": [
        {
          "file_id": integer,
          "start_line": integer,
          "imports": ["index or details"],
          "modules": ["details"],
          "calls": [integer],
          "entities": [integer]
        }
      ]
    }
  ]
}



Context Restoration

Load sandwiches_index.json to access project metadata, files, entities, and users.
Load sandwiches_structure.json to navigate sandwich files (sandwich_N.txt) and their blocks using start_line, file_id, and dependency details.
Update relevance for posts based on LLM references.
Use datasheet from sandwiches_index.json for project context (e.g., paths, addresses).
Note: Tools using older index formats (without start_line-end_line in entities) may require updates to handle the new format.

Limitations

Dependency resolution is heuristic-based and may miss complex imports.
Entity extraction for .vue, .js, .ts, .py, .sh, .php is basic, though improved for .js and .ts in version 0.5 with better line number accuracy and TypeScript support.
Large projects require multiple sandwiches, managed via the deep index.
Files must be in UTF-8 (with BOM support via utf-8-sig).

Future Improvements

Enhance dependency extraction for .vue, .js, .ts, .py, .sh, .php to support complex structures (e.g., nested imports, dynamic calls).
Optimize index size with shorter field names.
Add versioning for indexes to improve compatibility with older tools.
Add module/namespace support for .vue, .js, .ts, .py, .php similar to Rust's module prefixing.

Contributing

Add new block classes in /lib/*_block.py with SandwichPack.register_block_class.
Enhance entity/dependency extraction for other languages.
Submit issues or PRs to the project repository.
