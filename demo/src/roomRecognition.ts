import {api} from "./api";
// Classroom location data and recognition adapters.
// Local reference comparison and on-device OCR require no cloud API key.

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
  { name: "Academic Building East", code: "ABE", campus: "College Ave" },
  { name: "Campbell Hall", code: "CA", campus: "College Ave" },
  { name: "Richard Weeks Hall", code:"RWH", campus:"Busch" },
  { name: "Physics Lecture Hall", code:"PHY", campus:"Busch" },
  { name: "Lucy Stone Hall", code:"LSH", campus:"Livingston" },
  { name: "Wright Labs", code:"WL", campus:"Busch" },
  { name: "Cook/Douglass Lecture Hall", code:"CDL", campus:"Cook/Douglass" },
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
  recognizeRoom(photo: File | null, campusHint: CampusId | null, scope?:"all"|"five"): Promise<RoomCandidate[]>;
  readPlacard(photo: File | null): Promise<Omit<RoomLocation, "source"> | null>;
  describeItem(photo: File | null): Promise<ItemDescription>;
}

async function roomQuery(photo:File|null,campusHint:CampusId|null,scope:"all"|"five"="all"){
  const room=scope==="five"?"RWH-105":"ABW-1150A";
  const file=photo||new File([await fetch(`/api/classrooms/${room}/reference-photo`).then(r=>{if(!r.ok)throw new Error("Reference photo unavailable");return r.blob();})],`Rutgers-${room}.jpg`,{type:"image/jpeg"});
  const form=new FormData();form.append("image",file);form.append("scope",scope);if(campusHint)form.append("campus",campusHint);
  return api("/vision/rooms",form);
}
export const activeRecognizer: RoomRecognizer = {
 isDemo:false,
 async recognizeRoom(photo,campusHint,scope="all"){const result=await roomQuery(photo,campusHint,scope);return result.candidates.map((r:any)=>({location:{campus:r.campus,building:r.building,code:r.code,room:r.room,source:"room-scan"},features:[...r.evidence,"Confirm this room before saving"]}));},
 async readPlacard(photo){if(!photo)return null;const result=await roomQuery(photo,null);const candidate=result.candidates.find((r:any)=>r.method==="local-ocr");return candidate?{campus:candidate.campus,building:candidate.building,code:candidate.code,room:candidate.room}:null;},
 async describeItem(photo){if(!photo)return {title:"",category:"",color:"",description:""};const form=new FormData();form.append("image",photo);const result=await api("/vision/items",form);return {title:result.title,category:result.category,color:result.attributes.color||"",description:result.private_details||""};}
};

export const acceptedImageTypes = ["image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"];

export function validateImage(file: File | undefined): string | null {
  if (!file) return "No photo was selected. Try again or use another option.";
  if (file.type && !acceptedImageTypes.includes(file.type)) return "That file type isn't supported. Use a JPG, PNG, WEBP, or HEIC photo.";
  if (file.size > 8 * 1024 * 1024) return "That photo is larger than 8 MB. Try a smaller one.";
  return null;
}
