# Architecture Decision Records

Why OpenSpeechMap is built the way it is, and what was turned down.

The records themselves are written in Japanese. The titles below say what each
one decided, so you can tell whether a given record is worth translating.

| # | Decision | Status |
|---|---|---|
| [0001](0001-agent-driven-not-gui.md) | Designed to be driven by an agent; no GUI | Accepted (2026-08-23) |
| [0002](0002-lenses-as-data.md) | A lens is data, not code | Accepted (2026-08-23) |
| [0003](0003-bind-existing-oss.md) | Bind existing OSS; build only the gaps | Accepted (2026-08-23) |
| [0004](0004-input-is-timestamped-text.md) | The input surface is timestamped text, not audio | Accepted (2026-08-23) |
| [0005](0005-place-identity-by-osm-id.md) | Place identity by osm_id, with no normalisation dictionary | Accepted (2026-08-23) |
| [0006](0006-candidates-not-verdicts.md) | Return candidates, not verdicts; the threshold lives outside the tool | Accepted (2026-08-23) |
| [0007](0007-provenance-on-every-record.md) | Every record carries its provenance | Accepted (2026-08-23) |
| [0008](0008-geographic-scoping.md) | Aggregate within a geographic scope | Accepted (2026-08-23) |
| [0009](0009-accepting-the-osm-acronym.md) | Accept that the acronym collides with OSM | Accepted (2026-08-23) |
| [0010](0010-series-is-a-separate-command.md) | Series is its own command; places carry a time | Accepted (2026-08-23) |
| [0011](0011-viewer-is-vite-react-typescript.md) | The viewer is Vite + React + TypeScript | Accepted (2026-08-23) |
| [0012](0012-python-for-the-cli.md) | The CLI is Python and stays a thin wrapper around other programs | Accepted (2026-08-23) |
| [0013](0013-capture-belongs-here.md) | Continuous capture belongs in this repository | Accepted (2026-08-23) |
| [0014](0014-transcription-belongs-here.md) | Transcription belongs here, and how a recording's time is decided | Accepted (2026-08-23) |
| [0015](0015-idempotent-stages-and-a-declaration.md) | Stages are idempotent; composition is declared in speechmap.yaml | Accepted (2026-08-23) |

## Before this repository

This was extracted from a proof of concept. Decisions taken before the
extraction, particularly about recording, ASR, GPU allocation and working in
more than one language, are recorded on the PoC side. What is here is only what
the binding layer inherited.
