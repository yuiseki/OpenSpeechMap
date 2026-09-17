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

// Open MCT will not start without a time system: it boots to a blank page and
// throws `Unknown clock local. Has it been registered with 'addClock'?`.
// Installing UTCTimeSystem is not enough — it has to be activated as well
// (sas0 DECISIONS.md D…, recorded for Plot, but it holds for the shell too).
//
// No Conductor. The bar it adds offers a fixed timespan and a live clock over
// data that is a finished snapshot, so every control on it is either a no-op
// or a way to hide rows. sas0 leaves it out for the same reason. Bounds are
// set once so anything that asks has an answer.
openmct.install(openmct.plugins.UTCTimeSystem());
openmct.time.setTimeSystem("utc", {
  start: Date.UTC(2026, 5, 27),
  end: Date.UTC(2026, 7, 24),
});

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
