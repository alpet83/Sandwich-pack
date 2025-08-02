# /lib/sandwich_pack.py, updated 2025-08-01 12:51 EEST
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
from typing import List, Dict, Optional
from .content_block import ContentBlock, estimate_tokens

def compute_md5(content: str) -> str:
    return hashlib.md5(content.encode("utf-8")).hexdigest()

class SandwichPack:
    _block_classes = []

    def __init__(self, project_name: str, max_size: int = 80_000, system_prompt: Optional[str] = None):
        self.project_name = project_name
        self.max_size = max_size
        self.system_prompt = system_prompt
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
            try:
                spec = importlib.util.spec_from_file_location(module_name, module)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                logging.debug(f"Loaded module: {module_name}")
            except Exception as e:
                logging.error(f"Failed to load module {module_name}: {str(e)}")
                stack = traceback.format_exception(type(e), e, e.__traceback__)
                logging.info(f"TRACEBACK: " + ''.join(stack))
        return SandwichPack._block_classes

    @classmethod
    def supported_type(cls, content_type: str) -> bool:
        for block_class in cls._block_classes:
            if content_type in block_class.supported_types:
                logging.debug(f"Supported content_type={content_type} by {block_class.__name__}")
                return True
        logging.debug(f"Content_type={content_type} falls back to ContentBlock")
        return content_type in ContentBlock.supported_types

    @classmethod
    def create_block(cls, content_text: str, content_type: str, file_name: Optional[str] = None,
                    timestamp: Optional[str] = None, **kwargs) -> ContentBlock:
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

    def pack(self, blocks: List[ContentBlock], users: List[Dict] = None) -> Dict[str, any]:
        """Packs content blocks into sandwiches with an index including entity boundaries.

        Args:
            blocks (List[ContentBlock]): List of content blocks to pack.
            users (List[Dict], optional): List of user metadata. Defaults to None.

        Returns:
            Dict[str, any]: Dictionary containing global index, deep index, and sandwiches.
        """
        try:
            self.busy_ids.clear()
            file_map = {}
            file_list = []
            entity_map = {}
            entities_list = []
            name_to_locations = {}

            for block in blocks:
                if block.content_type != ":post" and block.file_id is not None:
                    self.busy_ids.add(block.file_id)

            for block in blocks:
                if block.content_type != ":post" and block.file_name:
                    file_id = block.file_id if block.file_id is not None else self.generate_unique_file_id()
                    file_map[block.file_name] = file_id
                    file_list.append(
                        f"{file_id},{block.file_name},{compute_md5(block.to_sandwich_block())},"
                        f"{block.tokens},{block.timestamp}"
                    )
                block.strip_strings()
                block.strip_comments()
                parsed = block.parse_content()
                if block.file_name and parsed["entities"]:
                    for ent in parsed["entities"]:
                        if "first_line" not in ent or "last_line" not in ent:
                            logging.warning(
                                f"Entity {ent['name']} in file {block.file_name} missing first_line or last_line"
                            )
                            continue
                        key = (block.file_name, ent["type"], ent["name"])
                        if key not in entity_map:
                            entity_map[key] = len(entities_list)
                            vis_short = "pub" if ent["visibility"] == "public" else "prv"
                            file_id = block.file_id or file_map.get(block.file_name)
                            start_line = ent["first_line"]
                            end_line = ent["last_line"]
                            entities_list.append(
                                f"{vis_short},{ent['type']},{ent['name']},"
                                f"{file_id},{start_line}-{end_line},{ent['tokens']}"
                            )
                            name_to_locations.setdefault(ent["name"], []).append((block.file_name, ent["type"]))

            current_size = 0
            current_tokens = 0
            current_content = []
            current_index = []
            current_file_index = 1
            sandwiches = []
            global_index = {
                "packer_version": "0.5",
                "context_date": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ"),
                "templates": {
                    "filelist": "file_id,file_name,md5,tokens,timestamp",
                    "users": "user_id,username,role",
                    "entities": "vis(pub/prv),type,name,file_id,start_line-end_line,tokens"
                },
                "project_name": self.project_name,
                "datasheet": self.datasheet,
                "entities": entities_list,
                "files": file_list,
                "users": users or []
            }

            deep_index = {
                "templates": {
                    "entities": "vis(pub/prv),type,name,file_id,start_line-end_line,tokens"
                },
                "dep_format": (
                    "modules: details[:file_id] (str); "
                    "imports: index (int) or details[:file_id] (str); "
                    "calls: index (int)"
                ),
                "sandwiches": []
            }

            current_line = 1
            for block in blocks:
                parsed = block.parse_content()
                block_str = block.to_sandwich_block()
                block_size = len(block_str.encode("utf-8"))
                block_tokens = block.tokens
                block_lines = block_str.count("\n") + 1

                if current_size + block_size > self.max_size or current_tokens + block_tokens > 20_000:
                    sandwiches.append("".join(current_content))
                    deep_index["sandwiches"].append({
                        "file": f"sandwich_{current_file_index}.txt",
                        "blocks": current_index
                    })
                    current_file_index += 1
                    current_content = []
                    current_index = []
                    current_size = 0
                    current_tokens = 0
                    current_line = 1

                block_data = {
                    "start_line": current_line
                }
                if block.content_type == ":post":
                    block_data["post_id"] = block.post_id
                else:
                    block_data["file_id"] = block.file_id if block.file_id is not None else file_map.get(block.file_name)
                deps = parsed["dependencies"]
                if deps["imports"]:
                    block_data["imports"] = [re.sub(r'\n+', ' ', item).strip() for item in deps["imports"]]
                if deps["modules"]:
                    block_data["modules"] = [re.sub(r'\n+', ' ', item).strip() for item in deps["modules"]]
                if deps["calls"]:
                    block_data["calls"] = deps["calls"]
                if block.file_name and parsed["entities"]:
                    ent_uids = [entity_map[(block.file_name, e["type"], e["name"])] for e in parsed["entities"]]
                    block_data["entities"] = sorted(ent_uids)
                current_content.append(block_str + "\n")
                current_index.append(block_data)
                current_size += block_size
                current_tokens += block_tokens
                current_line += block_lines

            if current_content:
                sandwiches.append("".join(current_content))
                deep_index["sandwiches"].append({
                    "file": f"sandwich_{current_file_index}.txt",
                    "blocks": current_index
                })

            return {
                "index": json.dumps(global_index, indent=2),
                "deep_index": json.dumps(deep_index, indent=2),
                "sandwiches": sandwiches
            }
        except Exception as e:
            logging.error(f"#ERROR: Failed to pack blocks: {str(e)}")
            traceback.print_exc()
            raise