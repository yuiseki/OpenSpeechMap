/** What the console shows.
 *
 * One entry per run: a lens applied to a stream over some stretch of time.
 * Both files come out of the CLI unchanged, so a second run is a second entry
 * here and nothing else. That is the point of the tree — the cost of adding a
 * source should be one leaf, not a change of structure.
 */
export const SOURCES = [
  {
    key: "sample",
    name: "Japanese public radio",
    lens: "ja-radio-disaster",
    note: "2026-06-27 to 2026-08-23, 58 days",
    series: "sample/series.json",
    places: "sample/places.geojson",
  },
];
