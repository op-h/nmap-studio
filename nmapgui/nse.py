"""NSE script catalogue.

Categories come from script.db (one cheap read); descriptions, usage and
arguments are lifted from the .nse source on demand and cached.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from functools import lru_cache

from .platform_support import script_dirs

_ENTRY = re.compile(r'Entry\s*{\s*filename\s*=\s*"([^"]+)"\s*,\s*categories\s*=\s*{([^}]*)}')
_CATS_IN_SRC = re.compile(r'categories\s*=\s*{([^}]*)}', re.S)
_DESC = re.compile(r'description\s*=\s*\[\[(.*?)\]\]', re.S)
_DESC2 = re.compile(r'description\s*=\s*"((?:[^"\\]|\\.)*)"', re.S)
_AUTHOR = re.compile(r'author\s*=\s*(?:\[\[(.*?)\]\]|"([^"]*)")', re.S)
_LICENSE = re.compile(r'license\s*=\s*(?:\[\[(.*?)\]\]|"([^"]*)")', re.S)
_USAGE = re.compile(r'@usage\s+(.*?)(?:\n\s*--\s*@|\n\s*--\s*\]\]|\Z)', re.S)
_ARG = re.compile(r'@args\s+(\S+)\s+(.*?)(?=\n\s*--\s*@|\Z)', re.S)


@dataclass
class Script:
    name: str
    categories: tuple = ()
    path: str = ""
    _detail: dict = field(default_factory=dict, repr=False)

    # ------------------------------------------------ lazily loaded detail
    def _load(self) -> dict:
        if self._detail:
            return self._detail
        self._detail = _read_source(self.path)
        return self._detail

    @property
    def description(self) -> str:
        return self._load().get("description", "")

    @property
    def author(self) -> str:
        return self._load().get("author", "")

    @property
    def license(self) -> str:
        return self._load().get("license", "")

    @property
    def usage(self) -> str:
        return self._load().get("usage", "")

    @property
    def args(self) -> list:
        return self._load().get("args", [])

    @property
    def summary(self) -> str:
        desc = self.description.strip()
        if not desc:
            return ""
        first = re.split(r"(?<=[.!?])\s", desc.replace("\n", " "))[0]
        return first.strip()[:240]


def _clean(text: str) -> str:
    text = re.sub(r"^\s*--\s?", "", text, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _reflow(text: str) -> str:
    """Undo the hard wrapping in .nse sources.

    Script descriptions are wrapped at about 75 columns in the Lua source, which
    reads as ragged nonsense in a resizable panel. Single newlines become spaces;
    blank lines stay as paragraph breaks, as do list items.
    """
    paragraphs = re.split(r"\n\s*\n", _clean(text))
    out = []
    for para in paragraphs:
        lines = [ln.strip() for ln in para.splitlines() if ln.strip()]
        if any(re.match(r"^([*+-]|\d+[.)])\s", ln) for ln in lines):
            out.append("\n".join(lines))        # keep lists as they are
        else:
            out.append(" ".join(lines))
    return "\n\n".join(out).strip()


@lru_cache(maxsize=4096)
def _read_source(path: str) -> dict:
    out: dict = {"description": "", "author": "", "license": "", "usage": "", "args": []}
    if not path or not os.path.isfile(path):
        return out
    try:
        with open(path, "r", errors="replace") as fh:
            src = fh.read(120_000)
    except OSError:
        return out

    m = _DESC.search(src) or _DESC2.search(src)
    if m:
        out["description"] = _reflow(m.group(1))
    m = _AUTHOR.search(src)
    if m:
        out["author"] = _clean(m.group(1) or m.group(2) or "")
    m = _LICENSE.search(src)
    if m:
        out["license"] = _clean(m.group(1) or m.group(2) or "")
    m = _USAGE.search(src)
    if m:
        out["usage"] = _clean(m.group(1))[:600]
    out["args"] = [(a, _clean(d)[:300]) for a, d in _ARG.findall(src)][:12]
    return out


def scripts_dir() -> str:
    """The first NSE directory that actually exists on this machine."""
    for directory in script_dirs():
        if os.path.isdir(directory):
            return directory
    return ""


def load_catalogue() -> list[Script]:
    """Every installed NSE script with its categories, sorted by name."""
    directory = scripts_dir()
    if not directory:
        return []

    found: dict[str, Script] = {}
    db = os.path.join(directory, "script.db")
    if os.path.isfile(db):
        try:
            with open(db, "r", errors="replace") as fh:
                for fname, cats in _ENTRY.findall(fh.read()):
                    name = fname[:-4] if fname.endswith(".nse") else fname
                    cat = tuple(sorted(c.strip().strip('"') for c in cats.split(",") if c.strip()))
                    found[name] = Script(name, cat, os.path.join(directory, fname))
        except OSError:
            pass

    # Anything dropped in by hand that script.db does not know about yet.
    try:
        for fname in os.listdir(directory):
            if not fname.endswith(".nse"):
                continue
            name = fname[:-4]
            if name in found:
                continue
            path = os.path.join(directory, fname)
            cats: tuple = ()
            try:
                with open(path, "r", errors="replace") as fh:
                    m = _CATS_IN_SRC.search(fh.read(60_000))
                if m:
                    cats = tuple(sorted(
                        c.strip().strip('"') for c in m.group(1).split(",") if c.strip()))
            except OSError:
                pass
            found[name] = Script(name, cats, path)
    except OSError:
        pass

    return sorted(found.values(), key=lambda s: s.name)


def all_categories(catalogue: list[Script]) -> list[str]:
    cats = {c for s in catalogue for c in s.categories}
    return sorted(cats)
