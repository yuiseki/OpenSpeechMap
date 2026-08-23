# The commands

Five commands, one per stage plus one that runs the stages a declaration names.
Each is idempotent and each leaves a file behind, so any of them can be re-run
alone. See [ARCHITECTURE.md](ARCHITECTURE.md) for why they are separate and
[PREREQUISITES.md](PREREQUISITES.md) for what each one needs installed.

```
speechmap record      a stream or the airwaves  ->  .ts segments
speechmap transcribe  segments                  ->  timestamped transcripts
speechmap lens             transcripts               ->  labels and grounded places
speechmap series      labels                    ->  counts, candidates, a schedule
speechmap pass        a speechmap.yaml          ->  the three above, over what is new
```

`speechmap check` reports, stage by stage, what is reachable.

## Capture

If the speech you want is on the air rather than on your disk:

```bash
speechmap record --out ./recordings --source sdr --label JOAK-FM \
  --freq 82.5M --gain 19.7 --retention-hours 168 --max-gb 50
speechmap record --out ./recordings --source http --label OKAPI \
  --url https://example.invalid/stream --retention-hours 672
```

ffmpeg does the recording; what this adds is the part ffmpeg does not do.
It restarts the capture when it dies, which matters because that failure is
silent: a recording that stopped three weeks ago looks exactly like one that is
running. And it deletes old segments by age and by total size, leaving the file
being written alone.

Each segment is named `<LABEL>-YYYYMMDD-HHMMSS.ts`, and that timestamp is how
the time reaches everything downstream. Nothing here reads audio metadata.

## Transcribe

```bash
speechmap transcribe ./recordings --out ./transcripts \
  --chunk-sec 60 --language ja
```

Takes a file or a directory of them, cuts each into pieces the recogniser can
hold, and writes one record per piece. whisper.cpp does the recognition, over
HTTP; point `--whisper-url` at your server.

Three decisions in here are worth knowing, because each of them is a way to get
quietly wrong answers later.

**Where the time comes from.** The filename if it looks like
`<LABEL>-YYYYMMDD-HHMMSS`, otherwise the file's mtime, otherwise `--start`. The
filename wins over mtime because copying or rsyncing a file keeps its name and
loses its mtime. A name-shaped string that is not a date, like `20261345`, falls
back rather than being guessed at: a wrong timestamp puts records in the wrong
bucket, and nothing downstream can tell.

**A minute per record, by default.** Shorter and there are no place names in it.
Longer and the summary the lens produces rounds them off, which is the one thing
the place resolver cannot survive.

**A silent minute is still a record.** It is a fact about that minute. Dropping
it leaves a hole the time series cannot tell from a minute that was never
recorded.

If you already have transcripts, meeting minutes, subtitles or a timestamped
article archive, skip this and hand them to `speechmap` directly.

## Apply a lens, and ground the places

```bash
speechmap lens ./transcripts --lens lenses/ja-radio-disaster --out ./out
```

Input is one JSON object per line, carrying a time, an id and some text:

```json
{"t": "2026-08-13T19:00:00", "seg": "a", "text": "千葉県柏市で猛烈な雨が降り..."}
```

You need an OpenAI-compatible LLM endpoint and a
[locitorium](https://github.com/yuiseki/locitorium) server. Nothing is sent to
a third-party API.

## What you get

Three files, and a line saying what happened:

```
speechmap: 20 in -> 20 labeled -> 13 selected -> 29 places
```

`labeled.jsonl` is one line per input line, with the lens fields added. Real
output, from a Japanese radio bulletin during the Chiba floods of 2026-08-13:

```json
{
  "t": "2026-08-13T19:00:50",
  "seg": "JOAK-FM-20260813-185850.ts@120",
  "text": "…特に千葉県では、発発した雨雲がかかり続けていて…柏市付近と安倍湖市付近でおよそ100ミリ、…市原市付近でおよそ100ミリのいずれも猛烈な雨が降ったとみられ、気象庁は記録的短時間大雨の気象防災速報を発表しました。…",
  "category": "気象",
  "topic": "千葉県柏市、市原市、千葉市などで記録的短時間大雨。気象庁が防災速報発表。",
  "is_disaster": true
}
```

`places.geojson` is one feature per place mentioned, grounded where possible:

```json
{
  "type": "Feature",
  "geometry": {"type": "Point", "coordinates": [140.1062653, 35.6070629]},
  "properties": {
    "input_id": "JOAK-FM-20260813-185850.ts@120",
    "mention": "千葉市",
    "status": "resolved",
    "osm_type": "relation",
    "osm_id": 2679956,
    "display_name": "千葉市, 千葉県, 日本",
    "country_code": "JP"
  }
}
```

`input_id` is the id you gave, carried through untouched, so features join back
to the records they came from.

Note what the transcription got wrong: 発発した for 発達した, 安倍湖市 for
我孫子市. The summary still carries 柏市, 市原市 and 千葉市 exactly as spoken,
which is the only reason they resolve. Mentions that were misheard come back
with `status` set to `rejected` or `no_candidate` and no coordinates, rather
than being placed somewhere wrong. In this run 23 of 29 resolved.

This is situational awareness assembled from imperfect transcription and a
model's judgement. It is not a source of truth.

[AGENTS.md](AGENTS.md) is the full contract, written for the agent that will
actually run this.

## Keeping it running

The everyday shape of this is a stream that never stops and a directory that
keeps growing. Write it down once:

```yaml
# speechmap.yaml
source:
  kind: http
  url: http://npr-ice.streamguys1.com/live.mp3
  label: NPR
  segment_sec: 30
out: ./out
lens: lenses/en-radio-disaster
transcribe:
  chunk_sec: 30
  language: en
series:
  bucket: hour
```

```bash
speechmap --plan     # says what will run, and how to start the capture
speechmap record --out ./out/recordings --source http --label NPR \
  --url http://npr-ice.streamguys1.com/live.mp3 --segment-sec 30 &
speechmap pass            # transcribe -> lens -> series, over whatever is new
```

Put that last line on a timer. Every stage is idempotent: one output file per
input file, and the output's existence is the record that the input is done. A
pass over unchanged input costs a directory listing.

```
 transcribe  1 file(s) -> 1 records (0 with no speech)
 lens        1 file(s) -> 1 records; 3 labelled, 0 selected, 0 places
 series      nothing to count yet
```

Deleting an output redoes exactly that input, which is the property that makes
this safe to leave alone. `--redo` on either stage ignores what is there.

Capture is not part of a pass, because recording never finishes and so cannot be
a step in something that ends. Paths in the file are resolved against the file,
so it means the same thing run from anywhere, including from a timer with no
meaningful working directory. An unknown key is an error rather than something
ignored: a setting you think you set and have not is worse than a typo you are
told about.

## Look at it

```bash
speechmap series out/labeled.jsonl --out ./out   # counts over time, via detempus
cd web && npm install && npm run dev                 # map + chart + candidates
```

`speechmap series` reshapes the labeled records into counts and hands them to
[detempus](https://github.com/yuiseki/detempus). What comes back per series is
a score for every bucket, the candidates above the threshold, the change points
where the level moved, and a `method` block recording how the answer was
produced. The viewer in [web/](web/) reads that and `places.geojson`, and
clicking a candidate moves the map to the places mentioned in that bucket.

Over 55 days of Japanese public radio, the `気象` (weather) series peaked on
2026-08-13 with a score of 19.18 (the Chiba floods), and `ニュース` (news) on
2026-07-28 with 8.67 (the Kumamoto earthquake). No threshold was passed on the
command line; those two stand out against a default cut of 3.5.

Two things about that output are worth knowing before quoting it.

A candidate is a reason to go and read what was said on that date, not a
finding. Sorting by score rather than by count matters, because a catch-all
category accumulates candidates while being the least interesting: on this data
`その他` had seven and `気象` had two.

Check `method.score_scale` before comparing scores across series. `mad` is the
usual scale. `meanad` means the series had no ordinary variation at all, so its
numbers are not on the same footing as another series'. Change points are a
separate answer from candidates: the level moving is not a spike.


### Finding out when something is on the air

`--bucket hour` and the `profile` in the answer, which is the broadcaster's
schedule:

```console
$ speechmap series out/labeled.jsonl --bucket hour --out ./out
$ jq '.series[] | select(.key=="ニュース") | .profile | sort_by(-.center) | .[:3]' out/series.json
[{"phase": 16, "label": "19", "center": 22.0, "scale": 3.191, "n": 26},
 {"phase": 9,  "label": "12", "center": 14.5, "scale": 2.869, "n": 26},
 {"phase": 4,  "label": "07", "center": 13.5, "scale": 3.276, "n": 26}]
```

News at 07:00, 12:00 and 19:00. Read `label`, not `phase`: the phase is a
position in the cycle and only matches the clock if the series starts at
midnight.

That is not a separate feature. The periodic component has to be subtracted
before anything can be called anomalous, so asking to see it costs nothing. It
also tells you which hours are worth transcribing densely, which is the
difference between running a language model over three hours a day and
twenty-four.

The cycle must have come round at least eight times before it is claimed;
otherwise `method.seasonal` is `none` and `profile` is empty. The bundled sample
is 26 daily buckets against a weekly period, so it is one of those.

## Reading the output as an agent

[../AGENTS.md](../AGENTS.md) is the contract: what each file contains, how to
read a place that failed to ground, what the expected failures mean, and what
not to conclude from a candidate.
