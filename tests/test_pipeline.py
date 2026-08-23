"""The lens stage, the selection stage and the place stage, end to end through
the command line, with the stubs standing in for the two programs that would
otherwise need a network."""
from __future__ import annotations

import json

from conftest import features, records, run_cli

INPUT = [
    {"t": "2026-08-13T19:00:00", "seg": "a",
     "text": "千葉県柏市と市原市で猛烈な雨が降り警報が出ました"},
    {"t": "2026-08-13T19:05:00", "seg": "b", "text": "次の曲をお送りします"},
    {"t": "2026-08-13T19:10:00", "seg": "c", "text": "千葉市で氾濫の危険が高まっています"},
]


def write_input(tmp_path, rows=INPUT):
    p = tmp_path / "in.jsonl"
    body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    p.write_text(body, encoding="utf-8")
    return p


def test_emits_one_labeled_record_per_input_record(tmp_path, env, lenses):
    src = write_input(tmp_path)
    r = run_cli("lens", [str(src), "--lens", str(lenses / "ja-radio-disaster"),
                        "--out", str(tmp_path / "o")], env)
    assert r.returncode == 0, r.stderr
    assert len(records(tmp_path / "o" / "labeled.jsonl")) == 3


def test_carries_the_input_fields_through_untouched(tmp_path, env, lenses):
    src = write_input(tmp_path)
    run_cli("lens", [str(src), "--lens", str(lenses / "ja-radio-disaster"),
                    "--out", str(tmp_path / "o")], env)
    rows = {r["seg"]: r for r in records(tmp_path / "o" / "labeled.jsonl")}
    assert set(rows) == {"a", "b", "c"}
    assert rows["a"]["t"] == "2026-08-13T19:00:00"
    assert rows["a"]["text"] == INPUT[0]["text"]


def test_adds_every_field_the_schema_declares(tmp_path, env, lenses):
    src = write_input(tmp_path)
    run_cli("lens", [str(src), "--lens", str(lenses / "ja-radio-disaster"),
                    "--out", str(tmp_path / "o")], env)
    row = records(tmp_path / "o" / "labeled.jsonl")[0]
    assert {"category", "topic", "is_disaster"} <= set(row)


def test_selection_defaults_to_is_disaster(tmp_path, env, lenses):
    src = write_input(tmp_path)
    run_cli("lens", [str(src), "--lens", str(lenses / "ja-radio-disaster"),
                    "--out", str(tmp_path / "o")], env)
    assert len(records(tmp_path / "o" / "selected.jsonl")) == 2


def test_a_narrower_select_is_honoured(tmp_path, env, lenses):
    src = write_input(tmp_path)
    r = run_cli("lens", [str(src), "--lens", str(lenses / "ja-radio-disaster"),
                        "--select", '.is_disaster and (.category == "気象")',
                        "--out", str(tmp_path / "o")], env)
    assert r.returncode == 0, r.stderr
    # 気象 is set only when the text mentions rain or a warning, so the record
    # about a river does not match.
    assert len(records(tmp_path / "o" / "selected.jsonl")) == 1


def test_selected_records_are_reduced_to_id_and_text(tmp_path, env, lenses):
    src = write_input(tmp_path)
    run_cli("lens", [str(src), "--lens", str(lenses / "ja-radio-disaster"),
                    "--out", str(tmp_path / "o")], env)
    assert set(records(tmp_path / "o" / "selected.jsonl")[0]) == {"id", "text"}


def test_every_place_carries_the_time_of_its_record(tmp_path, env, lenses):
    src = write_input(tmp_path)
    run_cli("lens", [str(src), "--lens", str(lenses / "ja-radio-disaster"),
                    "--out", str(tmp_path / "o")], env)
    feats = features(tmp_path / "o" / "places.geojson")
    assert feats
    assert all(f["properties"]["t"] for f in feats)
    a = [f for f in feats if f["properties"]["input_id"] == "a"]
    assert a and a[0]["properties"]["t"] == "2026-08-13T19:00:00"


def test_only_resolved_places_get_coordinates(tmp_path, env, lenses):
    src = write_input(tmp_path)
    run_cli("lens", [str(src), "--lens", str(lenses / "ja-radio-disaster"),
                    "--out", str(tmp_path / "o")], env)
    for f in features(tmp_path / "o" / "places.geojson"):
        if f["properties"]["status"] != "resolved":
            assert f["geometry"] is None


def test_the_time_join_can_be_switched_off(tmp_path, env, lenses):
    src = write_input(tmp_path)
    run_cli("lens", [str(src), "--lens", str(lenses / "ja-radio-disaster"),
                    "--time-field", "", "--out", str(tmp_path / "o")], env)
    assert all("t" not in f["properties"] for f in features(tmp_path / "o" / "places.geojson"))


def test_a_lens_gate_drops_records_before_the_model(tmp_path, env, lenses):
    src = write_input(tmp_path)
    r = run_cli("lens", [str(src), "--lens", str(lenses / "ja-radio-event"),
                        "--select", ".is_event", "--place-field", "place",
                        "--out", str(tmp_path / "o")], env)
    assert r.returncode == 0, r.stderr
    # None of the three inputs mentions a festival, so nothing reaches the model.
    assert records(tmp_path / "o" / "labeled.jsonl") == []
    assert "gate kept 0 of 3" in r.stderr


def test_records_matching_the_gate_go_through(tmp_path, env, lenses):
    src = write_input(tmp_path, [
        {"t": "2026-08-02T18:00:00", "seg": "f",
         "text": "長岡市の花火大会の交通規制をお伝えします"},
    ])
    r = run_cli("lens", [str(src), "--lens", str(lenses / "ja-radio-event"),
                        "--select", ".is_event", "--place-field", "place",
                        "--out", str(tmp_path / "o")], env)
    assert r.returncode == 0, r.stderr
    assert len(records(tmp_path / "o" / "labeled.jsonl")) == 1
    assert len(features(tmp_path / "o" / "places.geojson")) == 1


def test_a_record_with_empty_text_still_produces_a_row(tmp_path, env, lenses):
    src = write_input(tmp_path, [{"t": "2026-08-14T13:00:00", "seg": "z", "text": ""}])
    r = run_cli("lens", [str(src), "--lens", str(lenses / "ja-radio-disaster"),
                        "--out", str(tmp_path / "o")], env)
    assert r.returncode == 0, r.stderr
    rows = records(tmp_path / "o" / "labeled.jsonl")
    assert len(rows) == 1
    assert rows[0]["is_disaster"] is None


def test_stdin_is_refused_with_an_explanation(tmp_path, env, lenses):
    """Each input file gets an output file named after it, and standard input
    has no name. Asking for a file instead is a one-line fix, so say so rather
    than inventing a name."""
    stdin = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in INPUT)
    r = run_cli("lens", ["-", "--lens", str(lenses / "ja-radio-disaster"),
                        "--out", str(tmp_path / "o")], env, stdin=stdin)
    assert r.returncode == 1
    assert "standard input" in r.stderr
    assert "Traceback" not in r.stderr


def test_the_whole_fixture_set_runs(tmp_path, env, lenses, fixtures):
    r = run_cli("lens", [str(fixtures / "transcripts.jsonl"),
                        "--lens", str(lenses / "ja-radio-disaster"),
                        "--out", str(tmp_path / "o")], env)
    assert r.returncode == 0, r.stderr
    rows = records(tmp_path / "o" / "labeled.jsonl")
    assert len(rows) == 13
    # The misheard place name must not acquire coordinates. The mention comes
    # back as the whole run of characters before the 市, so match on containment
    # rather than equality.
    feats = features(tmp_path / "o" / "places.geojson")
    misheard = [f for f in feats if "森谷市" in (f["properties"]["mention"] or "")]
    assert misheard, "the fixture with a misheard place name produced no mention"
    assert all(f["geometry"] is None for f in misheard)
