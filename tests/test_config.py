"""`speechmap.yaml`: declaring a pipeline instead of typing it.

The stage commands stay. This is a layer above them that says what to run,
which is the difference between handing someone three commands and handing them
a thing they can start.

Reading a declaration is the easy part. What matters is that a bad declaration
is reported before anything runs, because the alternative is a job that fails
twenty minutes in.
"""
from __future__ import annotations

import pathlib

import pytest

from openspeechmap import config


@pytest.fixture(autouse=True)
def a_lens_next_to_the_declaration(tmp_path, lenses):
    """Paths in the file are resolved against the file, so the tests need a lens
    at the path they name, relative to tmp_path."""
    import shutil

    shutil.copytree(lenses, tmp_path / "lenses", dirs_exist_ok=True)
    return tmp_path / "lenses"


def write(tmp_path, text):
    p = tmp_path / "speechmap.yaml"
    p.write_text(text, encoding="utf-8")
    return p


MINIMAL = """
source:
  kind: http
  url: http://example.invalid/stream
  label: TEST
out: ./out
lens: lenses/ja-radio-disaster
"""


def test_a_minimal_declaration_loads(tmp_path, lenses):
    cfg = config.load(write(tmp_path, MINIMAL))
    assert cfg.source.kind == "http"
    assert cfg.source.label == "TEST"
    assert cfg.lens.name == "ja-radio-disaster"


def test_paths_are_resolved_against_the_file_not_the_cwd(tmp_path, monkeypatch):
    """A declaration you can hand to someone else has to mean the same thing
    wherever it is run from."""
    (tmp_path / "recordings").mkdir()
    p = write(tmp_path, """
source:
  kind: dir
  path: ./recordings
out: ./out
lens: ./lenses/ja-radio-disaster
""")
    monkeypatch.chdir("/")
    cfg = config.load(p)
    assert cfg.out == tmp_path / "out"
    assert cfg.source.path == tmp_path / "recordings"


def test_the_defaults_match_the_command_line_defaults(tmp_path):
    cfg = config.load(write(tmp_path, MINIMAL))
    assert cfg.transcribe.chunk_sec == 60
    assert cfg.lens_stage.select == ".is_disaster"
    assert cfg.series.bucket == "day"


def test_an_unknown_key_is_refused_rather_than_ignored(tmp_path):
    """Silently ignoring a misspelled key means the setting the person thought
    they had set is not set."""
    with pytest.raises(config.ConfigError, match="chunk_secs"):
        config.load(write(tmp_path, MINIMAL + "\ntranscribe:\n  chunk_secs: 30\n"))


def test_a_missing_required_key_says_which(tmp_path):
    with pytest.raises(config.ConfigError, match="out"):
        config.load(write(tmp_path, "source:\n  kind: dir\n  path: .\n"))


def test_a_lens_that_does_not_exist_is_caught_before_anything_runs(tmp_path):
    with pytest.raises(config.ConfigError, match="lens"):
        config.load(write(tmp_path, MINIMAL.replace(
            "lenses/ja-radio-disaster", "lenses/nope")))


def test_an_http_source_without_a_url_is_caught(tmp_path):
    with pytest.raises(config.ConfigError, match="url"):
        config.load(write(tmp_path, """
source:
  kind: http
  label: X
out: ./out
lens: lenses/ja-radio-disaster
"""))


def test_an_sdr_source_needs_a_frequency(tmp_path):
    with pytest.raises(config.ConfigError, match="freq"):
        config.load(write(tmp_path, """
source:
  kind: sdr
  label: X
out: ./out
lens: lenses/ja-radio-disaster
"""))


def test_an_unknown_source_kind_lists_the_ones_that_exist(tmp_path):
    with pytest.raises(config.ConfigError, match="http"):
        config.load(write(tmp_path, MINIMAL.replace("kind: http", "kind: telepathy")))


def test_a_directory_source_skips_the_capture_stage(tmp_path):
    (tmp_path / "rec").mkdir()
    cfg = config.load(write(tmp_path, """
source:
  kind: dir
  path: ./rec
out: ./out
lens: lenses/ja-radio-disaster
"""))
    assert cfg.stages() == ["transcribe", "lens", "series"]


def test_a_transcripts_source_skips_capture_and_transcription(tmp_path):
    (tmp_path / "t.jsonl").write_text("")
    cfg = config.load(write(tmp_path, """
source:
  kind: transcripts
  path: ./t.jsonl
out: ./out
lens: lenses/ja-radio-disaster
"""))
    assert cfg.stages() == ["lens", "series"]


def test_a_stream_source_runs_everything(tmp_path):
    cfg = config.load(write(tmp_path, MINIMAL))
    assert cfg.stages() == ["record", "transcribe", "lens", "series"]


def test_yaml_that_is_not_a_mapping_says_so(tmp_path):
    with pytest.raises(config.ConfigError, match="mapping"):
        config.load(write(tmp_path, "- one\n- two\n"))


def test_broken_yaml_names_the_file(tmp_path):
    p = write(tmp_path, "source: [unclosed\n")
    with pytest.raises(config.ConfigError, match="speechmap.yaml"):
        config.load(p)


def test_the_example_that_ships_actually_loads(tmp_path, lenses):
    """A broken example is the same kind of lie as a README whose commands do
    not run. Every key in it must be one the loader knows."""
    import shutil

    root = pathlib.Path(__file__).resolve().parents[1]
    shutil.copy(root / "speechmap.example.yaml", tmp_path / "speechmap.yaml")
    shutil.copytree(root / "lenses", tmp_path / "lenses", dirs_exist_ok=True)
    cfg = config.load(tmp_path / "speechmap.yaml")
    assert cfg.source.kind == "http"
    assert cfg.stages() == ["record", "transcribe", "lens", "series"]
    assert cfg.out == tmp_path / "out"


def test_the_examples_commented_out_alternatives_are_known_keys(tmp_path, lenses):
    """The commented lines are instructions. If one names a key the loader
    rejects, following the comment produces an error."""
    import re

    root = pathlib.Path(__file__).resolve().parents[1]
    text = (root / "speechmap.example.yaml").read_text(encoding="utf-8")
    commented = re.findall(r"^\s*#\s*([a-z_]+):", text, re.M)
    known = (
        {f.name for f in config.Source.__dataclass_fields__.values()}
        | {f.name for f in config.Transcribe.__dataclass_fields__.values()}
        | {f.name for f in config.LensStage.__dataclass_fields__.values()}
        | {f.name for f in config.Series.__dataclass_fields__.values()}
        | {"source", "out", "lens", "transcribe", "lens_stage", "series"}
    )
    unknown = sorted(set(commented) - known)
    assert not unknown, f"the example suggests keys nobody reads: {unknown}"
