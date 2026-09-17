import { get, placesAt } from "../data.js";
import { createMap } from "../mapview.js";

/** Every place the run grounded, on one map. */
export function mapView() {
  return {
    key: "osm.places",
    name: "Places",
    cssClass: "icon-map",
    canView: (domainObject) => domainObject.type === "osm.places",
    view: (domainObject) => {
      let map = null;
      let holder = null;
      return {
        show(element) {
          holder = document.createElement("div");
          holder.className = "osm-map";
          element.appendChild(holder);
          map = createMap(holder);
          get(domainObject.osm.source).then(({ places }) => {
            map.setFeatures(placesAt(places, null), { fit: true });
          });
        },
        destroy() {
          if (map) map.destroy();
          map = null;
          holder = null;
        },
      };
    },
  };
}
