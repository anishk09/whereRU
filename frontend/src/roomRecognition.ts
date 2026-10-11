// Classroom location data and recognition adapters.
// The demo provider returns sample results. Swap in a Gemini provider later
// by implementing RoomRecognizer and changing activeRecognizer below.

export type CampusId = "College Ave" | "Busch" | "Livingston" | "Cook/Douglass";

export type LocationSource = "room-scan" | "placard" | "manual";

export type RoomLocation = {
  campus: CampusId;
  building: string;
  code: string;
  room: string;
  source: LocationSource;
};

export type Building = { name: string; code: string; campus: CampusId };

// Building codes match the public Rutgers Schedule of Classes feed.
export const buildings: Building[] = [
  { name: "Hardenbergh Hall", code: "HH", campus: "College Ave" },
  { name: "Scott Hall", code: "SC", campus: "College Ave" },
  { name: "Murray Hall", code: "MU", campus: "College Ave" },
  { name: "Academic Building West", code: "ABW", campus: "College Ave" },
  { name: "Campbell Hall", code: "CA", campus: "College Ave" },
  { name: "Hill Center", code: "HLL", campus: "Busch" },
  { name: "Allison Road Classroom", code: "ARC", campus: "Busch" },
  { name: "Science and Engineering Resource Center", code: "SEC", campus: "Busch" },
  { name: "Beck Hall", code: "BE", campus: "Livingston" },
  { name: "Tillett Hall", code: "TIL", campus: "Livingston" },
  { name: "Hickman Hall", code: "HCK", campus: "Cook/Douglass" },
  { name: "Ruth Adams Building", code: "RAB", campus: "Cook/Douglass" },
];

export const campuses: CampusId[] = ["College Ave", "Busch", "Livingston", "Cook/Douglass"];

export const campusCenters: Record<CampusId, [number, number]> = {
  "College Ave": [-74.4518, 40.502],
  Busch: [-74.46, 40.5225],
  Livingston: [-74.437, 40.5235],
  "Cook/Douglass": [-74.436, 40.4835],
};

export function nearestCampus(longitude: number, latitude: number): CampusId {
  return campuses.reduce((best, campus) => {
    const [x, y] = campusCenters[campus];
    const [bx, by] = campusCenters[best];
    return Math.hypot(x - longitude, y - latitude) < Math.hypot(bx - longitude, by - latitude) ? campus : best;
  }, campuses[0]);
}

export function formatLocation(location: RoomLocation) {
  return `${location.building} ${location.room}`.trim();
}

export function shortLocation(location: RoomLocation) {
  return `${location.code} ${location.room}`.trim();
}

export const sourceLabel: Record<LocationSource, string> = {
  "room-scan": "Room scan",
  placard: "Placard",
  manual: "Chosen manually",
};

export type RoomCandidate = {
  location: RoomLocation;
  features: string[];
};

export type ItemDescription = {
  title: string;
  category: string;
  color: string;
  description: string;
};

export interface RoomRecognizer {
  readonly isDemo: boolean;
  recognizeRoom(photo: File | null, campusHint: CampusId | null): Promise<RoomCandidate[]>;
  readPlacard(photo: File | null): Promise<Omit<RoomLocation, "source"> | null>;
  describeItem(photo: File | null): Promise<ItemDescription>;
}

const wait = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

// Sample rooms for the demo. The College Ave and Livingston rooms appear in the
// Fall 2026 schedule feed; the others are placeholders until the real index exists.
const demoRooms: Record<CampusId, { code: string; room: string; features: string[] }[]> = {
  "College Ave": [
    { code: "HH", room: "A2", features: ["Tiered seating", "Two chalkboards", "No windows"] },
    { code: "SC", room: "221", features: ["Flat floor", "Whiteboard wall", "Tall windows"] },
    { code: "MU", room: "212", features: ["Seminar tables", "Projector screen"] },
  ],
  Busch: [
    { code: "ARC", room: "103", features: ["Large lecture hall", "Tiered seating"] },
    { code: "HLL", room: "116", features: ["Flat floor", "Whiteboards"] },
    { code: "SEC", room: "111", features: ["Tiered seating", "Wood panels"] },
  ],
  Livingston: [
    { code: "BE", room: "101", features: ["Flat floor", "Tall windows"] },
    { code: "BE", room: "219", features: ["Seminar layout", "Whiteboard wall"] },
    { code: "TIL", room: "232", features: ["Tablet arm chairs"] },
  ],
  "Cook/Douglass": [
    { code: "HCK", room: "138", features: ["Tiered seating", "Projector screen"] },
    { code: "RAB", room: "018", features: ["Flat floor", "Whiteboards"] },
    { code: "HCK", room: "110", features: ["Tablet arm chairs"] },
  ],
};

function toLocation(campus: CampusId, code: string, room: string, source: LocationSource): RoomLocation {
  const building = buildings.find((item) => item.code === code);
  return { campus, code, room, building: building?.name ?? code, source };
}

export const demoRecognizer: RoomRecognizer = {
  isDemo: true,
  async recognizeRoom(_photo, campusHint) {
    await wait(1400);
    const campus = campusHint ?? "College Ave";
    return demoRooms[campus].map((room) => ({ location: toLocation(campus, room.code, room.room, "room-scan"), features: room.features }));
  },
  async readPlacard() {
    await wait(900);
    const { campus, code, name } = { campus: "College Ave" as CampusId, code: "HH", name: "Hardenbergh Hall" };
    return { campus, code, building: name, room: "A2" };
  },
  async describeItem() {
    await wait(1000);
    return { title: "Blue water bottle", category: "Water bottle", color: "Navy blue", description: "Insulated bottle with a silver lid and a small sticker" };
  },
};

export const activeRecognizer: RoomRecognizer = demoRecognizer;

export const acceptedImageTypes = ["image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"];

export function validateImage(file: File | undefined): string | null {
  if (!file) return "No photo was selected. Try again or use another option.";
  if (file.type && !acceptedImageTypes.includes(file.type)) return "That file type isn't supported. Use a JPG, PNG, WEBP, or HEIC photo.";
  if (file.size > 15 * 1024 * 1024) return "That photo is larger than 15 MB. Try a smaller one.";
  return null;
}
