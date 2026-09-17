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
| `src/views/map.js` | MapLibre, as in `web/` |
| `src/views/series.js` | hand-drawn SVG, as in `web/` |

Not used: the Telemetry API, Plot, Display Layout, PlanLayout,
`nasa/openmct-map`. That is not a shortcut. Five independent Open MCT consoles
in dwg7 reached the same arrangement — tree and chrome from the framework,
pixels from the application — and their notes are worth reading before changing
any of this:

- https://github.com/dwg7/cafebabe/blob/main/patterns/open-mct.md

`nasa/openmct-map` is skipped for its own reasons: no commit since 2022, no
licence file, and a README that says it is not for production.

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
