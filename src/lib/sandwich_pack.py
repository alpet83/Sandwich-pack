# /lib/sandwich_pack.py, updated 2025-08-05 16:00 EEST
# Formatted with proper line breaks and indentation for project compliance.

import hashlib
import importlib.util
import os
import re
import logging
import datetime
import json
import math
import traceback
from pathlib import Path
from .content_block import ContentBlock, estimate_tokens
from .deps_builder import organize_modules


def compute_md5(content: str) -> str:
    return hashlib.md5(content.encode("utf-8")).hexdigest()


class SandwichPack:
    _block_classes = []

    def __init__(self, project_name: str, max_size: int = 42_000, token_limit=131_000, system_prompt=None, compression=False):
        self.project_name = project_name
        self.max_size = max_size
        self.token_limit = token_limit
        self.entity_rev_map = {}
        self.system_prompt = system_prompt
        self.compression = compression
        self.datasheet = {
            "project_root": "/app",
            "backend_address": "http://localhost:8080",
            "frontend_address": "http://vps.vpn:8008",
            "resources": {
                "database": "sqlite:///app/data/multichat.db",
                "log_file": "/app/logs/colloquium_core.log"
            }
        }
        self.busy_ids = set()

    @classmethod
    def register_block_class(cls, block_class):
        logging.debug(f"Registering block class: {block_class.__name__}")
        cls._block_classes.append(block_class)

    @classmethod
    def load_block_classes(cls):
        for module in Path(__file__).parent.glob("*_block.py"):
            module_name = module.stem
            if module_name == "content_block":
                continue
            try:
                spec = importlib.util.spec_from_file_location(module_name, module)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                logging.debug(f"Loaded module: {module_name}")
            except Exception as e:
                logging.error(f"Failed to load module {module_name}: {str(e)}")
                stack = traceback.format_exception(type(e), e, e.__traceback__)
                logging.info(f"TRACEBACK: " + ''.join(stack))
        return cls._block_classes

    @classmethod
    def supported_type(cls, content_type: str) -> bool:
        for block_class in cls._block_classes:
            if content_type in block_class.supported_types:
                logging.debug(f"Supported content_type={content_type} by {block_class.__name__}")
                return True
        logging.debug(f"Content_type={content_type} falls back to ContentBlock")
        return content_type in ContentBlock.supported_types

    @classmethod
    def create_block(cls, content_text: str, content_type: str, file_name=None,
                    timestamp=None, **kwargs) -> ContentBlock:
        for block_class in cls._block_classes:
            if content_type in block_class.supported_types:
                logging.debug(f"Creating block with {block_class.__name__} for content_type={content_type}")
                return block_class(content_text, content_type, file_name, timestamp, **kwargs)
        logging.debug(f"Creating default ContentBlock for content_type={content_type}")
        return ContentBlock(content_text, content_type, file_name, timestamp, **kwargs)

    def generate_unique_file_id(self) -> int:
        file_id = 0
        while file_id in self.busy_ids:
            file_id += 1
        self.busy_ids.add(file_id)
        logging.debug(f"Generated unique file_id={file_id}")
        return file_id

    def find_entity(self, e_type: str, e_name: str, file_id=None):
        key = (file_id, e_type, e_name) if file_id is not None else (None, e_type, e_name)
        return self.entity_rev_map.get(key, -1)

    def pack(self, blocks, users=None) -> dict:
        """Packs content blocks into sandwiches with an index including entity boundaries."""
        try:
            self.busy_ids.clear()
            file_map = {}
            file_list = []
            entity_stor = {}
            entities_list = []
            name_to_locations = {}
            module_map = {}
            module_list = []
            parsed_blocks = []
            file_blocks = 0

            for block in blocks:
                if block.content_type != ":post" and block.file_id is not None:
                    self.busy_ids.add(block.file_id)
                    file_blocks += 1

            logging.debug(f"Pack started: input {len(blocks)} included {file_blocks} files blocks")

            for block in blocks:
                if block.content_type != ":post" and block.file_name:
                    # file_id - четко указывает на ссылку файла из БД, он привязан к блоку намертво
                    file_id = block.file_id if block.file_id is not None else self.generate_unique_file_id()
                    file_map[block.file_name] = file_id
                    block.file_id = file_id
                    file_list.append(
                        f"{file_id},{block.file_name},{compute_md5(block.to_sandwich_block())}," +
                        f"{block.tokens},{block.timestamp}"
                    )
                block.strip_strings()
                block.strip_comments()
                parsed = block.parse_content()
                parsed_blocks.append((block, parsed))
                if block.file_name and parsed["entities"]:
                    for ent in parsed["entities"]:
                        name = ent['name']
                        file_id = block.file_id or file_map.get(block.file_name)
                        if "first_line" not in ent or "last_line" not in ent:
                            logging.warning(
                                f"Entity {name} in file {block.file_name} missing first_line or last_line"
                            )
                            continue
                        key = (block.file_name, ent["type"], name)
                        if key not in entity_stor:
                            entity_stor[key] = len(entities_list)  # global index of entity
                            vis_short = "pub" if ent["visibility"] == "public" else "prv"
                            e_type = ent["type"]
                            name_to_locations.setdefault(name, []).append((block.file_name, e_type))
                            start_line = ent["first_line"]
                            end_line = ent["last_line"]
                            parent = ent.get("parent", "")
                            entities_list.append(
                                f"{vis_short},{e_type},{parent},{name},{file_id},{start_line}-{end_line},{ent['tokens']}"
                            )
                            self.entity_rev_map[(file_id, ent["type"], name)] = len(entities_list) - 1

                for module in parsed["dependencies"]["modules"]:
                    if module not in module_map:
                        module_map[module] = len(module_list)
                        module_list.append(module)

            #  список файлов и блоков упорядочивается по зависимостям, порядок file_id предполагаемо станет хаотичным
            # sorted_files, blocks = organize_modules(file_list, [b[0] for b in parsed_blocks])

            current_size = 0
            current_tokens = 0
            current_content = []
            current_index = []
            current_sw_index = 1
            sandwiches = []
            global_index = {
                "packer_version": "0.6",
                "context_date": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ"),
                "templates": {
                    "filelist": "file_id,file_name,md5,tokens,timestamp",
                    "users": "user_id,username,role",
                    "entities": "vis(pub/prv),type,parent,name,file_id,start_line-end_line,tokens"
                },
                "project_name": self.project_name,
                "datasheet": self.datasheet,
                "entities": entities_list,
                "files": file_list,
                "users": users or []
            }

            deep_index = {
                "templates": {
                    "entities": "vis(pub/prv),type,parent,name,file_id,start_line-end_line,tokens",
                    "modules": "module_name"
                },
                "dep_format": (
                    "modules: index (int) referencing modules list; " +
                    "imports: tuple (file_id, entity_name) referencing entities list"
                ),
                "modules": module_list,
                "sandwiches": []
            }

            current_line = 1
            processed = 0
            total_blocks = len(parsed_blocks)
            for block, parsed in parsed_blocks:
                logging.debug(f" ================= PROCESSING BLOCK type {block.content_type}, file_id {block.file_id} ==================== ")
                if self.compression:
                    block.compress(self.entity_rev_map, file_map)
                block_str = block.to_sandwich_block()
                block_size = len(block_str.encode("utf-8"))
                block_tokens = block.tokens
                block_lines = block_str.count("\n") + 1
                processed += 1
                target_size = current_size + block_size
                target_tks = current_tokens + block_tokens

                if target_size > self.max_size or target_tks > self.token_limit:
                    logging.debug(f"Sandwich #{current_sw_index} reached maximum size, target_size = {target_size}, target_tks = {target_tks} storing and creating new")
                    sandwiches.append("".join(current_content))
                    deep_index["sandwiches"].append({
                        "file": f"sandwich_{current_sw_index}.txt",
                        "blocks": current_index
                    })
                    current_size = 0
                    current_sw_index += 1
                    current_content = []
                    current_index = []
                    current_tokens = 0
                    current_line = 1

                block_data = {
                    "start_line": current_line
                }
                if block.content_type == ":post":
                    block_data["post_id"] = block.post_id
                elif block.file_id is not None:
                    block_data["file_id"] = block.file_id
                if parsed.get('modules'):
                    block_data["modules"] = [module_map[module] for module in parsed["modules"]]
                if parsed.get('imports'):
                    block_data["imports"] = []
                    for ent_name, mod_name in parsed["imports"].items():
                        mod_path = f"/{mod_name.replace('.', '/')}.py" if mod_name.startswith('lib.') else f"/tests/{mod_name}.py"
                        mod_file_id = file_map.get(mod_path)
                        for ent_type in ("function", "interface", "class", "struct", "method", "module", "component", "object"):
                            idx = self.find_entity(ent_type, ent_name, mod_file_id)
                            if idx >= 0:
                                block_data["imports"].append((mod_file_id, ent_name))
                                break
                        else:
                            if block.file_name and "/tests/" in block.file_name:
                                block_data["imports"].append((mod_file_id, ent_name))
                    block_data["imports"].sort()
                if block.file_name and parsed["entities"]:
                    ent_uids = [entity_stor[(block.file_name, e["type"], e["name"])] for e in parsed["entities"]]
                    block_data["entities"] = sorted(ent_uids)
                current_content.append(block_str + "\n")
                current_index.append(block_data)
                current_size += block_size
                current_tokens += block_tokens
                current_line += block_lines

            if current_content:
                sandwiches.append("".join(current_content))
                deep_index["sandwiches"].append({
                    "file": f"sandwich_{current_sw_index}.txt",
                    "blocks": current_index
                })

            logging.debug(f" Processed {processed} / {total_blocks} blocks, packing complete")

            return {
                "index": json.dumps(global_index, indent=2),
                "deep_index": json.dumps(deep_index, indent=2),
                "sandwiches": sandwiches
            }
        except Exception as e:
            logging.error(f"#ERROR: Failed to pack blocks: {str(e)}")
            traceback.print_exc()
            raise