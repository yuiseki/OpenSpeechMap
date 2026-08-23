"""How the command line behaves when something is wrong.

An expected failure prints one line and exits non-zero. A caller -- often an
agent -- needs to know what to fix, and a traceback does not say that."""
from __future__ import annotations

import json

from conftest import run_cli


def write_input(tmp_path):
    p = tmp_path / "in.jsonl"
    p.write_text(json.dumps({"t": "2026-08-13T19:00:00", "seg": "a",
                             "text": "柏市で雨"}, ensure_ascii=False) + "\n",
                 encoding="utf-8")
    return p


def test_missing_input_is_one_line(tmp_path, env, lenses):
    r = run_cli("lens", [str(tmp_path / "nope.jsonl"),
                        "--lens", str(lenses / "ja-radio-disaster"),
                        "--out", str(tmp_path / "o")], env)
    assert r.returncode == 1
    assert "input not found" in r.stderr
    assert "Traceback" not in r.stderr
    assert r.stdout == ""


def test_missing_lens_is_one_line(tmp_path, env):
    r = run_cli("lens", [str(write_input(tmp_path)), "--lens", str(tmp_path / "nope"),
                        "--out", str(tmp_path / "o")], env)
    assert r.returncode == 1
    assert "lens directory not found" in r.stderr
    assert "Traceback" not in r.stderr


def test_no_lens_given(tmp_path, env):
    r = run_cli("lens", [str(write_input(tmp_path)), "--out", str(tmp_path / "o")], env)
    assert r.returncode == 1
    assert "--lens is required" in r.stderr


def test_no_out_given(tmp_path, env, lenses):
    r = run_cli("lens", [str(write_input(tmp_path)),
                        "--lens", str(lenses / "ja-radio-disaster")], env)
    assert r.returncode == 1
    assert "--out is required" in r.stderr


def test_no_input_given(tmp_path, env, lenses):
    r = run_cli("lens", ["--lens", str(lenses / "ja-radio-disaster"),
                        "--out", str(tmp_path / "o")], env)
    assert r.returncode == 1
    assert "no input given" in r.stderr


def test_a_record_missing_the_text_field_says_which_field(tmp_path, env, lenses):
    p = tmp_path / "in.jsonl"
    p.write_text(json.dumps({"t": "x", "seg": "a"}) + "\n", encoding="utf-8")
    r = run_cli("lens", [str(p), "--lens", str(lenses / "ja-radio-disaster"),
                        "--out", str(tmp_path / "o")], env)
    assert r.returncode == 1
    assert "'text'" in r.stderr
    assert "Traceback" not in r.stderr


def test_malformed_json_names_the_line(tmp_path, env, lenses):
    p = tmp_path / "in.jsonl"
    p.write_text('{"seg":"a","text":"ok"}\nnot json\n', encoding="utf-8")
    r = run_cli("lens", [str(p), "--lens", str(lenses / "ja-radio-disaster"),
                        "--out", str(tmp_path / "o")], env)
    assert r.returncode == 1
    assert "line 2" in r.stderr
    assert "Traceback" not in r.stderr


def test_an_unknown_option_is_refused(tmp_path, env, lenses):
    r = run_cli("lens", [str(write_input(tmp_path)),
                        "--lens", str(lenses / "ja-radio-disaster"),
                        "--out", str(tmp_path / "o"), "--wat"], env)
    assert r.returncode != 0
    assert "wat" in (r.stderr + r.stdout)


def test_traceback_can_be_restored_for_debugging(tmp_path, env, lenses):
    env["OPENSPEECHMAP_TRACEBACK"] = "1"
    r = run_cli("lens", [str(tmp_path / "nope.jsonl"),
                        "--lens", str(lenses / "ja-radio-disaster"),
                        "--out", str(tmp_path / "o")], env)
    assert r.returncode != 0
    assert "Traceback" in r.stderr


def test_check_reports_where_each_program_was_found(tmp_path, env):
    r = run_cli("check", [], env)
    assert r.returncode == 0, r.stderr
    for name in ("jq", "aiq", "locitorium", "detempus"):
        assert name in r.stderr


def test_check_fails_when_something_is_missing(tmp_path, env):
    env["PATH"] = str(tmp_path)          # nothing on PATH
    env.pop("DETEMPUS", None)
    env.pop("AIQ", None)
    env.pop("LOCITORIUM", None)
    r = run_cli("check", [], env)
    assert r.returncode == 1
    assert "not found" in r.stderr


def test_stdout_stays_free_of_progress_chatter(tmp_path, env, lenses):
    r = run_cli("lens", [str(write_input(tmp_path)),
                        "--lens", str(lenses / "ja-radio-disaster"),
                        "--out", str(tmp_path / "o")], env)
    assert r.returncode == 0, r.stderr
    assert r.stdout == ""


def test_version_is_printed_on_stdout(tmp_path, env):
    r = run_cli("version", [], env)
    assert r.returncode == 0
    assert r.stdout.strip()
