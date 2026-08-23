"""Counting labeled records over time. detempus is real here, not stubbed: it is
deterministic and offline, so faking it would only hide whether the two agree
about the shape of the data."""
from __future__ import annotations

import datetime as dt
import json

from conftest import run_cli

# A day-to-day wobble, so the baseline has something to be robust about. A
# perfectly flat series makes the residual MAD collapse to floating-point noise
# and the scores come back astronomically large, which is true but useless: no
# threshold can be chosen against it.
WOBBLE = [3, 5, 4, 6, 4, 3, 5, 6, 4, 5, 3, 6, 5, 4, 6, 3, 5, 4, 6, 5,
          4, 6, 3, 5, 4, 6, 5, 3, 4, 6]


def write_labeled(tmp_path, spike_day=20, days=30):
    """Two categories over `days` days, with a spike in one of them on one day,
    so the expected candidate is known rather than discovered."""
    rows = []
    d0 = dt.date(2026, 7, 1)
    for i in range(days):
        day = (d0 + dt.timedelta(days=i)).isoformat()
        for k in range(40 if i == spike_day else WOBBLE[i % len(WOBBLE)]):
            rows.append({"t": f"{day}T0{k % 9}:00:00", "seg": f"w{i}-{k}",
                         "category": "気象", "is_disaster": True})
        for k in range(WOBBLE[(i + 7) % len(WOBBLE)]):
            rows.append({"t": f"{day}T{10 + k % 9}:00:00", "seg": f"n{i}-{k}",
                         "category": "ニュース", "is_disaster": True})
        rows.append({"t": f"{day}T15:00:00", "seg": f"m{i}",
                     "category": "音楽", "is_disaster": False})
    p = tmp_path / "labeled.jsonl"
    body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    p.write_text(body, encoding="utf-8")
    return p, (d0 + dt.timedelta(days=spike_day)).isoformat()


def load(tmp_path, name="s"):
    return json.loads((tmp_path / name / "series.json").read_text(encoding="utf-8"))


def test_one_series_per_key(tmp_path, env):
    src, _ = write_labeled(tmp_path)
    r = run_cli("series", [str(src), "--out", str(tmp_path / "s")], env)
    assert r.returncode == 0, r.stderr
    doc = load(tmp_path)
    assert {s["key"] for s in doc["series"]} == {"気象", "ニュース"}


def test_records_the_select_rejects_are_excluded(tmp_path, env):
    src, _ = write_labeled(tmp_path)
    run_cli("series", [str(src), "--out", str(tmp_path / "s")], env)
    assert all(s["key"] != "音楽" for s in load(tmp_path)["series"])


def test_finds_the_planted_spike(tmp_path, env):
    src, spike = write_labeled(tmp_path)
    run_cli("series", [str(src), "--out", str(tmp_path / "s")], env)
    weather = next(s for s in load(tmp_path)["series"] if s["key"] == "気象")
    assert [a["t"] for a in weather["anomalies"]] == [spike]
    assert weather["anomalies"][0]["value"] == 40


def test_the_flat_series_has_no_candidates(tmp_path, env):
    src, _ = write_labeled(tmp_path)
    run_cli("series", [str(src), "--out", str(tmp_path / "s")], env)
    news = next(s for s in load(tmp_path)["series"] if s["key"] == "ニュース")
    assert news["anomalies"] == []


def test_a_score_exists_for_every_bucket(tmp_path, env):
    """Candidates are the list cut at a threshold; the score behind it is kept
    for every point so the cutoff stays the caller's to change."""
    src, _ = write_labeled(tmp_path)
    run_cli("series", [str(src), "--out", str(tmp_path / "s")], env)
    weather = next(s for s in load(tmp_path)["series"] if s["key"] == "気象")
    assert len(weather["score"]) == 30 == len(weather["t"])


def test_detempus_method_block_is_kept_verbatim(tmp_path, env):
    src, _ = write_labeled(tmp_path)
    run_cli("series", [str(src), "--out", str(tmp_path / "s")], env)
    method = load(tmp_path)["series"][0]["method"]
    assert method["baseline"] == "stl"
    assert method["threshold"] == 3.5


def test_how_this_run_was_set_up_is_recorded(tmp_path, env):
    src, _ = write_labeled(tmp_path)
    run_cli("series", [str(src), "--out", str(tmp_path / "s")], env)
    doc = load(tmp_path)
    assert doc["bucket"] == "day"
    assert doc["key_field"] == "category"
    assert doc["select"] == ".is_disaster"
    assert doc["generated"].endswith("Z")


def test_threshold_reaches_detempus_and_changes_the_cut(tmp_path, env):
    src, _ = write_labeled(tmp_path)
    low = run_cli("series", [str(src), "--out", str(tmp_path / "lo")], env)
    high = run_cli("series", [str(src), "--out", str(tmp_path / "hi"),
                              "--threshold", "1000"], env)
    assert low.returncode == 0, low.stderr
    assert high.returncode == 0, high.stderr
    hi = load(tmp_path, "hi")
    assert hi["series"][0]["method"]["threshold"] == 1000
    assert sum(len(s["anomalies"]) for s in hi["series"]) == 0
    assert sum(len(s["anomalies"]) for s in load(tmp_path, "lo")["series"]) > 0


def test_an_empty_key_field_gives_one_combined_series(tmp_path, env):
    src, _ = write_labeled(tmp_path)
    r = run_cli("series", [str(src), "--out", str(tmp_path / "s"), "--key-field", ""], env)
    assert r.returncode == 0, r.stderr
    doc = load(tmp_path)
    assert len(doc["series"]) == 1
    assert doc["series"][0]["key"] == "all"
    assert doc["key_field"] is None


def test_hourly_bucketing(tmp_path, env):
    src, _ = write_labeled(tmp_path)
    r = run_cli("series", [str(src), "--out", str(tmp_path / "s"), "--bucket", "hour"], env)
    assert r.returncode == 0, r.stderr
    doc = load(tmp_path)
    assert doc["bucket"] == "hour"
    assert doc["series"][0]["method"]["period"] == 24


def test_an_unknown_bucket_is_refused(tmp_path, env):
    src, _ = write_labeled(tmp_path)
    r = run_cli("series",
                [str(src), "--out", str(tmp_path / "s"), "--bucket", "fortnight"], env)
    assert r.returncode == 1
    assert "must be one of" in r.stderr
    assert "Traceback" not in r.stderr


def test_a_select_that_matches_nothing_says_so(tmp_path, env):
    src, _ = write_labeled(tmp_path)
    r = run_cli("series", [str(src), "--out", str(tmp_path / "s"), "--select", ".nope"], env)
    assert r.returncode == 1
    assert "matched no records" in r.stderr
    assert "Traceback" not in r.stderr


def test_the_intermediate_counts_file_is_not_left_behind(tmp_path, env):
    src, _ = write_labeled(tmp_path)
    run_cli("series", [str(src), "--out", str(tmp_path / "s")], env)
    assert not (tmp_path / "s" / "counts.jsonl").exists()
