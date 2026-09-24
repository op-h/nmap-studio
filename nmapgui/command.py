"""Turn a ScanConfig into an nmap argument vector (and back again)."""
from __future__ import annotations

import os
import shlex
from dataclasses import dataclass, field

from .optionsdata import CHOICE, EMIT_ORDER, EXCLUSIVE, FLAG, OPT_BY_KEY, OPTIONS
from .platform_support import (find_nmap, is_elevated, nmap_exists, privileged_argv)

NMAP = find_nmap()


@dataclass
class ScanConfig:
    """Everything the user picked, in a form that survives save/load."""
    targets: str = ""
    opts: dict = field(default_factory=dict)      # key -> bool | str
    scripts: list = field(default_factory=list)   # script or category names
    script_args: str = ""
    run_default_scripts: bool = False             # -sC
    custom_command: str = ""                      # set when the user edits by hand

    # ---------------------------------------------------------------- helpers
    def clone(self) -> "ScanConfig":
        return ScanConfig(
            targets=self.targets,
            opts=dict(self.opts),
            scripts=list(self.scripts),
            script_args=self.script_args,
            run_default_scripts=self.run_default_scripts,
            custom_command=self.custom_command,
        )

    def to_dict(self) -> dict:
        return {
            "targets": self.targets, "opts": self.opts, "scripts": self.scripts,
            "script_args": self.script_args, "run_default_scripts": self.run_default_scripts,
            "custom_command": self.custom_command,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ScanConfig":
        return cls(
            targets=d.get("targets", ""),
            opts=dict(d.get("opts", {})),
            scripts=list(d.get("scripts", [])),
            script_args=d.get("script_args", ""),
            run_default_scripts=bool(d.get("run_default_scripts", False)),
            custom_command=d.get("custom_command", ""),
        )

    # ---------------------------------------------------------------- flags
    def option_args(self) -> list[str]:
        """Every selected option, in catalogue order."""
        args: list[str] = []
        for key in EMIT_ORDER:
            if key not in self.opts:
                continue
            val = self.opts[key]
            opt = OPT_BY_KEY[key]
            if val in (None, False, ""):
                # A value-taking flag such as -PS is still meaningful with an
                # empty value, but only if the user explicitly switched it on.
                if val == "" and self.opts.get(f"{key}__on"):
                    args.append(opt.flag)
                continue
            if opt.kind in (FLAG, EXCLUSIVE) or val is True:
                args.append(opt.flag)
            elif opt.joiner == "RAW":
                args.append(str(val))
            elif opt.joiner == "":
                args.append(f"{opt.flag}{val}")
            elif opt.joiner == "=":
                args.append(f"{opt.flag}={val}")
            else:
                args.extend([opt.flag, str(val)])

        if self.run_default_scripts:
            args.append("-sC")
        if self.scripts:
            args.append("--script=" + ",".join(self.scripts))
        if self.script_args.strip():
            args.append("--script-args=" + self.script_args.strip())
        return args

    def target_args(self) -> list[str]:
        return shlex.split(self.targets.strip()) if self.targets.strip() else []

    # ---------------------------------------------------------------- command
    def preview(self) -> str:
        """The command as the user should see it (no internal -oX plumbing)."""
        if self.custom_command.strip():
            return self.custom_command.strip()
        parts = ["nmap"] + self.option_args() + self.target_args()
        return " ".join(shlex.quote(p) if _needs_quote(p) else p for p in parts)

    def argv(self, xml_path: str | None = None) -> list[str]:
        """The real argv handed to QProcess."""
        if self.custom_command.strip():
            toks = shlex.split(self.custom_command.strip())
            if toks and os.path.basename(toks[0]).lower() in ("nmap", "nmap.exe"):
                toks = toks[1:]
            argv = [NMAP] + toks
        else:
            argv = [NMAP] + self.option_args() + self.target_args()

        argv += ["--stats-every", "1s"]
        if xml_path and "-oX" not in argv and "-oA" not in argv:
            argv += ["-oX", xml_path]
        return argv

    # ---------------------------------------------------------------- checks
    def needs_root(self) -> list[str]:
        """Names of selected options that need raw-socket privileges."""
        if self.custom_command.strip():
            toks = set(self.custom_command.split())
            return sorted({o.flag for o in OPTIONS if o.root and o.flag in toks})
        out = []
        for key, val in self.opts.items():
            if val in (None, False, ""):
                continue
            opt = OPT_BY_KEY.get(key)
            if opt and opt.root:
                out.append(opt.flag)
        return sorted(set(out))

    def validate(self) -> list[str]:
        """Human-readable problems, empty list when the scan is runnable."""
        problems = []
        if self.custom_command.strip():
            try:
                toks = shlex.split(self.custom_command)
            except ValueError as exc:
                return [f"Command cannot be parsed: {exc}"]
            if not toks:
                problems.append("The command is empty.")
            return problems

        if not self.targets.strip() and not self.opts.get("iL") and not self.opts.get("iR"):
            problems.append("No target given. Enter a host, range or CIDR — "
                            "or load a target list with -iL.")
        for key in ("iL", "excludefile", "datadir", "resume"):
            path = self.opts.get(key)
            if path and not os.path.exists(str(path)):
                problems.append(f"{OPT_BY_KEY[key].flag}: '{path}' does not exist.")
        ti = self.opts.get("version_intensity")
        if ti not in (None, "", False):
            try:
                if not 0 <= int(ti) <= 9:
                    problems.append("--version-intensity must be between 0 and 9.")
            except ValueError:
                problems.append("--version-intensity must be a number.")
        mtu = self.opts.get("mtu")
        if mtu and str(mtu).isdigit() and int(mtu) % 8:
            problems.append("--mtu must be a multiple of 8.")
        return problems


def _needs_quote(token: str) -> bool:
    return any(c in token for c in " \t'\"\\$`;|&<>()")


def is_root() -> bool:
    """Raw sockets available: root on POSIX, Administrator on Windows."""
    return is_elevated()


def elevated_argv(argv: list[str], helper: str = "pkexec") -> list[str]:
    """Wrap argv so it runs with privileges, preserving the nmap arguments."""
    return privileged_argv(argv, helper)


def nmap_available() -> bool:
    return nmap_exists(NMAP)


def parse_command(text: str) -> tuple[ScanConfig | None, str]:
    """Best-effort reverse mapping of a typed command onto the option catalogue.

    Returns (config, note). config is None when something in the command has no
    catalogue entry, in which case the caller should keep it as a custom command.
    """
    try:
        toks = shlex.split(text.strip())
    except ValueError as exc:
        return None, f"unparsable: {exc}"
    if toks and os.path.basename(toks[0]).lower().startswith("nmap"):
        toks = toks[1:]

    cfg = ScanConfig()
    targets: list[str] = []
    by_flag = {o.flag: o for o in OPTIONS}
    i = 0
    while i < len(toks):
        tok = toks[i]
        if not tok.startswith("-"):
            targets.append(tok)
            i += 1
            continue

        if tok.startswith("--script-args="):
            cfg.script_args = tok.split("=", 1)[1]
            i += 1
            continue
        if tok.startswith("--script="):
            cfg.scripts = [s for s in tok.split("=", 1)[1].split(",") if s]
            i += 1
            continue
        if tok == "--script" and i + 1 < len(toks):
            cfg.scripts = [s for s in toks[i + 1].split(",") if s]
            i += 2
            continue
        if tok == "-sC":
            cfg.run_default_scripts = True
            i += 1
            continue
        if tok in ("-v", "-vv", "-vvv"):
            cfg.opts["v"] = tok
            i += 1
            continue
        if tok in ("-d", "-dd", "-ddd"):
            cfg.opts["d"] = tok
            i += 1
            continue
        if tok.startswith("-T") and len(tok) == 3 and tok[2].isdigit():
            cfg.opts["T"] = tok[2]
            i += 1
            continue

        key_eq = tok.split("=", 1)
        opt = by_flag.get(key_eq[0])
        if opt is None:
            # things like -PS22,80 where the value is glued on
            match = None
            for flag, o in by_flag.items():
                if o.joiner == "" and flag != "-T" and tok.startswith(flag) and len(tok) > len(flag):
                    if match is None or len(flag) > len(match.flag):
                        match = o
            if match is not None:
                cfg.opts[match.key] = tok[len(match.flag):]
                i += 1
                continue
            return None, f"unknown option {tok}"

        if len(key_eq) == 2:
            cfg.opts[opt.key] = key_eq[1]
            i += 1
        elif opt.kind in (FLAG, EXCLUSIVE):
            cfg.opts[opt.key] = True
            i += 1
        elif opt.kind == CHOICE and opt.joiner == "":
            cfg.opts[opt.key] = ""
            i += 1
        elif opt.joiner == "" and opt.kind != FLAG:
            cfg.opts[opt.key] = ""
            cfg.opts[f"{opt.key}__on"] = True
            i += 1
        elif i + 1 < len(toks) and not toks[i + 1].startswith("-"):
            cfg.opts[opt.key] = toks[i + 1]
            i += 2
        else:
            cfg.opts[opt.key] = True
            i += 1

    cfg.targets = " ".join(targets)
    return cfg, ""
