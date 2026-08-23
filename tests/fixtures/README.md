# Fixtures

`transcripts.jsonl` is what the tests run against. Thirteen synthetic
transcripts, plus one with empty text.

They are synthetic on purpose, for two reasons. Tests need transcripts that
read like broadcast speech, and shipping recordings of an actual broadcaster in
a public repository is a licensing question this project does not need to have.

## Regenerating

```bash
LLM_URL=http://your-endpoint/v1 tests/fixtures/generate.sh
```

The script asks a language model for one transcript per case. Cases are chosen
to exercise decisions the pipeline makes, not to be representative of
broadcast:

| id | what it is | why it is here |
|---|---|---|
| `d1` | rain warning naming two municipalities | the ordinary success path |
| `d2` | evacuation advisory, place name misheard | a place that must not resolve |
| `d3` | river flood risk, a word misheard | misrecognition away from place names |
| `d4` | earthquake bulletin | a disaster with no forecast phase |
| `d5` | vague regional outlook, no municipality | disaster reporting with nothing to place |
| `n1` | baseball results | place names that are not the subject |
| `n2` | language lesson | not a disaster, no places |
| `n3` | reading listener letters | chat, and the longest record |
| `e1` | fireworks festival traffic notice | the event lens's success path |
| `e2` | a song that mentions fireworks | must be `is_event=false` |
| `e3` | history of Edo-period fireworks | must be `is_event=false` |
| `m1` | back-announcing a track | neither lens should fire |
| `z1` | empty text | must still produce a row |

## Two edits made by hand

The model would not write a misrecognition when asked to. Told to spell 守谷市
as 森谷市, and 氾濫 as 反乱, it corrected both. Those two substitutions were
applied afterwards, deliberately, because a fixture that never contains a
misheard place name cannot test what happens to one, and what happens to one
is a third of the mentions in real material.

If you regenerate, apply them again.
