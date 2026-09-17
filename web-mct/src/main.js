import openmct from "openmct";
import "./style.css";
import { installTree } from "./tree.js";
import { mapView } from "./views/map.js";
import { seriesView } from "./views/series.js";
import { situationView } from "./views/situation.js";
import { overviewView } from "./views/overview.js";

// Open MCT loads worker scripts and themes as files at runtime, not through
// the bundler. Without this, the search indexer's worker request falls through
// to the SPA fallback, gets HTML back, and fails with `Unexpected token '<'`.
// It has to come before install(); see cafebabe patterns/open-mct-operations.md.
//
// The path is `public/openmct/`, which `npm run copy-openmct` fills from
// node_modules before dev and before build. Pointing at node_modules directly
// works in dev and silently breaks in the built output, where node_modules is
// not served — the same failure, one deploy later.
openmct.setAssetPath("/openmct/");

openmct.install(openmct.plugins.LocalStorage());
openmct.install(openmct.plugins.Espresso());
openmct.install(openmct.plugins.MyItems());

// Without these two, Open MCT boots to a blank page and throws
// `Unknown clock local. Has it been registered with 'addClock'?` — the time
// conductor is part of the shell, not an optional extra, and it refuses to
// start without a time system and a valid menu option.
//
// Only a fixed option is offered, and no clock. The data is a snapshot of a
// stretch that has already happened; a realtime clock would offer the operator
// a mode in which nothing ever arrives.
openmct.install(openmct.plugins.UTCTimeSystem());
openmct.install(
  openmct.plugins.Conductor({
    menuOptions: [
      {
        name: "Fixed",
        timeSystem: "utc",
        bounds: {
          start: Date.UTC(2026, 5, 27),
          end: Date.UTC(2026, 7, 24),
        },
      },
    ],
  }),
);

openmct.objectViews.addProvider(overviewView());
openmct.objectViews.addProvider(mapView());
// Both apply to a series. The combined one claims the higher priority, so
// opening a series lands on the chart with the map under it; the chart on its
// own stays in the view switcher.
openmct.objectViews.addProvider(situationView());
openmct.objectViews.addProvider(seriesView());

installTree(openmct);

// `openmct.on('start', ...)` fires reliably in some setups and never in
// others, with the cause still unidentified across the dwg7 consoles. Nothing
// here depends on it: the tree is installed before start() and the views are
// registered with it.
openmct.start(document.getElementById("app"));
