"""断点续传：每条数据即时保存到磁盘，重启时自动跳过已采集的重复数据。

用法:
    from checkpoint import CheckpointStore

    store = CheckpointStore(Path("heybox_search_cleaned.json"), dedup_key=lambda item: item.get("share_url", ""))
    
    # 加载已有数据（自动）
    print(len(store))  # 已有条数
    
    # 添加新数据，自动去重并立即写入磁盘
    for item in new_items:
        added = store.add(item)  # True=新增, False=重复跳过
    
    # 或者批量添加
    new_count = store.add_batch(new_items)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable


def _atomically_write(path: Path, content: str) -> None:
    """原子写入：先写临时文件再重命名，避免写入中途崩溃导致文件损坏。"""
    tmp = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


class CheckpointStore:
    """即时持久化的数据存储，支持断点续传去重。

    每条数据通过 add() 添加时立即写入磁盘。
    构造时自动加载已有数据，后续新增自动跳过重复项。
    """

    def __init__(self, path: Path, dedup_key: Callable[[dict], str]):
        """
        Args:
            path: 数据文件路径（JSON 数组格式）
            dedup_key: 从单条数据提取去重键的函数，返回空字符串表示不参与去重
        """
        self._path = path
        self._dedup_key = dedup_key
        self._items: list[dict] = []
        self._seen: set[str] = set()
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """延迟加载已有数据。"""
        if self._loaded:
            return
        self._loaded = True
        if not self._path.exists():
            return
        try:
            existing = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                return
            for item in existing:
                key = self._dedup_key(item)
                if key and key not in self._seen:
                    self._seen.add(key)
                    self._items.append(item)
        except (json.JSONDecodeError, OSError):
            pass

    def exists(self, item: dict) -> bool:
        """检查数据是否已存在。"""
        self._ensure_loaded()
        key = self._dedup_key(item)
        return key in self._seen if key else False

    def add(self, item: dict) -> bool:
        """添加一条数据，立即写入磁盘。返回 True 表示新增，False 表示重复已跳过。"""
        self._ensure_loaded()
        key = self._dedup_key(item)
        if key and key in self._seen:
            return False
        if key:
            self._seen.add(key)
        self._items.append(item)
        self._flush()
        return True

    def add_batch(self, items: list[dict]) -> int:
        """批量添加，返回实际新增条数。每添加一条都会触发写入。"""
        count = 0
        for item in items:
            if self.add(item):
                count += 1
        return count

    def _flush(self) -> None:
        """将当前全部数据写入磁盘（原子写入）。"""
        _atomically_write(
            self._path,
            json.dumps(self._items, ensure_ascii=False, indent=2),
        )

    def __len__(self) -> int:
        self._ensure_loaded()
        return len(self._items)

    @property
    def items(self) -> list[dict]:
        """返回当前全部数据的副本。"""
        self._ensure_loaded()
        return list(self._items)
