import { SOURCES } from "./sources.js";
import { get } from "./data.js";

/** The tree.
 *
 * `objects.addProvider` + `composition.addProvider` is the only extension
 * point that three independent Open MCT consoles in dwg7 agreed on, so the
 * whole structure is defined here in code and nothing is created through the
 * GUI. Objects are non-persistent: they exist because this provider answers
 * for them, not because anything was saved.
 *
 * Every type is registered with `creatable: false` and carries exactly one
 * view. Using the built-in `folder` type would leave Grid View sitting in the
 * view switcher next to ours, which reads as a choice the operator does not
 * actually have.
 */
export const NAMESPACE = "speechmap";

const ROOT = { namespace: NAMESPACE, key: "root" };

export function installTree(openmct) {
  openmct.types.addType("osm.root", {
    name: "OpenSpeechMap", cssClass: "icon-folders", creatable: false,
  });
  openmct.types.addType("osm.source", {
    name: "Run", cssClass: "icon-database", creatable: false,
  });
  openmct.types.addType("osm.places", {
    name: "Places", cssClass: "icon-map", creatable: false,
  });
  openmct.types.addType("osm.series", {
    name: "Counts", cssClass: "icon-telemetry", creatable: false,
  });

  openmct.objects.addRoot(ROOT);

  openmct.objects.addProvider(NAMESPACE, {
    get(identifier) {
      return Promise.resolve(build(identifier));
    },
  });

  openmct.composition.addProvider({
    appliesTo: (domainObject) =>
      domainObject.identifier.namespace === NAMESPACE &&
      ["osm.root", "osm.source"].includes(domainObject.type),
    load: (domainObject) => children(domainObject),
  });
}

/** One provider, several roles, keyed off the identifier. The alternative is
 * a provider per type, which would mean a namespace per type; the tree is
 * small enough that one namespace reads better. */
function build(identifier) {
  const { key } = identifier;
  if (key === "root") {
    return { identifier, type: "osm.root", name: "OpenSpeechMap", location: null };
  }
  const [kind, sourceKey, rest] = key.split(":");
  const source = SOURCES.find((s) => s.key === sourceKey);
  if (!source) return undefined;

  if (kind === "src") {
    return {
      identifier, type: "osm.source", name: source.name,
      location: `${NAMESPACE}:root`, osm: { source },
    };
  }
  if (kind === "places") {
    return {
      identifier, type: "osm.places", name: "Places",
      location: `${NAMESPACE}:src:${sourceKey}`, osm: { source },
    };
  }
  if (kind === "series") {
    return {
      identifier, type: "osm.series", name: rest,
      location: `${NAMESPACE}:src:${sourceKey}`,
      osm: { source, seriesKey: rest },
    };
  }
  return undefined;
}

async function children(domainObject) {
  if (domainObject.type === "osm.root") {
    return SOURCES.map((s) => ({ namespace: NAMESPACE, key: `src:${s.key}` }));
  }
  const source = domainObject.osm.source;
  const { series } = await get(source);
  // Places first: the map is what an operator opens the run to see. Then the
  // series, largest first, because a series with three points is noise next to
  // one with fifty-eight.
  return [
    { namespace: NAMESPACE, key: `places:${source.key}` },
    ...[...series.series]
      .sort((a, b) => b.n - a.n)
      .map((s) => ({ namespace: NAMESPACE, key: `series:${source.key}:${s.key}` })),
  ];
}
