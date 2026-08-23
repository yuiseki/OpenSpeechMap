# Lenses

A lens is what turns "speech" into "the thing you are looking for". It is
text files, not code.

| file | required | what it is |
|---|---|---|
| `schema.json` | yes | JSON Schema for the fields to extract. Sent to the model as `response_format`, so the shape is enforced by the decoder rather than requested politely |
| `instruction.txt` | yes | what to do with each record. The text is appended after it |
| `system.txt` | no | the system prompt |
| `gate.txt` | no | one keyword per line. A record must contain at least one of them to reach the model at all |

Swap the files and the same pipeline looks for something else. No Python is
involved. See [ADR 0002](../docs/ADR/0002-lenses-as-data.md) for why.

## Naming

`<language>-<source>-<theme>`, flat.

- **language** is the ISO 639-1 code of the speech the lens is calibrated for
  (`ja`, not `jp`; `JP` is the country)
- **source** is what kind of speech (`radio`, and later `meeting`, `interview`)
- **theme** is what you are looking for (`disaster`, `event`)

Flat rather than nested by language, because with a handful of lenses one
`ls` should show every lens with its full identity, and `--lens` takes a path
so migrating to `ja/radio-disaster` later would cost nothing.

## `gate.txt`, and when to use one

The language model is the scarce resource in this chain. For a narrow theme
almost every record is irrelevant, and paying a second of inference to learn
that is waste.

`ja-radio-event` has a gate. Festival reporting always contains one of a
recognisable set of words, so 32 keywords cut the model calls to under 2% of
records. In the original PoC that turned a three-hour job into twelve minutes.

`ja-radio-disaster` has no gate, deliberately. Disaster reporting is not
lexically narrow. An evacuation advisory, a river gauge reading and a
cancelled train service share no vocabulary, so a keyword gate would drop
real material. Screening for that lens is done with an embedding classifier
instead, which is cheap enough to run on everything.

Records dropped by a gate are not emitted, so `labeled.jsonl` is shorter than
the input when a gate is in use. The count is reported at the end of the run.
A gate always trades recall for cost: reporting that uses none of your
keywords is invisible. Choose the vocabulary wide.

## `ja-radio-disaster`

Disaster reporting in Japanese public radio. This is the lens with measured
results behind it, so it is the one to copy first.

Fields: `is_disaster` (boolean), `category` (radio programme type), `topic`
(a short summary that must keep place names verbatim).

Two things about it are deliberate.

**`topic` is where place names survive.** Place resolution reads `topic`, not
the full text, so any place name the summary rounds off is lost for good. An
earlier version asked for "about 15 characters" and got regional
generalisations back; place counts for one day went from 11 to 46 once the
instruction said to keep municipality, ward, station, river and road names
exactly as spoken.

**`category` is a radio programme type**, which is meaningless for a personal
recording or a meeting. Delete it in your own lens unless you are processing
broadcast. It is kept here because the published numbers were measured with it
present.

## `ja-radio-event`

Festivals, fireworks displays and other public events. Useful on its own, and
useful as the positive counterpart to disaster reporting: the same machinery
pointed at something people gather for rather than flee.

Fields: `is_event` (boolean), `fest_category` (enum), `place`, `reason`.

**`is_event` is the whole point, and it is a "no" detector.** Broadcast is full
of festivals that are not happening: a song called "Festival", lyrics about
fireworks, a music programme with a summer-festival theme, a simile ("a tune
as cheerful as a festival"), the history of Edo-period fireworks, a listener
writing in about a dance they enjoyed. The instruction enumerates these and
demands `false` for all of them, and demands `false` when unsure. Only actual
reporting of an event, meaning dates, venue, scale, traffic restrictions or
cancellation, is `true`.

On twelve records containing festival vocabulary, three came back `true`: two
reporting traffic restrictions for the Nagaoka fireworks festival, one on
post-event congestion. The nine `false` ones were song introductions,
historical explanation and chat. That ratio is the normal shape of the
problem.

Note `fest_category` rather than `event_category`. The name is kept as it was
in the PoC so that the prompt fingerprint, and therefore the provenance of
records produced by it, stays continuous. See
[ADR 0007](../docs/ADR/0007-provenance-on-every-record.md).

## Writing your own

Copy a directory and edit the text. The one rule that matters: whichever field
you point `--place-field` at is the *only* text the place resolver sees. If
your instruction lets the model summarise a place name away, that place is
gone.

Both lenses here spell the output schema out in prose inside
`instruction.txt`, which is now redundant since the schema is sent as
`response_format`. It is left in place because removing it would change the
prompt fingerprint. In a new lens, leave it out.
