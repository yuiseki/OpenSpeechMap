# The bundled sample

Real output, from Japanese public radio between 2026-06-27 and 2026-08-23.

| file | how it was made |
|---|---|
| `series.json` | `speechmap series` over 58 days of labeled records (15,625 of them, 418 with `is_disaster`) |
| `places.geojson` | `speechmap` over 85 transcripts, chosen as described below. 216 mentions, 135 of them with coordinates |

## Why the places are a subset, and how they were chosen

Resolving places costs a model call and a geocoder lookup each, so the sample
does not carry every place from 58 days. It carries the days that produced a
candidate or a change point, and for each of those days, the transcripts from
the **two hours that carried the most disaster reporting**.

That last part matters, and getting it wrong is instructive. The first version
of this sample took the first ten disaster records of each day, in clock order.
For 2026-07-28 that gave France, Spain, Russia, North Korea and a city in
Shandong: early-morning international news, hours before the earthquake at
16:28. The map showed disasters happening across the whole world on a day when
one happened in Kumamoto.

An anomalous day is anomalous because of something that happened at a
particular time in a particular place. Sampling it uniformly across the day
averages that away. Picking the hours that carry the reporting keeps it: all 22
places for 2026-07-28 are now in Kyushu, clustered on Kumamoto.

Places from other days are still spread across the world, because some of them
genuinely are: a Japanese bulletin covering the Kumamoto earthquake also
covered one in Colombia. The viewer draws all of them and points the camera at
the densest cluster rather than at everything.

## What you should see

Two of the seven series have anything in them: `ニュース` and `気象`, five
candidates and two change points each. The rest are categories that rarely
carry disaster reporting at all, and they are in the list to show what an empty
answer looks like.

- `ニュース` peaks on 2026-07-28 with a score of 15.28. An earthquake struck
  Kumamoto at 16:28 that day.
- `気象` peaks on 2026-08-13 with 11.04. Floods in Chiba.

`method.seasonal` reads `phase` for the longer series, so `profile` carries the
weekday pattern. Fifty-eight days is 8.3 weeks, which is just past the eight
cycles detempus wants before it will claim a periodic component.

## Regenerating

Both commands are in the repository; the record selection above is not, because
it is specific to this dataset. If you are making your own sample, run both
commands over the same input and the two files will agree exactly, which this
one does not: the series counts all 418 disaster records while the places come
from 85 transcripts.
