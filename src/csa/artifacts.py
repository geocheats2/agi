"""Artifact store: local, append-friendly files under a per-task directory.

Each write is recorded as an artifact file; content is hashable (integrity).
Prototype side effects are local only (D-07).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass
class Artifact:
    ref: str            # e.g. <task_id>/step3-work.txt
    content: str
    sha256: str
    size: int


class ArtifactStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def write(self, task_id: str, name: str, content: str) -> Artifact:
        if not _ID_RE.match(task_id) or not _ID_RE.match(name):
            raise ValueError(f"unsafe artifact name: task={task_id!r} name={name!r}")
        run_dir = self.root / task_id
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / name
        data = content.encode("utf-8")
        path.write_bytes(data)  # idempotent: same ref, rewritten identically
        return Artifact(ref=f"{task_id}/{name}", content=content,
                        sha256=hashlib.sha256(data).hexdigest(), size=len(data))

    def read(self, ref: str) -> Artifact:
        if not _ID_RE.match(ref.replace("/", ".")) or ".." in ref:
            raise ValueError(f"unsafe artifact ref: {ref!r}")
        path = self.root / ref
        if not path.is_file():
            raise FileNotFoundError(f"artifact not found: {ref}")
        data = path.read_bytes()
        return Artifact(ref=ref, content=data.decode("utf-8"),
                        sha256=hashlib.sha256(data).hexdigest(), size=len(data))

    def exists(self, ref: str) -> bool:
        if not ref or "/" not in ref:
            return False
        return (self.root / ref).is_file()
