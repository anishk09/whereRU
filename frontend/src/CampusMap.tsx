import { useEffect, useMemo, useRef, useState } from "react";
import { AttributionControl, Map as MapLibre, NavigationControl, Popup, setWorkerUrl, type GeoJSONSource, type Map as MapLibreMap } from "maplibre-gl";
import mapWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import "maplibre-gl/dist/maplibre-gl.css";
import { toListingFeatureCollection, type ListingProperties, type MapListing } from "./mapData";

export const campusViews = {
  "College Ave": { center: [-74.4518, 40.5020] as [number, number], zoom: 15.5 },
  Busch: { center: [-74.4600, 40.5225] as [number, number], zoom: 15 },
  Livingston: { center: [-74.4370, 40.5235] as [number, number], zoom: 15.5 },
  "Cook/Douglass": { center: [-74.4360, 40.4835] as [number, number], zoom: 15 },
};

export type CampusName = keyof typeof campusViews;

type CampusMapProps = {
  campus: CampusName;
  dark: boolean;
  listings: MapListing[];
  onVisibleListingsChange?: (listings: ListingProperties[]) => void;
  onSelectReport: (id: string) => void;
};

const lightStyle = "https://tiles.openfreemap.org/styles/positron";
const darkStyle = "https://tiles.openfreemap.org/styles/dark";

setWorkerUrl(mapWorkerUrl);

function addListingLayers(map: MapLibreMap, data: ReturnType<typeof toListingFeatureCollection>) {
  if (map.getSource("listings")) return;

  map.addSource("listings", {
    type: "geojson",
    data,
  });

  map.addLayer({
    id: "listing-heat",
    type: "heatmap",
    source: "listings",
    maxzoom: 18,
    paint: {
      "heatmap-weight": ["get", "weight"],
      "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 13, 0.7, 16, 1.6],
      "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 13, 18, 16, 34],
      "heatmap-color": [
        "interpolate",
        ["linear"],
        ["heatmap-density"],
        0, "rgba(255,255,255,0)",
        0.25, "rgba(255,229,128,0.62)",
        0.55, "rgba(244,132,40,0.78)",
        1, "#CC0033",
      ],
      "heatmap-opacity": ["interpolate", ["linear"], ["zoom"], 16, 1, 17, 0],
    },
  });

  map.addLayer({
    id: "listing-points",
    type: "circle",
    source: "listings",
    minzoom: 16,
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 16, 5, 18, 8],
      "circle-color": ["match", ["get", "type"], "lost", "#CC0033", "#34363A"],
      "circle-stroke-color": "#FFFFFF",
      "circle-stroke-width": 2,
    },
  });
}

function visibleListings(map: MapLibreMap, data: ReturnType<typeof toListingFeatureCollection>) {
  const bounds = map.getBounds();
  return data.features
    .filter((feature) => bounds.contains(feature.geometry.coordinates as [number, number]))
    .map((feature) => feature.properties)
    .sort((a, b) => b.weight - a.weight || a.hoursAgo - b.hoursAgo);
}

export default function CampusMap({ campus, dark, listings, onVisibleListingsChange, onSelectReport }: CampusMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const callbackRef = useRef(onVisibleListingsChange);
  const selectRef = useRef(onSelectReport);
  const darkRef = useRef(dark);
  const styleReadyRef = useRef(false);
  const [mapUnavailable, setMapUnavailable] = useState(false);
  const listingData = useMemo(() => toListingFeatureCollection(listings), [listings]);
  const listingDataRef = useRef(listingData);

  useEffect(() => {
    callbackRef.current = onVisibleListingsChange;
  }, [onVisibleListingsChange]);

  useEffect(() => {
    selectRef.current = onSelectReport;
  }, [onSelectReport]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const initialView = campusViews[campus];
    const map = new MapLibre({
      container: containerRef.current,
      style: dark ? darkStyle : lightStyle,
      center: initialView.center,
      zoom: initialView.zoom,
      dragRotate: false,
      pitchWithRotate: false,
      attributionControl: false,
    });
    mapRef.current = map;
    map.touchZoomRotate.disableRotation();
    map.setMissingStyleImageResolver((id) => {
      if (!map.hasImage(id)) {
        map.addImage(id, { width: 1, height: 1, data: new Uint8Array([0, 0, 0, 0]) });
      }
    });
    map.addControl(new NavigationControl({ showCompass: false, visualizePitch: false }), "top-right");
    map.addControl(new AttributionControl({ compact: true }), "bottom-right");

    const updateVisibleListings = () => {
      callbackRef.current?.(visibleListings(map, listingDataRef.current));
    };

    map.on("load", updateVisibleListings);
    map.on("style.load", () => {
      styleReadyRef.current = true;
      setMapUnavailable(false);
      addListingLayers(map, listingDataRef.current);
      updateVisibleListings();
    });
    map.on("moveend", updateVisibleListings);
    map.on("error", () => {
      if (!styleReadyRef.current) setMapUnavailable(true);
    });
    map.on("click", "listing-points", (event) => {
      const feature = event.features?.[0];
      if (!feature?.properties) return;
      const properties = feature.properties as ListingProperties;
      const coordinates = feature.geometry.type === "Point" ? feature.geometry.coordinates.slice() as [number, number] : event.lngLat.toArray();
      const placeType = properties.placeType.replace("_", " ");
      const popupContent = document.createElement("div");
      const title = document.createElement("strong");
      const details = document.createElement("span");
      title.textContent = properties.title;
      details.textContent = `${placeType} · ${properties.hoursAgo < 1 ? "in the last hour" : `${properties.hoursAgo}h ago`}`;
      popupContent.append(title, details);
      new Popup({ closeButton: false, offset: 10 })
        .setLngLat(coordinates)
        .setDOMContent(popupContent)
        .addTo(map);
      selectRef.current(properties.id);
    });
    map.on("mouseenter", "listing-points", () => {
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "listing-points", () => {
      map.getCanvas().style.cursor = "";
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    listingDataRef.current = listingData;
    const map = mapRef.current;
    const source = map?.getSource("listings") as GeoJSONSource | undefined;
    source?.setData(listingData);
    if (!map) return;
    callbackRef.current?.(visibleListings(map, listingData));
  }, [listingData]);

  useEffect(() => {
    const map = mapRef.current;
    const view = campusViews[campus];
    if (!map) return;
    map.flyTo({ center: view.center, zoom: view.zoom, essential: true });
    map.once("moveend", () => callbackRef.current?.(visibleListings(map, listingDataRef.current)));
  }, [campus]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || darkRef.current === dark) return;
    darkRef.current = dark;
    styleReadyRef.current = false;
    map.setStyle(dark ? darkStyle : lightStyle);
  }, [dark]);

  return <div className="map-shell">
    {mapUnavailable && <div className="map-unavailable" role="status"><strong>Map unavailable</strong><span>The nearby listing summary is still available below.</span></div>}
    <div ref={containerRef} className={`heat-map real-map ${mapUnavailable ? "is-unavailable" : ""}`} aria-label={`${campus} lost item heat map`} />
    {!mapUnavailable && <div className="map-legend"><span><i className="low" /> Low</span><span><i className="mid" /></span><span><i className="high" /> High activity</span></div>}
  </div>;
}
