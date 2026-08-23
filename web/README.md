# Viewer

A map, a time series, and the list of unusual stretches, over output that
`speechmap` and `speechmap series` produced. Vite, React and TypeScript.

```bash
npm install
npm run dev
```

It opens on the sample data in `public/sample/`, which is real output from
Japanese public radio over July and August 2026.

Two things about that sample are worth knowing, because both are visible in the
panel and would otherwise look like faults.

`method.seasonal` reads `none` and `profile` is empty. The series is 26 daily
buckets against a weekly period, so the cycle has come round fewer than four
times, and detempus does not claim a periodic component it cannot estimate. Run
`speechmap series --bucket hour` over a few weeks of hourly data and the
profile fills in with the broadcaster's actual schedule.

Some candidates are labelled "no places". The sample `places.geojson` covers
the eight days that carry candidates, with a handful of records each, while
`series.json` was counted over all 36,480 records. Point the viewer at output
from a single run of both commands and the two agree.

## Pointing it at your own output

Two files, both written by the CLI:

| file | written by | what the viewer uses it for |
|---|---|---|
| `series.json` | `speechmap series` | the chart, the candidate list, and the method block |
| `places.geojson` | `speechmap` | the markers |

Copy them into `public/`, or set the URLs and leave them where they are:

```bash
cp .env.example .env
# VITE_SERIES_URL=/absolute-or-relative/series.json
# VITE_PLACES_URL=/absolute-or-relative/places.geojson
```

The viewer joins the two by time. `speechmap` copies the time of each record
onto every place it resolved from it, so clicking a candidate can filter the
markers without the browser having to load `labeled.jsonl` and do the join
itself.

## The basemap

`VITE_MAP_STYLE` defaults to MapLibre's demo style, which needs no account and
is enough to look at your own output. It is a world political map, so it is
not much use as a basemap for anything you intend to show other people. Point
it at your own tiles for that.

## What it deliberately does not do

**It does not decide anything.** The candidate list is detempus's output cut at
its threshold, and the threshold it used is displayed alongside. A score exists
for every point, so a shorter or longer list is a re-run away, not a
disagreement with the tool.

**It draws only places that resolved.** A misheard place name has no
coordinates and no marker, rather than a marker somewhere plausible and wrong.
The counts in the panel still include it.

**A candidate is a band, not a dot.** A dot is a few pixels of a colour you
have to go looking for. The chart exists to point at the unusual stretches, so
they get the full height of it. Change points are drawn differently again, in
their own colour, with the mean either side of them: a spike and a shift in
level are different answers and should not look alike.

**The camera goes to the biggest cluster, not to everything.** All the markers
are drawn, but the view fits the densest group of places. On a day with an
earthquake in Kumamoto there is usually also foreign disaster news in the same
bulletin, and fitting the bounds to all of it zooms out until the thing that
made the day unusual is three pixels wide. Greedy single-linkage at three
degrees, ties going to the tighter cluster.

**It keeps the markers out from under the overlays.** `fitBounds` padding is
measured from the panel and the chart with `getBoundingClientRect`, not
hard-coded: the panel's height depends on how many candidates there are, and a
uniform padding puts half the markers behind it. The padding is clamped to a
third of the map on each axis, because MapLibre throws if it leaves no room.

**It survives without WebGL.** Virtual desktops, remote sessions and
containers without a GPU are common, and the chart and the candidate list do
not need one. If the map cannot start, it says so and the rest keeps working.
