export type PlaceType = "classroom" | "building" | "library" | "dining" | "bus_stop" | "outdoor";

export type ListingProperties = {
  id: string;
  title: string;
  type: "lost" | "found";
  status: "active" | "returned";
  placeType: PlaceType;
  hoursAgo: number;
  weight: number;
};

export type MapListing = ListingProperties & {
  coordinates: [number, number];
};

export type ListingFeatureCollection = {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    geometry: { type: "Point"; coordinates: [number, number] };
    properties: ListingProperties;
  }>;
};

type SeedLocation = {
  campus: "College Ave" | "Busch" | "Livingston" | "Cook/Douglass";
  name: string;
  coordinates: [number, number];
  placeType: PlaceType;
};

const locations: SeedLocation[] = [
  { campus: "College Ave", name: "College Ave Student Center", coordinates: [-74.4518, 40.5034], placeType: "building" },
  { campus: "College Ave", name: "Alexander Library", coordinates: [-74.4522, 40.5045], placeType: "library" },
  { campus: "College Ave", name: "Hardenbergh Hall", coordinates: [-74.4486, 40.5008], placeType: "classroom" },
  { campus: "College Ave", name: "Scott Hall bus stop", coordinates: [-74.4490, 40.4998], placeType: "bus_stop" },
  { campus: "Busch", name: "Busch Student Center", coordinates: [-74.4584, 40.5235], placeType: "building" },
  { campus: "Busch", name: "Hill Center", coordinates: [-74.4637, 40.5219], placeType: "classroom" },
  { campus: "Livingston", name: "Livingston Student Center", coordinates: [-74.4369, 40.5241], placeType: "dining" },
  { campus: "Cook/Douglass", name: "Cook Campus Center", coordinates: [-74.4364, 40.4813], placeType: "building" },
  { campus: "Cook/Douglass", name: "Douglass Student Center", coordinates: [-74.4370, 40.4855], placeType: "outdoor" },
];

export const campusPlaces = locations;

export function toListingFeatureCollection(listings: MapListing[]): ListingFeatureCollection {
  return {
    type: "FeatureCollection",
    features: listings.map(({ coordinates, ...properties }) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates },
      properties,
    })),
  };
}
