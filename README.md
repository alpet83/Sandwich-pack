# Sandwich Pack CLI and Library Documentation

## Purpose

The `sandwich_pack` library and `spack` CLI utility are designed for **client-side analysis and packaging of complex software projects and chat data** to enable efficient processing by AI systems, such as large language models (LLMs). They transform source files and chat posts into a structured, compact format called "sandwiches" and generate a comprehensive JSON index with metadata to facilitate AI-driven analysis, modification, or debugging. The library supports Rust, Vue, JavaScript, Python, Markdown, TOML, and chat-related content (posts, rules).

## Library Usage

The `SandwichPack` class in `/lib/sandwich_pack.py` provides a programmatic interface for packing content. It uses a modular structure with a base `ContentBlock` class and specialized classes for different content types, dynamically loaded from `lib/*_block.py`.

### Example

```python
from lib.sandwich_pack import SandwichPack, ContentBlock

content = [
    ContentBlock("fn main() {}", ".rs", "/main.rs", "2025-07-15 08:00:00Z"),
    ContentBlock("Hello @attach#1", ":post", "chat_1_post_1", "2025-07-15 08:01:00Z", post_id=1, chat_id=1, user_id=1, relevance=0)
]
packer = SandwichPack(max_size=80_000)
result = packer.pack(content)
print(result["index"])  # JSON index
for i, sandwich in enumerate(result["sandwiches"], 1):
    with open(f"sandwich_{i}.txt", "w") as f:
        f.write(sandwich)
```

### Modules

- **/lib/content_block.py**:
  - `ContentBlock`: Base class with fields `content_text`, `content_type` (string, e.g., `.rs`, `:post`), `file_name`, `timestamp`, `length`, `tokens`, `post_id`, `chat_id`, `user_id`, `relevance`. Method `parse_content()` is a stub for `.toml`, `.md`, `.markdown`, `:rules`.
- **/lib/rust_block.py**:
  - `ContentCodeRust`: Parses `.rs` files for structs, traits, functions, and dependencies (modules, imports, calls).
- **/lib/vue_block.py**:
  - `ContentCodeVue`: Parses `.vue` files for components and imports.
- **/lib/js_block.py**:
  - `ContentCodeJs`: Parses `.js` files for functions and imports/requires.
- **/lib/python_block.py**:
  - `ContentCodePython`: Parses `.py` files for functions, classes, and imports.
- **/lib/sandwich_pack.py**:
  - `SandwichPack`: Main class with methods:
    - `load_block_classes()`: Loads `*_block.py` modules.
    - `supported_type(content_type)`: Checks if content type is supported.
    - `create_block()`: Creates a block for a given content type.
    - `pack(blocks)`: Packs `ContentBlock` instances into sandwiches and index.

### Parameters

- **max_size**: Maximum size of a sandwich file in bytes (default: 80,000).
- **system_prompt**: Optional prompt describing content format for LLMs (default: None, set in MCP).
- **blocks**: List of `ContentBlock` instances with:
  - `content_text`: Content string.
  - `content_type`: String (e.g., `.rs`, `.vue`, `.js`, `.py`, `.toml`, `.md`, `.markdown`, `:post`, `:rules`).
  - `file_name`: Optional file name or identifier.
  - `timestamp`: Modification time (YYYY-MM-DD HH:MM:SSZ).
  - `post_id`, `chat_id`, `user_id`, `relevance`: Optional for `:post`.

### Output

- **index**: JSON string with metadata, datasheet, and dependencies.
- **sandwiches**: List of strings, each representing a sandwich file.

## CLI Usage

Run the CLI utility from the project root:

```bash
python spack.py
```

- **Input**: Scans current directory (`.`) for source files (`.rs`, `.vue`, `.js`, `.py`, `.md`, `.markdown`) and root for configuration files (`.toml`). Files are assumed to be in UTF-8 (with BOM support via `utf-8-sig`).
- **Output**:
  - `sandwich_N.txt`: Text files with content wrapped in tags (`<rustc>`, `<vue>`, `<jss>`, `<python>`, `<document>`, `<post>`, `<rules>`).
  - `sandwiches_index.json`: JSON index with metadata.
- **Behavior**: Exits with an error if no files are collected.

## Sandwich File Format

Each `sandwich_N.txt` contains content blocks:
- **Code**:
  - Rust: `<rustc src="/path/to/file.rs" mod_time="YYYY-MM-DD HH:MM:SSZ">...</rustc>`
  - Vue: `<vue src="/path/to/file.vue" mod_time="YYYY-MM-DD HH:MM:SSZ">...</vue>`
  - JavaScript: `<jss src="/path/to/file.js" mod_time="YYYY-MM-DD HH:MM:SSZ">...</jss>`
  - Python: `<python src="/path/to/file.py" mod_time="YYYY-MM-DD HH:MM:SSZ">...</python>`
  - TOML/Markdown: `<document src="/file.toml" mod_time="YYYY-MM-DD HH:MM:SSZ">...</document>`
- **Posts**: `<post src="identifier" mod_time="YYYY-MM-DD HH:MM:SSZ" post_id="N" chat_id="N" user_id="N" relevance="N">...</post>`
- **Rules**: `<rules src="identifier" mod_time="YYYY-MM-DD HH:MM:SSZ">...</rules>`

Example:
```text
<rustc src="/main.rs" mod_time="2025-07-15 08:00:00Z">
fn main() { ... }
</rustc>
<post src="chat_1_post_1" mod_time="2025-07-15 08:01:00Z" post_id="1" chat_id="1" user_id="1" relevance="0">
Hello @attach#1
</post>
```

## Index File Format (`sandwiches_index.json`)

```json
{
  "packer_version": "0.3.0",
  "context_date": "YYYY-MM-DD HH:MM:SSZ",
  "templates": {
    "filelist": "file_name,md5,tokens,timestamp",
    "entities": "vis(pub/prv),type,name,tokens"
  },
  "dep_format": "modules: details[:file_id] (str); imports: index (int) or details[:file_id] (str); calls: index (int)",
  "system_prompt": null,
  "datasheet": {
    "project_root": "/app",
    "backend_address": "http://localhost:8080",
    "frontend_address": "http://vps.vpn:8008",
    "resources": {
      "database": "sqlite:///app/data/multichat.db",
      "log_file": "/app/logs/colloquium_core.log"
    }
  },
  "files": ["file_name,md5,tokens,timestamp"],
  "entities": ["vis,type,name,tokens"],
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
```

## Context Restoration

- Load `sandwiches_index.json` to access metadata and datasheet.
- Navigate to `sandwich_N.txt` using `start_line` for targeted analysis.
- Update `relevance` for posts based on LLM references.
- Use `datasheet` for project context (e.g., paths, addresses).

## Limitations

- Dependency resolution is heuristic-based and may miss complex imports.
- Entity extraction for `.vue`, `.js`, `.py` is basic and may need refinement.
- Large projects require multiple sandwiches, managed via the index.
- Files must be in UTF-8 (with BOM support via `utf-8-sig`).

## Future Improvements

- Improve entity and dependency extraction for `.vue`, `.js`, `.py`.
- Support additional content types (e.g., `:markdown` explicitly).
- Optimize index size with shorter field names.
- Add versioning for indexes.

## Contributing

- Add new block classes in `/lib/*_block.py` with `SandwichPack.register_block_class`.
- Enhance entity/dependency extraction for other languages.
- Submit issues or PRs to the project repository.
```