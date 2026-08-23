# Tests

```bash
uv venv && uv pip install -e '.[dev]'
uv run --no-project python -m pytest tests/ -q
uv run --no-project ruff check src tests
```

Sixty tests, about fifteen seconds. Nothing reaches the network.

## Why the tests do not call a language model

The same prompt does not produce the same answer twice, so a test that asked a
model for its input or its expected value would be measuring the weather.

`tests/stubs/` holds stand-ins for `aiq` and `locitorium`, found ahead of
anything installed because the fixture puts them first on PATH. They derive
their answers from the input text by simple rules, so a test can predict them
exactly. The stub for `locitorium` knows four municipalities and rejects
everything else, which is how the resolvable and unresolvable paths both stay
covered without a Nominatim.

`detempus` is real, not stubbed. It is deterministic and runs offline, so
faking it would only hide whether the two agree about the shape of the data.

## Where the model is used

Once, to make the fixtures. `tests/fixtures/generate.sh` asks for thirteen
synthetic transcripts and the result is committed. They are synthetic because
tests need transcripts that read like broadcast speech, and redistributing a
broadcaster's recordings is a licensing question this project does not need to
have. See [fixtures/README.md](fixtures/README.md), including the two edits
made by hand and why.

## Checking the real thing

The tests say the plumbing works, not that the lens still works. For that, run
it against the services and read the output:

```bash
speechmap tests/fixtures/transcripts.jsonl \
  --lens lenses/ja-radio-disaster --out /tmp/check
```

On the fixtures as committed, the two municipalities that are spelled correctly
resolve to coordinates and the misheard one comes back `rejected` with none.
That is the property worth checking by eye after changing a lens.

## The synthetic series

`tests/test_series.py` builds thirty days of counts with a deliberate spike, so
the expected candidate is known rather than discovered. The counts wobble from
day to day on purpose, so the baseline has ordinary variation to be robust
about and the score comes out on detempus's usual MAD scale.

A perfectly flat series is a different case, and detempus now handles it: the
residual MAD collapses to floating-point noise, so it falls back to the
mean-absolute-deviation form of the same score and records
`method.score_scale`. Before that fix a single spike in a flat series scored
around 10^13. Keeping the wobble here means these tests exercise the ordinary
path rather than the fallback.
