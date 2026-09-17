# Prerequisites

Nothing here is bundled. Each stage drives programs and services that exist on
their own, so what you need depends on which stages you use.

Ask before you start:

```bash
speechmap check
```

It reports, stage by stage, where each program was found or what to install. A
missing optional program narrows what you can do; a missing required one is an
error.

## What each stage needs

| stage | command | programs | services |
|---|---|---|---|
| capture from a stream | `speechmap record --source http` | ffmpeg | none |
| capture off the air | `speechmap record --source sdr` | ffmpeg, **rtl_fm**, and a dongle | none |
| audio to transcripts | `speechmap transcribe` | ffmpeg, ffprobe, curl | a whisper.cpp server |
| lens and place grounding | `speechmap` | jq, [aiq](https://github.com/yuiseki/aiq) (the fork) | an OpenAI-compatible LLM endpoint, [locitorium](https://github.com/yuiseki/locitorium) and its Nominatim |
| counting over time | `speechmap series` | jq, [detempus](https://github.com/yuiseki/detempus) | none |
| the viewer | `cd web && npm run dev` | node, npm | none, beyond map tiles |

You can stop anywhere. If you already have transcripts, skip the first two rows
and nothing else changes. If you only want counts over time, the third row is
not needed either.

## Installing the programs

### Debian and Ubuntu

```bash
sudo apt install ffmpeg jq curl
sudo apt install rtl-sdr          # only for --source sdr; provides rtl_fm
```

Verified on Ubuntu 24.04, x86_64, Python 3.12.

### macOS

```bash
brew install ffmpeg jq curl
brew install librtlsdr            # only for --source sdr; provides rtl_fm
```

Not verified. Two things to expect. The dongle needs the kernel driver claimed
away from macOS, which `librtlsdr` normally handles but sometimes does not, and
`rtl_fm`'s gain values are hardware-dependent, so `--gain` may need a different
number. The rest of the chain is ffmpeg and HTTP and should behave.

### The Python package

```bash
uv venv && uv pip install -e .
```

`typer` is the only Python dependency, because everything else is driven as a
subprocess rather than imported. See
[ADR 0012](ADR/0012-python-for-the-cli.md).

None of the three components is on PyPI yet.

`detempus` is a library and a small command, so it goes into this environment
straight from git:

```bash
uv pip install 'detempus[all] @ git+https://github.com/yuiseki/detempus'
```

`aiq` and `locitorium` each need an environment of their own, so clone them and
point an environment variable at the checkout. Run this from the root of your
OpenSpeechMap checkout; `.tools/` is gitignored, so the clones stay out of
`git status` and `rm -rf .tools` undoes them:

```bash
git clone https://github.com/yuiseki/aiq        .tools/aiq
git clone https://github.com/yuiseki/locitorium .tools/locitorium
export AIQ="$PWD/.tools/aiq" LOCITORIUM="$PWD/.tools/locitorium"
```

`.tools/` is only a default that makes the command safe to paste. Any absolute
path works, so if you already keep these two somewhere, skip the clones and
point the variables there instead. Nothing reads `.tools/` by name.

The variables have to be set in the shell that runs `speechmap`, not just the
one that ran the clones, so put them somewhere durable.

`DETEMPUS` works the same way if you would rather run detempus from a checkout
too, which is what you want if you might change it.

`speechmap` looks for each on PATH first and falls back to the checkout named by
`AIQ`, `LOCITORIUM` or `DETEMPUS`. That fallback is what you want while working
on one of them: the interesting version is the working tree, not the release.

`aiq` is a fork of [taylorai/aiq](https://github.com/taylorai/aiq) (MIT).
Note that `aiq extract` exists only in that fork, not in upstream `aiq-cli`.

## The services

### An OpenAI-compatible LLM endpoint

Anything that answers `POST /v1/chat/completions` and honours
`response_format: json_schema`. The reference setup is
[llama.cpp](https://github.com/ggml-org/llama.cpp)'s `llama-server`, which does.

```bash
llama-server -m model.gguf --host 0.0.0.0 --port 8080
speechmap ... --llm-url http://127.0.0.1:8080/v1 --model your-model-alias
```

`curl -s "$LLM_URL/models"` lists the names you may pass to `--model`.

If your endpoint cannot do `response_format`, the lens stage will fail. `aiq
extract` has a `--response-format prompt` mode for that case, but `speechmap`
does not pass it through yet.

### A whisper.cpp server

```bash
whisper-server -m ggml-medium.bin --host 0.0.0.0 --port 8080
speechmap transcribe ... --whisper-url http://127.0.0.1:8080/inference
```

Any server accepting a multipart `file` field and answering with
`{"text": "..."}` works. Model choice matters more than you might expect:
`medium` is where Japanese becomes usable, and smaller models mangle proper
nouns, which is exactly what the rest of the pipeline needs from the
transcript.

### locitorium, and Nominatim behind it

[locitorium](https://github.com/yuiseki/locitorium) resolves place names to OSM
entities. It needs a Nominatim instance and an LLM endpoint of its own; see its
README. Check it with:

```bash
curl -s -o /dev/null -w '%{http_code}\n' "$LOCI_URL/"     # 200
```

There is no `/health`. `/` and `/docs` both answer.

Nothing in this repository sends anything to a third-party API. The reference
setup is entirely local, which is the point: the material is public broadcast,
but what you conclude from it does not have to leave your machine.

## Hardware, for `--source sdr`

An RTL2832U-based USB dongle. Verified with a DS-DT310BK, which pairs RTL2832U
with an FC0013 tuner.

Three things worth knowing before ordering one.

The dongle is held exclusively while recording. `rtl_test`, `rtl_power` and
scanning other stations all need the recording stopped, or a second dongle.

Tuner sensitivity differs. FC0013 tops out at 19.7 dB of gain and is less
sensitive than the more common R820T2. Strong stations are fine; weak ones need
a better aerial.

`rtl_fm`'s log says `Output at 170000 Hz`. That is an intermediate
demodulation rate, not what comes out of the pipe; the audio is 32 kHz, which
is why the ffmpeg command says so. Believing the log produces audio at the wrong
speed and a transcript of nonsense.
