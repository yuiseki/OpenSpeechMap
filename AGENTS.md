# Driving OpenSpeechMap

This file is for an agent working on behalf of someone who wants signals found
in speech. Read it and you should be able to run the thing without asking them
anything that the repository can answer.

## What this does, in one paragraph

You give it timestamped transcripts. It asks a language model, once per
record, to fill in the fields a *lens* declares. It then takes one of those
fields and resolves the place names in it to OpenStreetMap entities. Out comes
GeoJSON you can map, plus the labeled records you can count over time.

It returns candidates, not verdicts. Nothing here decides that a disaster
happened; it decides which records are worth a human or a downstream tool
looking at.

## Before you start: what must be running

Two services. Neither is bundled, because both are useful on their own and
neither should be reimplemented here.

| service | why | check it |
|---|---|---|
| an OpenAI-compatible chat endpoint | applies the lens | `curl -s "$LLM_URL/models"` lists the model names you may pass to `--model` |
| a locitorium server | resolves place names to OSM entities | `curl -s -o /dev/null -w '%{http_code}' "$LOCI_URL/"` returns 200. There is no `/health`; `/docs` also answers |

locitorium needs a Nominatim instance behind it. See its own README.

Nothing is sent to a third-party API by this repository. The reference setup
is `llama.cpp` and a self-hosted Nominatim, both local.

Two commands must be reachable:

```bash
speechmap check       # says where each of them was found, or what to install
```

It needs `jq`, [aiq](https://github.com/yuiseki/aiq) (the fork, for `extract`),
[locitorium](https://github.com/yuiseki/locitorium) and
[detempus](https://github.com/yuiseki/detempus). `speechmap record` needs
`ffmpeg`, and `--source sdr` also needs `rtl_fm` from librtlsdr.

If they are not installed, point `AIQ` and `LOCITORIUM` at source checkouts
and `speechmap` will run them with `uv` instead. `aiq` is a fork of
[taylorai/aiq](https://github.com/taylorai/aiq) (MIT); `aiq extract` only
exists in that fork, not in upstream `aiq-cli`.

## The input you need to produce

One JSON object per line. Three things matter:

```json
{"t": "2026-08-13T19:00:00", "seg": "any-unique-id", "text": "千葉県柏市で猛烈な雨が降り..."}
```

- a time. Used for the time series, and for nothing else in the map stage.
  Any of `YYYY-MM-DD`, ISO 8601, `YYYYMMDDHH` will parse downstream.
- an id. Carried through every stage untouched, so you can join results back.
  Name it whatever you like and pass `--id-field`.
- the text. One record should be roughly one utterance or one minute of
  speech. Very long records get summarised into uselessness; very short ones
  carry no place names.

**If the person wants to monitor something on the air**, `speechmap record`
captures it into fixed-length segments and keeps the disk from filling:

```bash
speechmap record --out ./recordings --source http --label STATION \
  --url https://example.invalid/stream
speechmap record --out ./recordings --source sdr --label JOAK-FM --freq 82.5M
```

It runs until interrupted, so start it in the background or under whatever
supervises long jobs for you, and check back. Two things it does that ffmpeg
alone does not: restart the capture when it dies, and delete old segments by age
and by total size. The first matters because the failure is silent; if someone
says their recording "has been running for weeks", check the timestamp on the
newest file before believing it.

Segments are named `<LABEL>-YYYYMMDD-HHMMSS.ts`. That timestamp is the only
place the time comes from, so do not rename them.

**If the person has audio rather than transcripts**, `speechmap transcribe`
turns it into the shape above:

```bash
speechmap transcribe ./recordings --out ./transcripts \
  --chunk-sec 60 --language ja
```

It takes a file or a directory of them, and needs a whisper.cpp server. Three
things about it decide whether the later answers mean anything.

The time on each record comes from the filename when it looks like
`<LABEL>-YYYYMMDD-HHMMSS`, otherwise from the file's mtime, otherwise from
`--start`. If the person's files have neither a useful name nor a trustworthy
mtime, ask them when the recording began and pass `--start`; do not let it fall
through to an mtime you have reason to doubt. A wrong timestamp puts records in
the wrong bucket and nothing downstream can detect it.

`--chunk-sec` defaults to 60. Shorter and a chunk contains no place names;
longer and the lens's summary rounds them off, which is the one thing place
resolution cannot survive.

Chunks with no speech in them still produce a record, with empty text. Do not
filter them out to tidy the file: a silent minute is a fact about that minute,
and removing it leaves a hole the time series cannot tell from a minute that was
never recorded.

**If the person already has transcripts, meeting minutes, subtitles, or an
article archive**, use them directly. Audio is not required anywhere.

## Running it

```bash
speechmap lens transcripts.jsonl \
  --lens lenses/ja-radio-disaster \
  --out ./out
```

Lenses that ship here, and the flags each one needs:

```bash
# disaster reporting. --select and --place-field are the defaults
speechmap lens in.jsonl --lens lenses/ja-radio-disaster --out ./out

# festivals, fireworks and other public events
speechmap lens in.jsonl --lens lenses/ja-radio-event \
  --select '.is_event' --place-field place --out ./out
```

Each lens declares different fields, so `--select` and `--place-field` must
match the lens. Read its `schema.json` if you are unsure what fields exist.

Three files appear in `--out`:

| file | contents |
|---|---|
| `labeled.jsonl` | every input record, plus the lens fields. Same number of lines as the input |
| `selected.jsonl` | the ones `--select` kept, reduced to `{id, text}` |
| `places.geojson` | resolved places, each carrying `osm_type`, `osm_id`, `display_name`, `mention` and the `input_id` it came from |

If the lens directory contains `gate.txt`, records containing none of its
keywords never reach the model, and are not emitted. `labeled.jsonl` is then
shorter than the input, and the run reports how many keywords were in use. Do
not report a short `labeled.jsonl` as data loss when a gate is in play; check
whether the lens has a `gate.txt` first.

`--select` is a jq expression, defaulting to `.is_disaster`. The threshold
lives in your command, not inside the tool, so you can change what counts
without touching anything:

```bash
--select '.is_disaster and (.category != "音楽")'
```

Stages write files, so re-running a later stage alone is a matter of piping
the earlier file back in. Nothing is destructive except overwriting the
outputs.

## Reading the places honestly

A feature with no `osm_id` was mentioned but not grounded. Two causes, and
they need different responses:

- the transcription mangled the name. `三宝市` for `三原市`, `森谷市` for
  `守谷市`. Nothing downstream can fix this; report it as a transcription
  problem.
- the mention has no extent. `関東`, `北部`, `沿岸部`. Correctly not placed.

Roughly a third of mentions fail to ground in Japanese radio material. That is
the normal rate, not a malfunction.

Two spellings of the same place come back with the same `osm_id`. Deduplicate
on `osm_type` plus `osm_id`, never on the spelling, and never write a
normalisation dictionary. That is what grounding is for.

## Writing a lens

Copy `lenses/ja-radio-disaster` and edit three text files. No code changes.
See [lenses/README.md](lenses/README.md) for what each file does and for two
mistakes worth avoiding.

The one rule that matters: whichever field you point `--place-field` at is the
*only* text the place resolver sees. If your instruction lets the model
summarise a place name away, that place is gone. Tell it to keep place names
verbatim.

## Failure modes and what they mean

Expected failures print one line and exit non-zero. There is no traceback to
read; the line says what to fix.

| message | what to do |
|---|---|
| `lens is missing schema.json` | the `--lens` directory is not a lens |
| `aiq not found`, `locitorium not found`, `detempus not found` | install it, or set `AIQ` / `LOCITORIUM` / `DETEMPUS` to a checkout. `speechmap check` reports all of them at once |
| `no audio files. Looked for ...` | the directory has recordings under some other extension, or none |
| `did not answer with JSON` | the whisper URL is answering, but not as a whisper.cpp server. Check `--whisper-url` ends in `/inference` |
| a record with `null` in every lens field | its text was empty. The record is still emitted, on purpose, so counts line up |
| every transcript is empty | the recording is silent. Measure it before blaming the recogniser: `ffmpeg -i FILE -af volumedetect -f null /dev/null` and look at `mean_volume`. Around -91 dB is digital silence, and a stream can go silent while still delivering bytes |
| `places.geojson` has zero features | check `selected.jsonl` first. If it is empty, `--select` matched nothing; if it has rows, locitorium is not answering |

An empty `selected.jsonl` is a normal outcome, not an error. Most speech is
not about the thing you are looking for.

## Things not to do

- Do not treat this as a source of truth. It is situational awareness assembled
  from imperfect transcription and a model's judgement.
- Do not remove the time from records to make them tidier. The time series
  stage needs it and cannot recover it.
- Do not deduplicate places by name.
- Do not raise `--concurrency` far above the endpoint's capacity; the LLM is
  usually the single scarce resource in the whole chain.

## Counting over time

`speechmap series` does the reshaping and calls
[detempus](https://github.com/yuiseki/detempus) for you:

```bash
speechmap series out/labeled.jsonl --out ./out
```

It writes `series.json`: one series per value of `--key-field` (default
`category`), each carrying the counts, the baseline, a score for every point,
the candidates above the threshold, the change points, and detempus's own
`method` block saying how it was produced.

Options worth knowing:

| flag | why |
|---|---|
| `--bucket day\|hour` | hourly needs a lot of data before the daily cycle is estimable |
| `--key-field ""` | one combined series instead of one per category |
| `--select EXPR` | same jq expression convention as `speechmap` |
| `--threshold N` | passed to detempus. The default cut is 3.5 |

## Finding out when something is on the air

If someone asks which hours carry the thing they care about, that is
`--bucket hour` and then the `profile` in the answer, not a separate tool:

```bash
speechmap series out/labeled.jsonl --bucket hour --out ./out
jq '.series[] | select(.key=="ニュース") | .profile | sort_by(-.center) | .[:5]' out/series.json
```

```json
[{"phase": 16, "label": "19", "center": 22.0, "scale": 3.191, "n": 26},
 {"phase": 9,  "label": "12", "center": 14.5, "scale": 2.869, "n": 26},
 {"phase": 4,  "label": "07", "center": 13.5, "scale": 3.276, "n": 26}]
```

That is the broadcaster's news schedule. Read `label`, not `phase`: the phase is
a position in the cycle, so it only matches the clock if the series happens to
start at midnight.

The profile is the periodic component that has to be subtracted before anything
can be called anomalous, so it costs nothing extra. Two conditions:

- The cycle must have come round at least eight times. With less, detempus sets
  `method.seasonal` to `none` and leaves `profile` empty rather than claim a
  pattern it cannot estimate. Twenty-six days of daily buckets against a weekly
  period is not enough; a few weeks of hourly buckets is.
- Do not use the anomaly list to answer this question. Being on the air at 19:00
  every day is the most regular thing in the data, so it is not an anomaly. If
  regular hours are showing up as candidates, the data is probably mostly empty
  buckets, and zero-filling has put the baseline near zero.

Practical use: this is how you decide which hours to transcribe densely.
Recording twenty-four hours and running a language model over all of it is
waste when the material you want is in three hours of it.

## Reading the candidates honestly

Report them as candidates. A high score means the count for that bucket
was far from the baseline, which is a reason to go and read what was actually
said then, not a finding in itself. Before quoting a date, filter
`labeled.jsonl` to it and look.

Two failure shapes to recognise. A series with `n` smaller than about three
periods cannot have a meaningful baseline, and detempus will say so by
returning no candidates rather than by complaining. And a catch-all category
(`その他`, `(none)`) tends to accumulate the most candidates while being the
least interesting; sort by score, not by count.

Check `method.score_scale` before comparing scores between series. `mad` is the
usual scale. `meanad` means the series had no ordinary variation at all -- flat,
with one spike -- so the score was computed a different way and its numbers are
not on the same footing as another series'. `none` means there was nothing to
score.

## Looking at the output

```bash
cd web && npm install && npm run dev
```

A map, the chart, and the candidate list. It reads `series.json` and
`places.geojson` and nothing else; see [web/README.md](web/README.md) for
pointing it at a directory other than the bundled sample.

Clicking a candidate filters the markers to that bucket, which works because
`speechmap` copied each record's time onto the places resolved from it. A
candidate labelled "no places" means nothing in that bucket resolved to
coordinates, usually because the run that produced `places.geojson` covered a
narrower slice than the one that produced `series.json`.
