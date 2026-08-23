"""Finding the programs this drives, and running them.

Each one is looked for on PATH first, then in a source checkout named by an
environment variable. The checkout fallback exists because during development
the interesting version of a component is the working tree, not the release.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class ToolError(Exception):
    """A program that is needed and not reachable, or that failed."""


@dataclass(frozen=True)
class Tool:
    """One external program, resolved to a command line."""

    name: str
    argv: list[str]
    source: str  # "PATH" or the checkout path it was found in

    def run(
        self,
        args: list[str],
        *,
        stdin: bytes | None = None,
        stdout_path: Path | None = None,
    ) -> bytes:
        """Run it. Its stderr is left alone so progress and warnings reach the
        terminal; only stdout is captured or redirected."""
        argv = [*self.argv, *args]
        try:
            if stdout_path is not None:
                with stdout_path.open("wb") as out:
                    subprocess.run(argv, input=stdin, stdout=out, check=True)
                return b""
            done = subprocess.run(argv, input=stdin, stdout=subprocess.PIPE, check=True)
            return done.stdout
        except FileNotFoundError as e:
            raise ToolError(f"{self.name}: {e}") from e
        except subprocess.CalledProcessError as e:
            raise ToolError(
                f"{self.name} exited {e.returncode}. Its own message is above."
            ) from e


# name -> (env var naming a checkout, how to run it from that checkout, install hint)
_KNOWN: dict[str, tuple[str, list[str], str]] = {
    "aiq": (
        "AIQ",
        ["uv", "run", "--frozen", "python", "-m", "aiq.aiq"],
        "a fork of aiq with `extract`: https://github.com/yuiseki/aiq",
    ),
    "locitorium": (
        "LOCITORIUM",
        ["uv", "run", "--frozen", "locitorium"],
        "https://github.com/yuiseki/locitorium",
    ),
    "detempus": (
        "DETEMPUS",
        ["uv", "run", "--no-project", "detempus"],
        "not on PyPI yet: "
        "uv pip install 'detempus[all] @ git+https://github.com/yuiseki/detempus'",
    ),
    "jq": ("", [], "your package manager"),
    "ffmpeg": ("", [], "your package manager"),
    "ffprobe": ("", [], "your package manager (it ships with ffmpeg)"),
    "curl": ("", [], "your package manager"),
    "rtl_fm": ("", [], "librtlsdr (Debian and Ubuntu call it rtl-sdr)"),
}


def find(name: str) -> Tool:
    """Resolve one program, or explain how to get it."""
    if shutil.which(name):
        return Tool(name=name, argv=[name], source="PATH")

    env_var, from_checkout, hint = _KNOWN.get(name, ("", [], "your package manager"))
    if env_var:
        checkout = os.environ.get(env_var)
        if checkout and Path(checkout).is_dir():
            # `env --chdir` rather than cwd= so the command is visible in ps
            # and reproducible by hand. VIRTUAL_ENV has to go: if this process
            # is itself running inside a virtualenv, uv would honour that one
            # and look for the component in the wrong place.
            return Tool(
                name=name,
                argv=["env", "--chdir", checkout, "-u", "VIRTUAL_ENV", *from_checkout],
                source=checkout,
            )
        raise ToolError(
            f"{name} not found. Install it ({hint}), or set {env_var} to a checkout."
        )
    raise ToolError(f"{name} not found. Install it from {hint}.")


def check(names: list[str]) -> list[tuple[str, str | None, str | None]]:
    """Resolve several, reporting rather than raising. Returns one row per
    program: (name, where it was found, why it was not)."""
    rows = []
    for name in names:
        try:
            tool = find(name)
        except ToolError as e:
            rows.append((name, None, str(e)))
        else:
            rows.append((name, tool.source, None))
    return rows
