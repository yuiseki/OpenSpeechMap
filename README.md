# OpenSpeechMap

Find the signals you care about in speech, and put them on a map and a
timeline.

A local radio station names the ward that flooded, the river that broke, the
road that closed, hours before any of it reaches a structured feed.
OpenSpeechMap listens to that, decides what matters using a lens you define,
grounds the place names in OpenStreetMap, and emits GeoJSON.

The theme is yours. Disasters, human security, threats to peacekeeping, or
festivals. A lens is three text files, not a code change.

![The viewer: where places were named, and the counts over time with the
unusual days marked](docs/viewer.png)

That is the bundled sample, 57 days of Japanese public radio, which is why the
labels in it are Japanese. The spike on 2026-07-28 is an earthquake in Kumamoto,
and it is why the markers cluster on Kyushu. Red bands are the days a score
crossed the threshold; the violet rules are where the level shifted rather than
spiked. Your own run puts your own lens and your own stream here.

日本語版: [README.ja.md](README.ja.md)

## Getting it running

Everything below is one path that works if you follow it. It records a public
radio stream, transcribes it, looks for disaster reporting, and puts what it
finds on a map.

### 1. Install

```bash
git clone https://github.com/yuiseki/OpenSpeechMap && cd OpenSpeechMap
uv venv && source .venv/bin/activate && uv pip install -e .
```

Every command below runs in that activated shell. If you open a new terminal,
`source .venv/bin/activate` again first, or `speechmap` will not be found.

Then the programs it drives, which it does not bundle:

```bash
sudo apt install ffmpeg jq curl               # or: brew install ffmpeg jq curl
uv pip install 'detempus[all] @ git+https://github.com/yuiseki/detempus'
git clone https://github.com/yuiseki/aiq        .tools/aiq
git clone https://github.com/yuiseki/locitorium .tools/locitorium
export AIQ="$PWD/.tools/aiq" LOCITORIUM="$PWD/.tools/locitorium"
```

None of those three is on PyPI yet. `aiq` and `locitorium` are cloned rather
than installed because each needs its own environment; `speechmap` runs them
from the checkout that `AIQ` and `LOCITORIUM` name. That `aiq` is a fork of
[taylorai/aiq](https://github.com/taylorai/aiq) (MIT); the `extract`
subcommand this uses exists only in the fork.

Those two clones land in `.tools/` inside this checkout, which is gitignored, so
they stay out of `git status` and `rm -rf .tools` undoes them. If you already
keep them elsewhere, skip the clones and point the two variables at what you
have. Like the activated venv, both variables have to be set in the shell that
runs `speechmap`, so put them somewhere durable if you do not want to repeat
them.

You also need three services running: an OpenAI-compatible LLM endpoint, a
whisper.cpp server, and locitorium with a Nominatim behind it. None of them is
a cloud API. [docs/PREREQUISITES.md](docs/PREREQUISITES.md) has the commands to
start each, package names for other platforms, and what `--source sdr` needs on
top.

Check before going further:

```bash
speechmap check
```

### 2. Declare what to listen to

```bash
cp speechmap.example.yaml speechmap.yaml
# edit the three endpoints and `model` in it, then:
speechmap --plan
```

The example is set up to record NPR's public stream and look for disaster
reporting in English. It is commented, including the alternatives for reading
off the air or starting from recordings you already have.

`--plan` prints what will run and the exact command to start the capture with.
It validates the declaration without doing any work, so a wrong path fails in a
second rather than twenty minutes in.

### 3. Start it

```bash
speechmap
```

That is the whole thing: it records, and every minute it transcribes what has
arrived, applies the lens, and counts over time. Ctrl-C stops it.

```
speechmap: capture and passes every 60s; Ctrl-C to stop
   transcribe  nothing recorded yet
   transcribe  4 file(s) -> 4 chunks -> 4 records (0 with no speech)
   lens        4 file(s) -> 4 records; 4 labelled, 3 selected, 8 places (7 resolved)
   series      3 counted -> 3 series, 0 candidates, 0 change points
```

Every stage is idempotent, so a pass over unchanged input costs a directory
listing. `0 selected` is a normal answer: most of any broadcast day is not about
the thing you are looking for. Capture and the passes are independent, so a
model endpoint going away for a minute does not end a run that has been
recording for a week.

### 4. Look at what it found

```bash
cd web && npm install && npm run dev
```

A map with the places on it, the counts over time, and the unusual stretches.
It opens on bundled sample output so there is something to see before your own
run has produced much.

## A word on the streams

NPR publishes that one for listening, and this reads it the way a radio does.
Check the terms of whatever you point it at, and prefer public broadcasters, who
generally intend their output to be heard.

Nothing here is specific to a language. The example uses an English lens, which
is three text files in `lenses/en-radio-disaster/`; the Japanese ones beside it
were written the same way, with no code involved.

## Status

| stage | state |
|---|---|
| capture, transcription, lens, place grounding, series, viewer | working |
| per-event map generation | in the prototype: geographic scoping, response-phase colouring |

## Where things are

| | |
|---|---|
| [docs/COMMANDS.md](docs/COMMANDS.md) | each command on its own, and what its options are for |
| [docs/PREREQUISITES.md](docs/PREREQUISITES.md) | what to install, per stage and per platform |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | the shape of the chain, what it binds, and idempotence |
| [docs/ADR/](docs/ADR/) | why it is like this, and what was rejected |
| [AGENTS.md](AGENTS.md) | the contract, for an agent driving this |
| [lenses/README.md](lenses/README.md) | writing a lens for your own theme |
| [tests/README.md](tests/README.md) | how the tests avoid needing a model |

## License

MIT
