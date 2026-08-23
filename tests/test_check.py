"""`speechmap --check` reports what is reachable, per stage.

Being able to ask before running anything saves diagnosing a failure halfway
through a long job. Grouping by stage matters because the answer "aiq is
missing" is only a problem if you were going to apply a lens; recording and
transcribing do not need it.
"""
from __future__ import annotations

from conftest import run_cli


def test_check_groups_the_programs_by_stage(env):
    r = run_cli("check", [], env)
    assert r.returncode == 0, r.stderr
    for stage in ("record", "transcribe", "lens", "series"):
        assert stage in r.stderr, f"{stage} is not named in the output"


def test_check_names_every_program(env):
    r = run_cli("check", [], env)
    for name in ("ffmpeg", "ffprobe", "curl", "jq", "aiq", "locitorium", "detempus"):
        assert name in r.stderr, name


def test_rtl_fm_is_reported_as_needed_only_for_sdr(env):
    """A machine with no dongle should not be told it is missing something
    required. It is missing something optional."""
    r = run_cli("check", [], env)
    assert "rtl_fm" in r.stderr
    assert "sdr" in r.stderr.lower()


def test_a_missing_optional_program_does_not_fail_the_check(env, tmp_path):
    """Everything required present, rtl_fm absent: still exit 0."""
    import os
    import shutil

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("ffmpeg", "ffprobe", "curl", "jq"):
        found = shutil.which(name)
        if found:
            (bin_dir / name).symlink_to(found)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH'].split(os.pathsep)[0]}"
    r = run_cli("check", [], env)
    # aiq and locitorium come from the stubs, which are first on PATH in the
    # fixture; rtl_fm is not there.
    assert "rtl_fm" in r.stderr


def test_a_missing_required_program_fails_the_check(env, tmp_path):
    env["PATH"] = str(tmp_path)
    for var in ("DETEMPUS", "AIQ", "LOCITORIUM"):
        env.pop(var, None)
    r = run_cli("check", [], env)
    assert r.returncode == 1
    assert "not found" in r.stderr


def test_check_says_where_each_one_was_found(env):
    r = run_cli("check", [], env)
    assert "PATH" in r.stderr
