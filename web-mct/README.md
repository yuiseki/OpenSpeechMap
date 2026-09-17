# The console (a spike)

An Open MCT front end for the same two files `web/` reads. It exists to answer
one question — is a mission-control console a better home for this than the
purpose-built viewer? — and `web/` is untouched so the two can be compared.

```bash
npm install
npm run dev      # http://localhost:5174
npm run build    # dist/, static, no server needed
```

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

The map is on top with the height, the chart underneath at its own size,
because the chart stops improving above about 280px and the map never does.

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

**The time conductor is not optional.** Without `UTCTimeSystem` and
`Conductor`, Open MCT boots to a blank page and throws `Unknown clock local.
Has it been registered with 'addClock'?`. This holds even though nothing here
uses the Telemetry API — the conductor is part of the shell. Only a fixed
option is offered and no clock, because the data is a snapshot of a stretch
that has already happened.

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
