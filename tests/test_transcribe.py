"""Audio to timestamped transcripts.

whisper.cpp does the recognition. What is here is the part around it: work out
when each segment was recorded, cut it into pieces the recogniser can hold, and
emit one record per piece with the time on it.

The time is the whole point. Nothing downstream reads audio metadata, so if this
stage gets the timestamp wrong every later answer is wrong in a way that looks
plausible.
"""
from __future__ import annotations

import datetime as dt

from openspeechmap import transcribe

# --- working out when a file was recorded ------------------------------------

def test_the_time_comes_from_the_filename_when_it_is_there(tmp_path):
    p = tmp_path / "JOAK-FM-20260813-190000.ts"
    p.write_bytes(b"")
    assert transcribe.started_at(p) == dt.datetime(2026, 8, 13, 19, 0, 0)


def test_a_label_with_hyphens_in_it_still_parses(tmp_path):
    p = tmp_path / "NPR-News-20260823-170218.ts"
    p.write_bytes(b"")
    assert transcribe.started_at(p) == dt.datetime(2026, 8, 23, 17, 2, 18)


def test_the_file_mtime_is_used_when_the_name_says_nothing(tmp_path):
    p = tmp_path / "interview.mp3"
    p.write_bytes(b"")
    import os
    when = dt.datetime(2026, 5, 4, 3, 2, 1)
    os.utime(p, (when.timestamp(), when.timestamp()))
    assert transcribe.started_at(p) == when


def test_an_explicit_start_wins_over_both(tmp_path):
    p = tmp_path / "JOAK-FM-20260813-190000.ts"
    p.write_bytes(b"")
    given = dt.datetime(2001, 1, 1)
    assert transcribe.started_at(p, override=given) == given


def test_a_nonsense_timestamp_in_the_name_falls_back_rather_than_lying(tmp_path):
    """20261345 is not a date. Guessing would put records in the wrong bucket."""
    p = tmp_path / "X-20261345-999999.ts"
    p.write_bytes(b"")
    import os
    when = dt.datetime(2026, 6, 1, 12, 0, 0)
    os.utime(p, (when.timestamp(), when.timestamp()))
    assert transcribe.started_at(p) == when


# --- the record it produces --------------------------------------------------

def test_each_chunk_gets_its_own_time(tmp_path):
    """A five-minute recording cut into one-minute pieces is five records, a
    minute apart, not five records with the same timestamp."""
    start = dt.datetime(2026, 8, 13, 19, 0, 0)
    records = [
        transcribe.record(
            source="JOAK-FM-20260813-190000.ts", start=start, offset=i * 60,
            text=f"piece {i}",
        )
        for i in range(3)
    ]
    assert [r["t"] for r in records] == [
        "2026-08-13T19:00:00", "2026-08-13T19:01:00", "2026-08-13T19:02:00",
    ]


def test_the_id_says_which_file_and_where_in_it(tmp_path):
    r = transcribe.record(
        source="JOAK-FM-20260813-190000.ts",
        start=dt.datetime(2026, 8, 13, 19, 0, 0), offset=120, text="hello",
    )
    assert r["seg"] == "JOAK-FM-20260813-190000.ts@120"


def test_the_text_is_carried_verbatim():
    r = transcribe.record(source="a.ts", start=dt.datetime(2026, 1, 1), offset=0,
                          text="  spaced  out  ")
    assert r["text"] == "spaced  out"


# --- cutting the audio up ----------------------------------------------------

def test_chunk_offsets_cover_the_whole_file():
    assert transcribe.offsets(duration=180, chunk_sec=60) == [0, 60, 120]


def test_a_trailing_part_shorter_than_a_chunk_is_still_included():
    assert transcribe.offsets(duration=150, chunk_sec=60) == [0, 60, 120]


def test_a_file_shorter_than_one_chunk_is_one_chunk():
    assert transcribe.offsets(duration=20, chunk_sec=60) == [0]


def test_a_sliver_at_the_end_is_dropped():
    """Half a second of audio produces nothing but a hallucination."""
    assert transcribe.offsets(duration=120.4, chunk_sec=60) == [0, 60]


def test_a_zero_length_file_produces_nothing():
    assert transcribe.offsets(duration=0, chunk_sec=60) == []


# --- talking to whisper ------------------------------------------------------

def test_the_request_carries_the_language_when_given():
    fields = transcribe.request_fields(language="ja")
    assert fields["language"] == "ja"


def test_no_language_lets_the_recogniser_decide():
    assert "language" not in transcribe.request_fields(language=None)


def test_an_empty_transcript_is_still_a_record():
    """A quiet minute is a fact about that minute. Dropping it would leave a
    hole that the time series cannot tell from a minute never recorded."""
    r = transcribe.record(source="a.ts", start=dt.datetime(2026, 1, 1), offset=0, text="")
    assert r["text"] == ""
    assert r["seg"] == "a.ts@0"
