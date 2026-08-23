"""Loading a lens. Failing here, with a message, beats failing deep inside
another program with its own idea of what went wrong."""
from __future__ import annotations

import json

import pytest

from openspeechmap import lens as lens_module


def test_loads_a_lens_that_ships_with_the_repository(lenses):
    lens = lens_module.load(lenses / "ja-radio-disaster")
    assert lens.name == "ja-radio-disaster"
    assert lens.fields == ["category", "topic", "is_disaster"]
    assert lens.system is not None
    assert lens.gate is None


def test_paths_are_absolute(lenses, tmp_path, monkeypatch):
    """The programs this drives may run with a different working directory, so a
    relative lens path would vanish under them."""
    monkeypatch.chdir(tmp_path)
    lens = lens_module.load(lenses / "ja-radio-disaster")
    assert lens.schema.is_absolute()
    assert lens.instruction.is_absolute()


def test_a_lens_can_declare_a_gate(lenses):
    lens = lens_module.load(lenses / "ja-radio-event")
    assert lens.gate is not None
    assert len(lens.gate_keywords()) > 10
    assert lens.passes_gate("長岡市の花火大会の交通規制です")
    assert not lens.passes_gate("次の曲をお送りします")


def test_a_lens_without_a_gate_passes_everything(lenses):
    lens = lens_module.load(lenses / "ja-radio-disaster")
    assert lens.gate_keywords() == []
    assert lens.passes_gate("anything at all")
    assert lens.passes_gate("")


def test_missing_directory_says_so(tmp_path):
    with pytest.raises(lens_module.LensError, match="lens directory not found"):
        lens_module.load(tmp_path / "nope")


def test_missing_schema_says_which_file(tmp_path):
    (tmp_path / "instruction.txt").write_text("hi")
    with pytest.raises(lens_module.LensError, match="missing schema.json"):
        lens_module.load(tmp_path)


def test_missing_instruction_says_which_file(tmp_path):
    (tmp_path / "schema.json").write_text('{"type":"object","properties":{"a":{}}}')
    with pytest.raises(lens_module.LensError, match="missing instruction.txt"):
        lens_module.load(tmp_path)


def test_schema_that_is_not_json_says_so(tmp_path):
    (tmp_path / "schema.json").write_text("{oops")
    (tmp_path / "instruction.txt").write_text("hi")
    with pytest.raises(lens_module.LensError, match="not valid JSON"):
        lens_module.load(tmp_path)


def test_schema_that_is_not_an_object_schema_says_so(tmp_path):
    (tmp_path / "schema.json").write_text(json.dumps({"type": "array"}))
    (tmp_path / "instruction.txt").write_text("hi")
    with pytest.raises(lens_module.LensError, match="JSON Schema object"):
        lens_module.load(tmp_path)


def test_schema_with_no_properties_says_nothing_would_be_extracted(tmp_path):
    (tmp_path / "schema.json").write_text(json.dumps({"type": "object", "properties": {}}))
    (tmp_path / "instruction.txt").write_text("hi")
    with pytest.raises(lens_module.LensError, match="nothing would be extracted"):
        lens_module.load(tmp_path)
