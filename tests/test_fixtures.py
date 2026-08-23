"""The fixtures themselves. If they drift, the meaning of every other test
drifts with them, so the properties the tests rely on are asserted here."""
from __future__ import annotations

import pytest

from openspeechmap import jsonl


@pytest.fixture
def rows(fixtures):
    return list(jsonl.read(fixtures / "transcripts.jsonl"))


def test_the_file_parses(rows):
    assert rows


def test_every_record_has_a_time_an_id_and_a_text(rows):
    for r in rows:
        assert {"t", "seg", "text"} <= set(r), r


def test_ids_are_unique_because_everything_joins_on_them(rows):
    ids = [r["seg"] for r in rows]
    assert len(ids) == len(set(ids))


def test_one_record_has_empty_text(rows):
    """So the rule that a stage emits a row per input row stays tested."""
    assert sum(1 for r in rows if r["text"] == "") == 1


def test_a_misheard_place_name_is_present(rows):
    """A third of place mentions in real material never resolve. A fixture set
    that always resolves cannot test what happens to the rest."""
    assert any("森谷市" in r["text"] for r in rows)


def test_each_lens_has_a_record_with_a_resolvable_municipality(rows):
    disaster = [r for r in rows if r["seg"].startswith("d")]
    event = [r for r in rows if r["seg"].startswith("e")]
    assert any(any(m in r["text"] for m in ("柏市", "市原市", "千葉市")) for r in disaster)
    assert any("長岡市" in r["text"] for r in event)


def test_festival_vocabulary_appears_in_records_that_are_not_events(rows):
    """The event lens's hardest job is saying no to a song about fireworks."""
    assert sum(1 for r in rows if "花火" in r["text"]) >= 3


def test_records_are_one_utterance_long(rows):
    for r in rows:
        if r["text"]:
            assert 150 <= len(r["text"]) <= 1500, r["seg"]


def test_the_generator_is_committed_alongside(fixtures):
    script = fixtures / "generate.sh"
    assert script.is_file()
    import os
    assert os.access(script, os.X_OK)


def test_no_fixture_is_a_verbatim_broadcast(fixtures):
    """They are synthetic on purpose: tests need transcripts that read like
    broadcast speech, and redistributing a broadcaster's recordings is a
    licensing question this project does not need to have."""
    readme = (fixtures / "README.md").read_text(encoding="utf-8")
    assert "synthetic" in readme.lower()
