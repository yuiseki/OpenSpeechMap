"""`speechmap` with no arguments: capture and passes, kept running.

This is the shape the pipeline is actually used in. Recording never ends and
passes happen over and over, so the thing you start has to hold both, and one of
them failing must not take the other down with it.

No real audio here. The capture is a fake that counts how long it was asked to
stay alive, and the pass is a fake that can be told to fail.
"""
from __future__ import annotations

import threading

from openspeechmap import runner


class Recorder:
    """Stands in for the capture. Records that it ran and when it was stopped."""

    def __init__(self, die_after: int | None = None):
        self.started = 0
        self.stopped = threading.Event()
        self.die_after = die_after

    def __call__(self, should_stop):
        self.started += 1
        polls = 0
        while not should_stop():
            polls += 1
            if self.die_after is not None and polls >= self.die_after:
                raise RuntimeError("capture fell over")
        self.stopped.set()


def passes(results):
    """A pass function that returns each of `results` in turn, then the last."""
    calls = []

    def run(cfg):
        calls.append(cfg)
        i = min(len(calls) - 1, len(results) - 1)
        outcome = results[i]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    run.calls = calls
    return run


def a_pass(ok=True, message="fine"):
    return [[runner.Step(stage="lens", ok=ok, message=message)]]


def test_it_runs_passes_until_told_to_stop(monkeypatch):
    done = passes(a_pass())
    monkeypatch.setattr(runner, "once", done)
    stop = threading.Event()

    def after_two(_):
        if len(done.calls) >= 2:
            stop.set()

    runner.forever(cfg=object(), interval=0, capture=None, stop=stop,
                   on_pass=after_two)
    assert len(done.calls) >= 2


def test_the_capture_runs_alongside_the_passes(monkeypatch):
    recorder = Recorder()
    done = passes(a_pass())
    monkeypatch.setattr(runner, "once", done)
    stop = threading.Event()
    runner.forever(cfg=object(), interval=0, capture=recorder, stop=stop,
                   on_pass=lambda _: stop.set())
    assert recorder.started == 1
    assert recorder.stopped.wait(timeout=5), "the capture was not told to stop"


def test_a_failing_pass_does_not_stop_the_run(monkeypatch):
    """The model endpoint going away for a minute must not end a run that has
    been recording for a week."""
    done = passes([RuntimeError("endpoint down"), a_pass()[0]])
    monkeypatch.setattr(runner, "once", done)
    stop = threading.Event()
    seen = []

    def watch(result):
        seen.append(result)
        if len(seen) >= 2:
            stop.set()

    runner.forever(cfg=object(), interval=0, capture=None, stop=stop, on_pass=watch)
    assert len(done.calls) >= 2
    assert seen[0] is None, "a pass that raised should be reported as no result"


def test_a_capture_that_dies_is_reported_but_the_passes_continue(monkeypatch):
    """Whatever is on the other end of the stream is not this program's fault,
    and the transcripts already on disk are still worth processing."""
    recorder = Recorder(die_after=1)
    done = passes(a_pass())
    monkeypatch.setattr(runner, "once", done)
    stop = threading.Event()
    problems = []
    runner.forever(cfg=object(), interval=0, capture=recorder, stop=stop,
                   on_pass=lambda _: stop.set(),
                   on_capture_lost=problems.append)
    assert len(done.calls) >= 1
    assert problems and "fell over" in str(problems[0])


def test_stopping_is_not_an_error(monkeypatch):
    done = passes(a_pass())
    monkeypatch.setattr(runner, "once", done)
    stop = threading.Event()
    stop.set()
    runner.forever(cfg=object(), interval=0, capture=None, stop=stop)
    assert done.calls == [], "a run stopped before it began should do nothing"


def test_an_empty_recordings_directory_is_not_a_failure(tmp_path, lenses, env,
                                                        monkeypatch):
    """The first pass happens before the first recording is finished. Reporting
    that as an error on every fresh start teaches whoever is watching that the
    exclamation mark means nothing."""
    import shutil

    from openspeechmap import config

    shutil.copytree(lenses, tmp_path / "lenses", dirs_exist_ok=True)
    (tmp_path / "rec").mkdir()
    (tmp_path / "speechmap.yaml").write_text("""
source:
  kind: dir
  path: ./rec
out: ./out
lens: ./lenses/ja-radio-disaster
""", encoding="utf-8")
    monkeypatch.setenv("PATH", env["PATH"])
    monkeypatch.setenv("DETEMPUS", env["DETEMPUS"])
    cfg = config.load(tmp_path / "speechmap.yaml")
    done = runner.once(cfg)
    assert done[0].stage == "transcribe"
    assert done[0].ok, done[0].message
    assert "nothing" in done[0].message.lower()
    # And the stages after it are not attempted, because there is nothing yet.
    assert [s.stage for s in done] == ["transcribe"]
