import * as api from "./api";

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
  { name: "Academic Building East Wing", code: "ABE", campus: "College Ave" },
  { name: "Academic Building West Wing", code: "ABW", campus: "College Ave" },
  { name: "Campbell Hall", code: "CA", campus: "College Ave" },
  { name: "Hardenbergh Hall", code: "HH", campus: "College Ave" },
  { name: "Milledoler Hall", code: "MI", campus: "College Ave" },
  { name: "Murray Hall", code: "MU", campus: "College Ave" },
  { name: "Scott Hall", code: "SC", campus: "College Ave" },
  { name: "Allison Road Classroom", code: "ARC", campus: "Busch" },
  { name: "Biomedical Engineering Building", code: "BME", campus: "Busch" },
  { name: "Chemistry & Chemical Biology", code: "CCB", campus: "Busch" },
  { name: "CoRE Building", code: "COR", campus: "Busch" },
  { name: "Engineering Building", code: "EN", campus: "Busch" },
  { name: "Fiber Optic Materials Research Building", code: "FBO", campus: "Busch" },
  { name: "Hill Center", code: "HLL", campus: "Busch" },
  { name: "Pharmacy Building", code: "PH", campus: "Busch" },
  { name: "Physics Lecture Hall", code: "PHY", campus: "Busch" },
  { name: "Richard Weeks Hall of Engineering", code: "RWH", campus: "Busch" },
  { name: "Science & Engineering Research Center", code: "SEC", campus: "Busch" },
  { name: "Beck Hall", code: "BE", campus: "Livingston" },
  { name: "Lucy Stone Hall", code: "LSH", campus: "Livingston" },
  { name: "Tillett Hall", code: "TIL", campus: "Livingston" },
  { name: "Art History Hall", code: "ARH", campus: "Cook/Douglass" },
  { name: "Cook/Douglass Lecture Hall", code: "CDL", campus: "Cook/Douglass" },
  { name: "Food Science and Nutritional Sciences West", code: "FSW", campus: "Cook/Douglass" },
  { name: "Hickman Hall", code: "HCK", campus: "Cook/Douglass" },
  { name: "Loree Classroom Building", code: "LOR", campus: "Cook/Douglass" },
  { name: "Ludwig Global Village Learning Center", code: "KLG", campus: "Cook/Douglass" },
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
  "room-scan": "Simulated room scan",
  placard: "Simulated placard read",
  manual: "Chosen manually",
};

export type RoomCandidate = {
  location: RoomLocation;
  features: string[];
  /** False when the result came from the real backend. */
  demo?: boolean;
  /** True when the backend is sure about this room; false for a close call between rooms. */
  confident?: boolean;
};

export type ItemDescription = {
  title: string;
  category: string;
  color: string;
  description: string;
  demo?: boolean;
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
    { code: "ARC", room: "103", features: ["500-seat lecture hall", "Tiered seating"] },
    { code: "PHY", room: "001", features: ["316-seat lecture hall", "Projection screens"] },
    { code: "RWH", room: "105", features: ["285-seat auditorium", "Red front wall", "Tall windows"] },
  ],
  Livingston: [
    { code: "LSH", room: "A102", features: ["400-seat lecture hall", "Tiered seating"] },
    { code: "BE", room: "100", features: ["391-seat lecture hall", "Projection screens"] },
    { code: "TIL", room: "232", features: ["208-seat lecture hall", "Tiered seating"] },
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
    return demoRooms[campus].map((room) => ({ location: toLocation(campus, room.code, room.room, "room-scan"), features: room.features, demo: true }));
  },
  async readPlacard() {
    await wait(900);
    const { campus, code, name } = { campus: "College Ave" as CampusId, code: "HH", name: "Hardenbergh Hall" };
    return { campus, code, building: name, room: "A2" };
  },
  async describeItem() {
    await wait(1000);
    return { title: "Blue water bottle", category: "Water bottle", color: "Navy blue", description: "Insulated bottle with a silver lid and a small sticker", demo: true };
  },
};

const categoryLabels: Record<string, string> = {
  bottle: "Water bottle", electronics: "Electronics", clothing: "Clothing", bag: "Bag", keys: "Keys",
  wallet: "Wallet or ID", id_card: "Wallet or ID", financial_card: "Wallet or ID", cash: "Wallet or ID", other: "",
};

function campusOf(value: string): CampusId {
  return (campuses as string[]).includes(value) ? (value as CampusId) : "College Ave";
}

/**
 * Uses the Flask backend (backend/) for real photos when it is running, and the demo data
 * otherwise (Figma preview, sample-photo buttons, or offline). Any backend error also falls
 * back to the demo result so a live demo never dead-ends.
 */
export const backendRecognizer: RoomRecognizer = {
  isDemo: false,
  async recognizeRoom(photo, campusHint) {
    if (!photo || !(await api.isOnline())) return demoRecognizer.recognizeRoom(photo, campusHint);
    try {
      const result = await api.recognizeRoomPhoto(photo, campusHint);
      return result.candidates.map((candidate) => ({
        location: {
          campus: campusOf(candidate.campus),
          code: candidate.room_id.split("-")[0] || candidate.building,
          building: candidate.building,
          room: candidate.room,
          source: "room-scan" as const,
        },
        features: [...candidate.evidence, ...(candidate.conflicts ?? [])],
        demo: false,
        confident: candidate.confident ?? false,
      }));
    } catch (error) {
      // The server is up but the scan failed or timed out. Show "no match" so the finder
      // uses the placard or picks the room, rather than showing made-up sample rooms.
      console.warn("Room recognition failed", error);
      return [];
    }
  },
  async readPlacard(photo) {
    // The backend has no sign reading without Gemini. Real photos fall through to
    // "couldn't read the sign", which offers manual entry.
    if (photo && (await api.isOnline())) return null;
    return demoRecognizer.readPlacard(photo);
  },
  async describeItem(photo) {
    if (!photo || !(await api.isOnline())) return demoRecognizer.describeItem(photo);
    try {
      const { suggestion } = await api.analyzeItemPhoto(photo);
      const color = suggestion.attributes.color ?? "";
      const label = categoryLabels[suggestion.category] ?? "";
      const genericTitle = !suggestion.title || suggestion.title === "Found item";
      return {
        title: genericTitle ? (color ? `${color[0].toUpperCase()}${color.slice(1)} item` : "") : suggestion.title,
        category: label,
        color: color ? `${color[0].toUpperCase()}${color.slice(1)}` : "",
        description: suggestion.description,
        demo: false,
      };
    } catch (error) {
      console.warn("Item analysis failed, using demo result", error);
      return demoRecognizer.describeItem(photo);
    }
  },
};

export const activeRecognizer: RoomRecognizer = backendRecognizer;

export const acceptedImageTypes = ["image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"];

export function validateImage(file: File | undefined): string | null {
  if (!file) return "No photo was selected. Try again or use another option.";
  if (file.type && !acceptedImageTypes.includes(file.type)) return "That file type isn't supported. Use a JPG, PNG, WEBP, or HEIC photo.";
  if (file.size > 15 * 1024 * 1024) return "That photo is larger than 15 MB. Try a smaller one.";
  return null;
}
