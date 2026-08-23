"""Test setup.

The stubs in `tests/stubs/` stand in for `aiq` and `locitorium`, so tests need
no network and no language model: the same prompt does not give the same answer
twice, and a test whose expected value moves is not a test.

detempus is real. It is deterministic and runs offline, so there is nothing to
gain by faking it and something to lose.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUBS = ROOT / "tests" / "stubs"
FIXTURES = ROOT / "tests" / "fixtures"


@pytest.fixture
def env() -> dict[str, str]:
    """An environment where the stubs are found before anything installed, and
    detempus resolves to a checkout if it is not installed."""
    e = dict(os.environ)
    e["PATH"] = f"{STUBS}{os.pathsep}{e.get('PATH', '')}"
    e.pop("OPENSPEECHMAP_TRACEBACK", None)
    e.setdefault("DETEMPUS", str(Path.home() / "Workspaces/repos/__yuiseki/_poc/detempus"))
    return e


@pytest.fixture
def lenses() -> Path:
    return ROOT / "lenses"


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


def run_cli(command: str, args: list[str], env: dict[str, str], stdin: str = ""):
    """Run a subcommand the way a caller would.

    `command` is the subcommand name; pass "" for the bare invocation that runs
    everything.
    """
    argv = [sys.executable, "-m", "openspeechmap.cli_main"]
    if command:
        argv.append(command)
    return subprocess.run(
        [*argv, *args],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=180,
        cwd=ROOT,
        env=env,
    )


def records(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def features(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["features"]


@pytest.fixture(scope="session")
def npr_segments(tmp_path_factory) -> Path:
    """Two short recordings with real speech in them, named a.ts and b.ts.

    Cut from the sample audio committed for this purpose rather than fetched:
    a test that needs the network is a test that fails on a train.
    """
    src = FIXTURES / "audio"
    if not src.is_dir():
        pytest.skip(f"{src} is missing; see tests/fixtures/README.md")
    return src
