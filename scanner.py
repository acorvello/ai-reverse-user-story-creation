"""Repository scanner: lists the source files worth sending to the model.

The scanner is conservative. It skips dependency and build folders, binary or very
large files, symbolic links and files that commonly hold secrets. The secret filter
is name-based and is not a guarantee: only run the tool on repositories you are
allowed to analyze, and keep the model local.
"""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_EXTENSIONS = frozenset(
    {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".cs", ".go", ".rb", ".php", ".sql", ".html", ".vue", ".svelte"}
)

DEFAULT_IGNORE_DIRS = frozenset(
    {
        ".git", "node_modules", "dist", "build", "out", "target", "vendor",
        "venv", ".venv", "__pycache__", ".idea", ".vscode", "coverage",
        ".next", ".nuxt", "bin", "obj",
    }
)

DEFAULT_SENSITIVE_PATTERNS = (
    ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "*.keystore",
    "id_rsa*", "id_ed25519*", ".npmrc", ".pypirc",
)


@dataclass(frozen=True)
class ScanConfig:
    max_file_bytes: int = 200_000
    include_extensions: frozenset[str] = field(default=DEFAULT_EXTENSIONS)
    ignore_dirs: frozenset[str] = field(default=DEFAULT_IGNORE_DIRS)
    sensitive_patterns: tuple[str, ...] = field(default=DEFAULT_SENSITIVE_PATTERNS)


@dataclass(frozen=True)
class SourceFile:
    path: str  # relative to the repository root, forward slashes
    size: int
    extension: str


def is_sensitive(filename: str, patterns: tuple[str, ...] = DEFAULT_SENSITIVE_PATTERNS) -> bool:
    name = filename.lower()
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


def scan_repository(root: str | Path, config: ScanConfig | None = None) -> list[SourceFile]:
    """Return the source files under root, in a stable order."""
    cfg = config or ScanConfig()
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")

    found: list[SourceFile] = []
    for dirpath, dirnames, filenames in os.walk(root_path, followlinks=False):
        current = Path(dirpath)
        dirnames[:] = sorted(
            d for d in dirnames if d not in cfg.ignore_dirs and not (current / d).is_symlink()
        )
        for name in sorted(filenames):
            full = current / name
            if full.is_symlink():
                continue
            extension = full.suffix.lower()
            if extension not in cfg.include_extensions:
                continue
            if is_sensitive(name, cfg.sensitive_patterns):
                continue
            size = full.stat().st_size
            if size > cfg.max_file_bytes:
                continue
            found.append(SourceFile(path=full.relative_to(root_path).as_posix(), size=size, extension=extension))
    return found


def _resolve_inside(root: str | Path, rel_path: str) -> Path:
    root_path = Path(root).resolve()
    target = (root_path / rel_path).resolve()
    if root_path not in target.parents:
        raise ValueError(f"Path escapes the repository root: {rel_path}")
    if not target.is_file():
        raise FileNotFoundError(rel_path)
    return target


def line_count(root: str | Path, rel_path: str) -> int:
    """Number of lines of a file inside the repository."""
    target = _resolve_inside(root, rel_path)
    return len(target.read_text(encoding="utf-8", errors="replace").splitlines())


def read_prefix(root: str | Path, rel_path: str, max_chars: int) -> str:
    """Read at most max_chars from a source file inside the repository."""
    if max_chars < 0:
        raise ValueError("max_chars must not be negative")
    target = _resolve_inside(root, rel_path)
    with target.open(encoding="utf-8", errors="replace") as source:
        return source.read(max_chars)


def read_lines(root: str | Path, rel_path: str, start: int = 1, end: int | None = None) -> list[tuple[int, str]]:
    """Read a line range as (line_number, text) pairs. Line numbers start at 1."""
    target = _resolve_inside(root, rel_path)
    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    last = len(lines) if end is None else min(end, len(lines))
    return [(number, lines[number - 1]) for number in range(max(start, 1), last + 1)]
