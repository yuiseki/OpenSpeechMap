# The console (a spike)

An Open MCT front end for the same two files `web/` reads. It exists to answer
one question — is a mission-control console a better home for this than the
purpose-built viewer? — and `web/` is untouched so the two can be compared.

Published at https://yuiseki.github.io/OpenSpeechMap/ by
`.github/workflows/pages.yml` on every push that touches `web-mct/`.

```bash
npm install
npm run dev      # http://localhost:5174
npm run build    # dist/, static, no server needed
```

`base` is `/` locally and `/<repository name>/` in CI, because a GitHub Pages
project site lives under a subdirectory. Anything that builds a URL reads
`import.meta.env.BASE_URL` instead of assuming the root — an absolute
`/openmct/` would send the search worker to the wrong place, and that fails as
search quietly returning nothing rather than as an error.

It reads `public/sample`, a symlink to `web/public/sample`. A second run is a
second entry in `src/sources.js` and nothing else.

## What Open MCT is used for, and what it is not

Open MCT supplies the object tree, the browse bar, the inspector and the theme.
It draws none of the content. Every view here builds its own DOM:

| | |
|---|---|
| `src/views/overview.js` | what the run was, and what came out of it |
| `src/views/situation.js` | a series and the places together, chart driving map |
| `src/views/map.js` | every grounded place, on its own |
| `src/views/series.js` | one series, on its own |

`src/chart.js` and `src/mapview.js` hold the drawing, so the combined view and
the single-pane views are the same code seen twice. Both single-pane views are
kept: a chart with nothing under it can be read at a glance, and a wall display
showing one series wants the height.

### The combined view

`situation.js` is what `web/` does — a chart and a map that agree about which
day you are looking at — rebuilt as one custom view that lays out both panes
itself. Not a Display Layout: sas0 and m3xx-fleet both reached for one, found
it does not agree with objects that come from a provider, and settled on
exactly this shape.

The map is on top with what is going, the chart underneath at `minmax(180px,
30vh)`. A share of the viewport rather than a fixed height, so the chart grows
on a large display instead of leaving everything to the map, and a floor so a
short window does not squeeze it into a smear. `renderChart` takes the height
from its caller for the same reason — a constant there would undo the vh.

The click is wired inside the view rather than through the time conductor.
Moving conductor bounds would be the mission-control idiom, and it would also
mean one click silently changes what every other open view is showing. A day
picked on this chart is a question about this chart.

Not used: the Telemetry API, Plot, Display Layout, PlanLayout,
`nasa/openmct-map`. That is not a shortcut. Five independent Open MCT consoles
in dwg7 reached the same arrangement — tree and chrome from the framework,
pixels from the application — and their notes are worth reading before changing
any of this:

- https://github.com/dwg7/cafebabe/blob/main/patterns/open-mct.md

Open MCT itself is in good health — v4.3.1 in August 2026, commits landing
most weeks. It is the *map plugin*, `nasa/openmct-map`, that is skipped, and
for its own reasons: no commit since December 2022, no licence file, and a
README that says it is not for production. The two are easy to confuse.

## Things that cost time here

**A time system has to be activated, not merely installed.** Without it Open
MCT boots to a blank page and throws `Unknown clock local. Has it been
registered with 'addClock'?`. `openmct.install(UTCTimeSystem())` is not enough
on its own; `openmct.time.setTimeSystem('utc', bounds)` is the part that
matters. sas0 recorded this for Plot (DECISIONS.md), and it turns out to hold
for the shell as well, even with no telemetry anywhere.

Installing `Conductor` also clears the error, and that is the wrong fix: it
buys a bar offering a fixed timespan and a live clock over data that is a
finished snapshot, so every control on it is either inert or a way to hide
rows. sas0 leaves the plugin out for the same reason.

**`setAssetPath` must not point into `node_modules`.** It works in `dev` and
silently breaks in `build`, where `node_modules` is not served. `npm run
copy-openmct` puts the files in `public/openmct/` before either.

**`inMemorySearchWorker.js` shows as pending forever in the network panel.**
It is not stuck. It is a `SharedWorker`, so the request belongs to the worker
context rather than to the page, and the worker outlives the request. Connect
to it and it answers; `curl` returns it in under a millisecond.

## What this costs

| | `web/` | here |
|---|---|---|
| our code | 875 lines | 546 lines |
| bundle | 1.2 MB | 6.4 MB (1.65 MB gzip) |
| deployed | ~1.5 MB | ~35 MB |
| framework | React | Open MCT |

The line count moved because the navigation went away; the bundle moved because
a mission control framework came in. Both numbers are the point of the spike.
