import type { Feature, FeatureCollection, Point } from "geojson";

export type PlaceType = "classroom" | "building" | "library" | "dining" | "bus_stop" | "outdoor";

export type ListingProperties = {
  id: string;
  title: string;
  type: "lost" | "found";
  placeType: PlaceType;
  hoursAgo: number;
  weight: number;
};

type SeedLocation = {
  name: string;
  coordinates: [number, number];
  placeType: PlaceType;
  count: number;
};

const locations: SeedLocation[] = [
  { name: "College Ave Student Center", coordinates: [-74.4518, 40.5034], placeType: "building", count: 5 },
  { name: "Alexander Library", coordinates: [-74.4522, 40.5045], placeType: "library", count: 5 },
  { name: "Hardenbergh Hall", coordinates: [-74.4486, 40.5008], placeType: "classroom", count: 5 },
  { name: "Scott Hall bus stop", coordinates: [-74.4490, 40.4998], placeType: "bus_stop", count: 4 },
  { name: "Busch Student Center", coordinates: [-74.4584, 40.5235], placeType: "building", count: 5 },
  { name: "Hill Center", coordinates: [-74.4637, 40.5219], placeType: "classroom", count: 4 },
  { name: "Livingston Student Center", coordinates: [-74.4369, 40.5241], placeType: "dining", count: 5 },
  { name: "Cook Campus Center", coordinates: [-74.4364, 40.4813], placeType: "building", count: 4 },
  { name: "Douglass Student Center", coordinates: [-74.4370, 40.4855], placeType: "outdoor", count: 4 },
];

export const campusPlaces = locations.map(({ name, coordinates, placeType }) => ({ name, coordinates, placeType })).map(p=>p.name==="Hardenbergh Hall"?{...p,coordinates:[-74.44997,40.50490] as [number,number]}:p);
campusPlaces.push(
 {name:"Richard Weeks Hall",coordinates:[-74.459505,40.524464],placeType:"building"},
 {name:"Academic Building West",coordinates:[-74.4480,40.5021],placeType:"classroom"},
 {name:"Academic Building East",coordinates:[-74.4480,40.5021],placeType:"classroom"},
 {name:"Allison Road Classroom",coordinates:[-74.4648,40.5239],placeType:"classroom"},
 {name:"Beck Hall",coordinates:[-74.4397,40.5230],placeType:"classroom"},
 {name:"Tillett Hall",coordinates:[-74.4355,40.5226],placeType:"classroom"},
 {name:"Cook/Douglass Lecture Hall",coordinates:[-74.4363,40.4801],placeType:"classroom"},
 {name:"Wright Labs",coordinates:[-74.4631,40.5238],placeType:"classroom"}
);

const itemNames = ["Water bottle", "AirPods case", "Calculator", "Hoodie", "Notebook", "Umbrella", "Keys", "Laptop sleeve"];
const ageSamples = [2, 5, 9, 18, 28, 46, 68, 84, 120];
const placeWeights: Record<PlaceType, number> = {
  classroom: 1,
  building: 0.8,
  library: 0.8,
  dining: 0.8,
  bus_stop: 0.4,
  outdoor: 0.3,
};

function seededRandom(seed: number) {
  let value = seed >>> 0;
  return () => {
    value = (value * 1664525 + 1013904223) >>> 0;
    return value / 4294967296;
  };
}

function timeWeight(hoursAgo: number) {
  if (hoursAgo < 24) return 1;
  if (hoursAgo < 72) return 0.6;
  return 0.3;
}

const random = seededRandom(198111);
let listingIndex = 0;

// Sample data. Replace with listings from the API.
const features: Array<Feature<Point, ListingProperties>> = locations.flatMap((location) =>
  Array.from({ length: location.count }, () => {
    const angle = random() * Math.PI * 2;
    const distanceMeters = Math.sqrt(random()) * 40;
    const latitudeOffset = Math.sin(angle) * distanceMeters / 111320;
    const longitudeOffset = Math.cos(angle) * distanceMeters / (111320 * Math.cos(location.coordinates[1] * Math.PI / 180));
    const hoursAgo = ageSamples[Math.floor(random() * ageSamples.length)];
    const type = random() > 0.48 ? "lost" : "found";
    const item = itemNames[Math.floor(random() * itemNames.length)];
    listingIndex += 1;

    return {
      type: "Feature",
      geometry: {
        type: "Point",
        coordinates: [location.coordinates[0] + longitudeOffset, location.coordinates[1] + latitudeOffset],
      },
      properties: {
        id: `sample-${listingIndex}`,
        title: `${type === "lost" ? "Lost" : "Found"} ${item}`,
        type,
        placeType: location.placeType,
        hoursAgo,
        weight: Number((placeWeights[location.placeType] * timeWeight(hoursAgo)).toFixed(2)),
      },
    };
  }),
);

const listingData: FeatureCollection<Point, ListingProperties> = {
  type: "FeatureCollection",
  features,
};

export default listingData;
