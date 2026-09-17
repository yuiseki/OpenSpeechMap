/** Fetch each source once and keep it. The files are static snapshots that
 * change when the CLI runs again, not a stream, so there is nothing to
 * subscribe to. This is why the console does not use Open MCT's Telemetry
 * API at all — see web-mct/README.md. */
const cache = new Map();

async function load(source) {
  // Resolved against BASE_URL so the same config works at the root and under
  // a project-site subdirectory.
  const at = (p) => new URL(p, new URL(import.meta.env.BASE_URL, location.href)).href;
  const [series, places] = await Promise.all([
    fetch(at(source.series)).then((r) => r.json()),
    fetch(at(source.places)).then((r) => r.json()),
  ]);
  return { series, places };
}

export function get(source) {
  if (!cache.has(source.key)) cache.set(source.key, load(source));
  return cache.get(source.key);
}

/** Places for one bucket, or all of them when `t` is null. A place with no
 * geometry is kept here and dropped by the map, so the counts still include
 * a mention that could not be grounded. */
export function placesAt(places, t) {
  const all = places.features.filter((f) => f.properties.status === "resolved");
  if (t === null) return all;
  return all.filter((f) => (f.properties.t || "").slice(0, 10) === t.slice(0, 10));
}
