import { createContext, useContext, useEffect, useMemo, useRef, useState, type ImgHTMLAttributes, type ReactNode } from "react";
import type { CampusId, LocationSource } from "./roomRecognition";
import type { PlaceType } from "./mapData";
import { startDemoSync, type SyncCatalog } from "./demoSync";
import { uploadDemoPhoto } from "./api";
import { metersBetween } from "./nearby";

export type ReportType = "lost" | "found";
export type ReportStatus = "active" | "possible_match" | "claim_under_review" | "returned" | "closed";
export type ReportVisibility = "public" | "trusted-only" | "private";
export type ReportCategory = "Electronics" | "Wallets/IDs" | "Keys" | "Bags" | "Clothing" | "Bottles" | "School Supplies" | "Other";
export type ClaimStatus = "submitted" | "approved" | "rejected" | "handoff" | "returned";

export type DemoUser = {
  id: "demo-jordan" | "demo-maya";
  firstName: string;
  lastName: string;
  email: string;
};

const initialDemoUsers: DemoUser[] = [
  { id: "demo-jordan", firstName: "Jordan", lastName: "Lee", email: "jordan.lee@rutgers.edu" },
  { id: "demo-maya", firstName: "Maya", lastName: "Patel", email: "maya.patel@rutgers.edu" },
];

export type ReportLocation = {
  campus: CampusId;
  area: string;
  building?: string;
  room?: string;
  source: LocationSource | "timeline" | "manual-area";
  placeType: PlaceType;
  approximateLabel: string;
  approximateCoordinates?: [number, number];
  precise?: {
    label: string;
    coordinates?: [number, number];
  };
};

export type ItemReport = {
  id: string;
  reporterId: string;
  type: ReportType;
  itemName: string;
  category: ReportCategory;
  color: string;
  publicDescription: string;
  privateDetails?: string;
  photoUrl?: string | null;
  location: ReportLocation | null;
  observedAt: string;
  createdAt: string;
  updatedAt: string;
  status: ReportStatus;
  visibility: ReportVisibility;
  sensitive: boolean;
  sample: boolean;
  clientSubmissionId?: string;
  relatedLostReportId?: string;
};

export type PublicItemReport = Omit<ItemReport, "reporterId" | "privateDetails" | "location" | "clientSubmissionId"> & {
  location: Omit<ReportLocation, "precise"> | null;
  restrictedProjection: boolean;
};

export type Claim = {
  id: string;
  reportId: string;
  claimantId: string;
  status: ClaimStatus;
  /** Where the finder left the item or will meet, shown to the claimant. */
  handoffNote?: string;
  createdAt: string;
  updatedAt: string;
};

export type AppNotification = {
  id: string;
  userId: string;
  reportId: string;
  claimId?: string;
  title: string;
  body: string;
  createdAt: string;
  read: boolean;
  demo: boolean;
};

export type ReportFilters = {
  type?: ReportType;
  campus?: CampusId;
  category?: ReportCategory;
  search?: string;
  includeClosed?: boolean;
  includeTrusted?: boolean;
};

type CatalogSnapshot = {
  reports: ItemReport[];
  claims: Claim[];
  notifications: AppNotification[];
};

export type NewReport = Omit<ItemReport, "id" | "createdAt" | "updatedAt">;

export interface ReportRepository {
  getAll(): ItemReport[];
  getById(id: string): ItemReport | undefined;
  filter(filters: ReportFilters): ItemReport[];
  getByReporter(reporterId: string): ItemReport[];
  create(input: NewReport, actorId: string): ItemReport;
  update(id: string, actorId: string, updates: Partial<Omit<ItemReport, "id" | "reporterId" | "createdAt">>): ItemReport | undefined;
  close(id: string, actorId: string): ItemReport | undefined;
  getClaims(): Claim[];
  createClaim(reportId: string, claimantId: string, privateProof?: string): Claim;
  getClaimAnswer(id: string, actorId: string): string | undefined;
  updateClaim(id: string, status: ClaimStatus, actorId: string, handoffNote?: string): Claim | undefined;
  addNotification(notification: Omit<AppNotification, "id" | "createdAt">): AppNotification;
  markNotificationRead(id: string, actorId: string): void;
  snapshot(): CatalogSnapshot;
}

const STORAGE_KEY = "where-ru.catalog.v1";
const IMAGE_DB = "where-ru.images.v1";
const IMAGE_STORE = "images";
const IMAGE_PREFIX = "where-ru-image:";

function imageDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("Local image storage is unavailable in this browser."));
      return;
    }
    const request = indexedDB.open(IMAGE_DB, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(IMAGE_STORE);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(new Error("The photo could not be saved locally."));
  });
}

export async function storeReportImage(file: File): Promise<string> {
  // In a live demo the photo goes to the shared server so the other phone sees it too.
  const shared = await uploadDemoPhoto(file).catch(() => null);
  if (shared) return shared;
  const id = uid("image");
  const database = await imageDatabase();
  await new Promise<void>((resolve, reject) => {
    const transaction = database.transaction(IMAGE_STORE, "readwrite");
    transaction.objectStore(IMAGE_STORE).put(file, id);
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(new Error("The photo could not be saved locally."));
  });
  database.close();
  return `${IMAGE_PREFIX}${id}`;
}

async function resolveReportImage(reference: string): Promise<string | null> {
  if (!reference.startsWith(IMAGE_PREFIX)) return reference;
  try {
    const database = await imageDatabase();
    const blob = await new Promise<Blob | undefined>((resolve, reject) => {
      const request = database.transaction(IMAGE_STORE).objectStore(IMAGE_STORE).get(reference.slice(IMAGE_PREFIX.length));
      request.onsuccess = () => resolve(request.result as Blob | undefined);
      request.onerror = () => reject(request.error);
    });
    database.close();
    return blob ? URL.createObjectURL(blob) : null;
  } catch {
    return null;
  }
}

export function ReportImage({ src, fallback, ...props }: Omit<ImgHTMLAttributes<HTMLImageElement>, "src"> & { src?: string | null; fallback: ReactNode }) {
  const [resolved, setResolved] = useState<string | null>(() => src && !src.startsWith(IMAGE_PREFIX) ? src : null);
  useEffect(() => {
    let active = true;
    let objectUrl: string | null = null;
    setResolved(src && !src.startsWith(IMAGE_PREFIX) ? src : null);
    if (src?.startsWith(IMAGE_PREFIX)) {
      resolveReportImage(src).then((url) => {
        if (!active) {
          if (url?.startsWith("blob:")) URL.revokeObjectURL(url);
          return;
        }
        objectUrl = url;
        setResolved(url);
      });
    }
    return () => {
      active = false;
      if (objectUrl?.startsWith("blob:")) URL.revokeObjectURL(objectUrl);
    };
  }, [src]);
  return resolved ? <img {...props} src={resolved} /> : <>{fallback}</>;
}

function uid(prefix: string) {
  const value = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${value}`;
}

function hoursAgo(hours: number) {
  return new Date(Date.now() - hours * 60 * 60 * 1000).toISOString();
}

const seedReports: ItemReport[] = [
  {
    id: "report-bottle-found",
    reporterId: "demo-jordan",
    type: "found",
    itemName: "Blue water bottle",
    category: "Bottles",
    color: "Navy blue",
    publicDescription: "Insulated bottle with a silver lid.",
    privateDetails: "Small white cat sticker near the bottom.",
    photoUrl: null,
    location: {
      campus: "College Ave",
      area: "Hardenbergh Hall",
      building: "Hardenbergh Hall",
      room: "A2",
      source: "room-scan",
      placeType: "classroom",
      approximateLabel: "Near Hardenbergh Hall",
      approximateCoordinates: [-74.4486, 40.5008],
      precise: { label: "Hardenbergh Hall A2" },
    },
    observedAt: hoursAgo(2),
    createdAt: hoursAgo(1.8),
    updatedAt: hoursAgo(1.8),
    status: "active",
    visibility: "public",
    sensitive: false,
    sample: true,
  },
  {
    id: "report-airpods-found",
    reporterId: "demo-jordan",
    type: "found",
    itemName: "AirPods case",
    category: "Electronics",
    color: "White",
    publicDescription: "Charging case found near the library entrance.",
    privateDetails: "The case has a private engraving.",
    photoUrl: null,
    location: {
      campus: "College Ave",
      area: "Alexander Library",
      building: "Alexander Library",
      source: "manual-area",
      placeType: "library",
      approximateLabel: "Near Alexander Library",
      approximateCoordinates: [-74.4522, 40.5045],
      precise: { label: "Held at a staffed desk" },
    },
    observedAt: hoursAgo(5),
    createdAt: hoursAgo(4.5),
    updatedAt: hoursAgo(4.5),
    status: "active",
    visibility: "public",
    sensitive: true,
    sample: true,
  },
  {
    id: "report-keys-lost",
    reporterId: "demo-user-alex",
    type: "lost",
    itemName: "Keys on a red lanyard",
    category: "Keys",
    color: "Silver and red",
    publicDescription: "Several keys attached to a Rutgers lanyard.",
    privateDetails: "Includes a uniquely shaped apartment key.",
    photoUrl: null,
    location: {
      campus: "Busch",
      area: "Busch Student Center",
      source: "timeline",
      placeType: "building",
      approximateLabel: "Around Busch Student Center",
      approximateCoordinates: [-74.4584, 40.5235],
    },
    observedAt: hoursAgo(8),
    createdAt: hoursAgo(7.5),
    updatedAt: hoursAgo(7.5),
    status: "possible_match",
    visibility: "public",
    sensitive: true,
    sample: true,
  },
  {
    id: "report-hoodie-lost",
    reporterId: "demo-user-sam",
    type: "lost",
    itemName: "Gray Rutgers hoodie",
    category: "Clothing",
    color: "Gray",
    publicDescription: "Pullover hoodie, size details kept private.",
    photoUrl: null,
    location: {
      campus: "Livingston",
      area: "Livingston Student Center",
      source: "timeline",
      placeType: "dining",
      approximateLabel: "Near Livingston Student Center",
      approximateCoordinates: [-74.4369, 40.5241],
    },
    observedAt: hoursAgo(18),
    createdAt: hoursAgo(17.5),
    updatedAt: hoursAgo(17.5),
    status: "active",
    visibility: "public",
    sensitive: false,
    sample: true,
  },
  {
    id: "report-umbrella-returned",
    reporterId: "demo-jordan",
    type: "lost",
    itemName: "Black umbrella",
    category: "Other",
    color: "Black",
    publicDescription: "Compact folding umbrella.",
    photoUrl: null,
    location: {
      campus: "Livingston",
      area: "Livingston Student Center",
      source: "timeline",
      placeType: "building",
      approximateLabel: "Near Livingston Student Center",
    },
    observedAt: hoursAgo(240),
    createdAt: hoursAgo(239),
    updatedAt: hoursAgo(239),
    status: "returned",
    visibility: "public",
    sensitive: false,
    sample: true,
  },
];

function persistentSnapshot(snapshot: CatalogSnapshot): CatalogSnapshot {
  return {
    ...snapshot,
    reports: snapshot.reports.map((report) => ({
      ...report,
      photoUrl: report.photoUrl?.startsWith("blob:") ? null : report.photoUrl,
    })),
    claims: snapshot.claims,
  };
}

function stableUserId(id: string) {
  if (id === "current-user" || id === "demo-user-jordan") return "demo-jordan";
  return id;
}

function currentClaimStatus(status: string): ClaimStatus {
  if (status === "under_review" || status === "more_information_requested") return "submitted";
  if (status === "return_arranged") return "handoff";
  if (["submitted", "approved", "rejected", "handoff", "returned"].includes(status)) return status as ClaimStatus;
  return "submitted";
}

const COLOR_WORDS = new Set(["black", "white", "gray", "grey", "silver", "red", "pink", "orange", "yellow", "gold", "green", "blue", "navy", "purple", "brown", "beige", "clear", "light", "dark"]);

// Words that say nothing about which specific item it is ("bottle" matches every bottle).
const GENERIC_WORDS = new Set(["with", "from", "near", "this", "that", "have", "found", "lost", "left", "item", "items", "small", "large", "little", "some", "inside", "outside", "front", "back", "side", "bottle", "water", "case", "card", "cards", "keys", "bag", "bags", "phone", "rutgers", "campus", "room", "hall", "floor", "table", "desk", "seat", "under", "sample", "demo", "photo", "color", "colored"]);

function keywords(report: ItemReport) {
  return new Set(`${report.itemName} ${report.publicDescription}`.toLowerCase().split(/[^a-z0-9]+/).filter((word) => word.length >= 4 && !COLOR_WORDS.has(word) && !GENERIC_WORDS.has(word)));
}

function colorWords(value: string) {
  return new Set(value.toLowerCase().split(/[^a-z]+/).filter((word) => COLOR_WORDS.has(word) && word !== "light" && word !== "dark"));
}

/** 0 = not a match. Same category is required; then a shared distinctive name word (3 points)
 * or a matching color (1 point) must back it up, plus a bonus when they're in the same place. */
function matchScore(lost: ItemReport, found: ItemReport) {
  if (lost.category !== found.category) return 0;
  const a = keywords(lost);
  const shared = [...keywords(found)].filter((word) => a.has(word)).length;
  const lostColors = colorWords(`${lost.color} ${lost.itemName}`);
  const colorMatch = [...colorWords(`${found.color} ${found.itemName}`)].some((color) => lostColors.has(color) || (color === "navy" && lostColors.has("blue")) || (color === "blue" && lostColors.has("navy")));
  if (!shared && !colorMatch) return 0;
  const sameBuilding = Boolean(lost.location?.building && found.location?.building && lost.location.building.toLowerCase() === found.location.building.toLowerCase());
  return 3 * shared + (colorMatch ? 1 : 0) + (sameBuilding ? 2 : 0) + (lost.location?.campus === found.location?.campus ? 1 : 0);
}

/** "in Hill Center, the same building where you lost it" / "about 4 min walk from where you lost it". */
function proximity(lost: ReportLocation | null, found: ReportLocation | null): { near: boolean; text: string } {
  if (!found) return { near: false, text: "on campus" };
  const place = found.building || found.area || found.approximateLabel;
  const sameText = (a?: string, b?: string) => Boolean(a && b && a.trim().toLowerCase() === b.trim().toLowerCase());
  if (lost && sameText(lost.building || lost.area, found.building || found.area)) {
    return sameText(lost.room, found.room)
      ? { near: true, text: `in ${place} ${found.room}, the same room where you lost it` }
      : { near: true, text: `in ${place}, the same building where you lost it` };
  }
  const a = lost?.approximateCoordinates, b = found.approximateCoordinates;
  if (a && b) {
    const meters = metersBetween(a, b);
    if (meters < 150) return { near: true, text: `near ${place}, right by where you lost it` };
    if (meters < 1200) return { near: true, text: `near ${place}, about ${Math.max(2, Math.round(meters / 80))} min walk from where you lost it` };
  }
  if (lost && lost.campus === found.campus) return { near: true, text: `near ${place} on ${found.campus}, the same campus where you lost it` };
  return { near: false, text: `near ${place} on ${found.campus}` };
}

export class LocalReportRepository implements ReportRepository {
  private data: CatalogSnapshot;
  private claimAnswers = new Map<string, string>();

  constructor() {
    this.data = this.load();
  }

  private load(): CatalogSnapshot {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as CatalogSnapshot;
        return {
          reports: parsed.reports.map((report) => ({
            ...report,
            reporterId: stableUserId(report.reporterId),
            photoUrl: report.photoUrl?.startsWith("blob:") ? null : report.photoUrl,
            updatedAt: report.updatedAt || report.createdAt,
          })),
          claims: parsed.claims.map((storedClaim) => {
            const claim = storedClaim as Claim & { privateProof?: string; evidenceProvided?: boolean };
            return {
              id: claim.id,
              reportId: claim.reportId,
              claimantId: stableUserId(claim.claimantId),
              status: currentClaimStatus(claim.status),
              handoffNote: claim.handoffNote,
              createdAt: claim.createdAt,
              updatedAt: claim.updatedAt || claim.createdAt,
            };
          }),
          notifications: parsed.notifications,
        };
      }
    } catch {
      // Storage can be unavailable in private browsing; the in-memory repository still works.
    }
    return { reports: seedReports, claims: [], notifications: [] };
  }

  private persist() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(persistentSnapshot(this.data)));
    } catch {
      // Keep the current session functional when storage is full or unavailable.
    }
  }

  getAll() {
    return [...this.data.reports];
  }

  getById(id: string) {
    return this.data.reports.find((report) => report.id === id);
  }

  filter(filters: ReportFilters) {
    const query = filters.search?.trim().toLowerCase();
    return this.data.reports.filter((report) => {
      if (!filters.includeClosed && ["closed", "returned"].includes(report.status)) return false;
      if (filters.type && report.type !== filters.type) return false;
      if (filters.campus && report.location?.campus !== filters.campus) return false;
      if (filters.category && report.category !== filters.category) return false;
      if (query) {
        const searchable = [report.itemName, report.category, report.publicDescription, report.location?.approximateLabel].join(" ").toLowerCase();
        if (!searchable.includes(query)) return false;
      }
      return true;
    });
  }

  getByReporter(reporterId: string) {
    return this.data.reports.filter((report) => report.reporterId === reporterId);
  }

  create(input: NewReport, actorId: string) {
    const duplicate = input.clientSubmissionId && this.data.reports.find((report) => report.clientSubmissionId === input.clientSubmissionId);
    if (duplicate) return duplicate;
    const observedTime = new Date(input.observedAt).getTime();
    if (!Number.isFinite(observedTime)) throw new Error("Choose a valid date and time.");
    if (observedTime > Date.now() + 5 * 60_000) throw new Error("The lost or found time cannot be in the future.");
    if (input.relatedLostReportId) {
      const related = this.getById(input.relatedLostReportId);
      if (!related || related.type !== "lost") throw new Error("The related lost report is unavailable.");
    }
    const now = new Date().toISOString();
    const report: ItemReport = { ...input, reporterId: actorId, id: uid("report"), createdAt: now, updatedAt: now };
    this.data = { ...this.data, reports: [report, ...this.data.reports] };
    this.notifyPossibleMatches(report);
    this.persist();
    return report;
  }

  /** A new found report alerts owners of matching lost reports (and a new lost report checks
   * what has already been turned in). The alert says how close the find is. */
  private notifyPossibleMatches(report: ItemReport) {
    // Only a newly posted FOUND item triggers alerts, and only to the owner of the single best
    // matching open LOST listing (same category plus a shared name word or matching color).
    if (report.type !== "found") return;
    const open = (candidate: ItemReport) => ["active", "possible_match"].includes(candidate.status);
    const ranked = this.data.reports
      .filter((lost) => lost.type === "lost" && open(lost) && lost.reporterId !== report.reporterId)
      .map((lost) => ({ lost, score: matchScore(lost, report) }))
      .filter((pair) => pair.score > 0)
      .sort((a, b) => b.score - a.score);
    if (!ranked.length) return;
    const { lost } = ranked[0];
    const found = report;
    {
      const where = proximity(lost.location, found.location);
      const name = found.itemName.toLowerCase();
      const colorAlready = found.color.toLowerCase().split(/\s+/).some((word) => word && name.includes(word));
      const item = (colorAlready || !found.color ? name : `${found.color.toLowerCase()} ${name}`) || found.category.toLowerCase();
      this.addNotification({
        userId: lost.reporterId,
        reportId: found.id,
        title: where.near ? "Possible match near you" : "Possible match",
        body: `A ${item} was found ${where.text}. Tap to check if it's yours.`,
        read: false,
        demo: true,
      });
      if (lost.status === "active") this.updateInternal(lost.id, { status: "possible_match" });
      if (found.status === "active") this.updateInternal(found.id, { status: "possible_match" });
    }
  }


  private updateInternal(id: string, updates: Partial<Omit<ItemReport, "id" | "reporterId" | "createdAt" | "updatedAt">>) {
    const current = this.getById(id);
    if (!current) return undefined;
    const updated = { ...current, ...updates, updatedAt: new Date().toISOString() };
    this.data = { ...this.data, reports: this.data.reports.map((report) => report.id === id ? updated : report) };
    this.persist();
    return updated;
  }

  update(id: string, actorId: string, updates: Partial<Omit<ItemReport, "id" | "reporterId" | "createdAt">>) {
    const current = this.getById(id);
    if (!current) return undefined;
    if (current.reporterId !== actorId) throw new Error("Only the report owner can edit this listing in the demo.");
    if ("status" in updates && updates.status !== current.status) throw new Error("Report status must be changed through its review or return workflow.");
    if (["closed", "returned"].includes(current.status)) throw new Error("Unavailable reports cannot be edited.");
    return this.updateInternal(id, updates);
  }

  close(id: string, actorId: string) {
    const current = this.getById(id);
    if (!current) return undefined;
    if (current.reporterId !== actorId) throw new Error("Only the report owner can close this listing in the demo.");
    if (current.status === "returned") throw new Error("A returned report cannot be closed.");
    return this.updateInternal(id, { status: "closed" });
  }

  getClaims() {
    return [...this.data.claims];
  }

  createClaim(reportId: string, claimantId: string, privateProof = "") {
    const report = this.getById(reportId);
    if (!report) throw new Error("That report does not exist.");
    if (!["active", "possible_match", "claim_under_review"].includes(report.status)) throw new Error("That report is not available for claims.");
    if (report.type !== "found" || report.visibility === "private") throw new Error("That report is not available to this claimant.");
    if (report.reporterId === claimantId) throw new Error("You cannot claim your own listing.");
    if (privateProof.trim().length < 8) throw new Error("Enter a specific ownership detail before submitting.");
    const duplicate = this.data.claims.find((claim) => claim.reportId === reportId && claim.claimantId === claimantId && !["rejected", "returned"].includes(claim.status));
    if (duplicate) throw new Error("You already have an active claim for this report.");
    const now = new Date().toISOString();
    const claim: Claim = { id: uid("claim"), reportId, claimantId, status: "submitted", createdAt: now, updatedAt: now };
    this.claimAnswers.set(claim.id, privateProof.trim());
    this.data = { ...this.data, claims: [claim, ...this.data.claims] };
    this.updateInternal(reportId, { status: "claim_under_review" });
    this.addNotification({
      userId: report.reporterId,
      reportId,
      claimId: claim.id,
      title: "New ownership claim",
      body: "A demo claimant submitted private ownership details for review.",
      read: false,
      demo: true,
    });
    this.persist();
    return claim;
  }

  getClaimAnswer(id: string, actorId: string) {
    const claim = this.data.claims.find((item) => item.id === id);
    const report = claim && this.getById(claim.reportId);
    if (!claim || !report || report.reporterId !== actorId) return undefined;
    return this.claimAnswers.get(id);
  }

  updateClaim(id: string, status: ClaimStatus, actorId: string, handoffNote?: string) {
    const current = this.data.claims.find((claim) => claim.id === id);
    if (!current) return undefined;
    const report = this.getById(current.reportId);
    if (!report) throw new Error("The claim's report no longer exists.");
    if (report.reporterId !== actorId) throw new Error("Only the report owner can review this claim in the demo.");
    if (current.status === status) return current;
    const transitions: Record<ClaimStatus, ClaimStatus[]> = {
      submitted: ["approved", "rejected"],
      approved: ["handoff"],
      rejected: [],
      handoff: ["returned"],
      returned: [],
    };
    if (!transitions[current.status].includes(status)) throw new Error(`A claim cannot move from ${current.status} to ${status}.`);
    if (status === "approved" && !this.claimAnswers.get(id)?.trim()) throw new Error("Private answer unavailable after refresh — ask the claimant to resubmit.");
    if (["closed", "returned"].includes(report.status)) throw new Error("Claims cannot be changed for an unavailable report.");
    const updated: Claim = { ...current, status, ...(handoffNote ? { handoffNote } : {}), updatedAt: new Date().toISOString() };
    this.data = { ...this.data, claims: this.data.claims.map((claim) => claim.id === id ? updated : claim) };
    if (status === "returned") {
      this.updateInternal(current.reportId, { status: "returned" });
      // The claimant got their item back, so their matching lost listing is resolved too.
      for (const lost of this.data.reports.filter((candidate) => candidate.type === "lost" && candidate.reporterId === current.claimantId && ["active", "possible_match"].includes(candidate.status) && (report.relatedLostReportId === candidate.id || matchScore(candidate, report) > 0))) {
        this.updateInternal(lost.id, { status: "returned" });
      }
    }
    else if (status === "rejected") {
      const hasOtherActiveClaim = this.data.claims.some((claim) => claim.id !== id && claim.reportId === current.reportId && !["rejected", "returned"].includes(claim.status));
      if (!hasOtherActiveClaim) this.updateInternal(current.reportId, { status: "active" });
    }
    const claimantNotifications: Partial<Record<ClaimStatus, { title: string; body: string }>> = {
      approved: { title: "Your claim was approved", body: "The finder approved your claim and is arranging the return. Tap for details." },
      handoff: { title: "Ready for pickup", body: handoffNote ? `Your item is waiting at ${handoffNote}. Tap for details.` : "The finder dropped off your item. Tap for details." },
      rejected: { title: "Your claim was not approved", body: "The finder did not approve your ownership claim." },
      returned: { title: "Item returned", body: "The finder marked the item as returned." },
    };
    const claimantNotification = claimantNotifications[status];
    if (claimantNotification) {
      this.addNotification({
        userId: current.claimantId,
        reportId: current.reportId,
        claimId: current.id,
        ...claimantNotification,
        read: false,
        demo: true,
      });
    }
    this.persist();
    return updated;
  }

  addNotification(input: Omit<AppNotification, "id" | "createdAt">) {
    const notification: AppNotification = { ...input, id: uid("notification"), createdAt: new Date().toISOString() };
    this.data = { ...this.data, notifications: [notification, ...this.data.notifications] };
    this.persist();
    return notification;
  }

  markNotificationRead(id: string, actorId: string) {
    const notification = this.data.notifications.find((item) => item.id === id);
    if (!notification || notification.userId !== actorId) return;
    this.data = { ...this.data, notifications: this.data.notifications.map((notification) => notification.id === id ? { ...notification, read: true } : notification) };
    this.persist();
  }

  snapshot() {
    return {
      reports: [...this.data.reports],
      claims: [...this.data.claims],
      notifications: [...this.data.notifications],
    };
  }

  // Shared demo catalog (demoSync.ts). Claim answers travel too, so the finder's phone can
  // review a claim made on the owner's phone.
  syncExport() {
    return { catalog: persistentSnapshot(this.data), claimAnswers: Object.fromEntries(this.claimAnswers) };
  }

  syncReplace(catalog: SyncCatalog, claimAnswers: Record<string, string>) {
    this.data = {
      reports: catalog.reports ?? [],
      claims: catalog.claims ?? [],
      notifications: catalog.notifications ?? [],
    };
    for (const [id, answer] of Object.entries(claimAnswers)) this.claimAnswers.set(id, answer);
    this.persist();
  }
}

export function toPublicReport(report: ItemReport): PublicItemReport {
  const { reporterId: _reporterId, privateDetails: _privateDetails, clientSubmissionId: _clientSubmissionId, location, ...safe } = report;
  const restricted = report.sensitive || report.visibility !== "public";
  return {
    ...safe,
    restrictedProjection: restricted,
    itemName: restricted ? report.category : report.itemName,
    publicDescription: restricted ? "Details hidden for safety" : report.publicDescription,
    photoUrl: restricted ? null : report.photoUrl,
    location: location ? {
      campus: location.campus,
      area: restricted ? location.campus : location.area,
      building: restricted ? undefined : location.building,
      room: undefined,
      source: location.source,
      placeType: location.placeType,
      approximateLabel: restricted ? `On ${location.campus} campus` : location.approximateLabel,
      approximateCoordinates: restricted ? undefined : location.approximateCoordinates,
    } : null,
  };
}

type ReportStore = CatalogSnapshot & {
  currentUserId: string;
  currentUser: DemoUser;
  users: DemoUser[];
  switchUser(id: DemoUser["id"]): void;
  updatePrimaryUser(identity: Pick<DemoUser, "firstName" | "lastName" | "email">): void;
  publicReports: PublicItemReport[];
  createReport(input: Omit<NewReport, "reporterId">): ItemReport;
  updateReport(id: string, updates: Partial<Omit<ItemReport, "id" | "reporterId" | "createdAt">>): ItemReport | undefined;
  closeReport(id: string): ItemReport | undefined;
  createClaim(reportId: string, privateProof?: string): Claim;
  getClaimAnswer(id: string): string | undefined;
  updateClaim(id: string, status: ClaimStatus, handoffNote?: string): Claim | undefined;
  markNotificationRead(id: string): void;
  /** In-app notification for another persona (e.g. the owner of a found ID card). */
  notifyUser(userId: string, reportId: string, title: string, body: string): void;
};

const ReportContext = createContext<ReportStore | null>(null);

const PERSONA_KEY = "where-ru.persona";

/** Which demo persona this phone plays: ?as=jordan (sender) or ?as=maya (receiver), remembered per phone. */
function initialPersona(): DemoUser["id"] {
  const requested = new URLSearchParams(window.location.search).get("as")?.toLowerCase();
  const fromLink = requested === "maya" || requested === "demo-maya" ? "demo-maya" : requested === "jordan" || requested === "demo-jordan" ? "demo-jordan" : null;
  try {
    if (fromLink) localStorage.setItem(PERSONA_KEY, fromLink);
    const saved = fromLink ?? localStorage.getItem(PERSONA_KEY);
    if (saved === "demo-maya" || saved === "demo-jordan") return saved;
  } catch {
    if (fromLink) return fromLink;
  }
  return "demo-jordan";
}

function savePersona(id: DemoUser["id"]) {
  try {
    localStorage.setItem(PERSONA_KEY, id);
  } catch {
    // The persona still applies for this session.
  }
}

export function ReportProvider({ children }: { children: ReactNode }) {
  const repositoryRef = useRef<LocalReportRepository | null>(null);
  if (!repositoryRef.current) repositoryRef.current = new LocalReportRepository();
  const repository = repositoryRef.current;
  const [snapshot, setSnapshot] = useState(() => repository.snapshot());
  const [currentUserId, setCurrentUserId] = useState<DemoUser["id"]>(initialPersona);
  const [users, setUsers] = useState(initialDemoUsers);
  const syncRef = useRef<ReturnType<typeof startDemoSync> | null>(null);
  useEffect(() => {
    const sync = startDemoSync(repository, () => setSnapshot(repository.snapshot()));
    syncRef.current = sync;
    return () => {
      sync.stop();
      syncRef.current = null;
    };
  }, [repository]);
  const refresh = () => {
    setSnapshot(repository.snapshot());
    syncRef.current?.notifyLocalChange();
  };
  const currentUser = users.find((user) => user.id === currentUserId) ?? users[0];
  const value = useMemo<ReportStore>(() => ({
    ...snapshot,
    currentUserId,
    currentUser,
    users,
    switchUser(id) {
      if (users.some((user) => user.id === id)) {
        setCurrentUserId(id);
        savePersona(id);
      }
    },
    updatePrimaryUser(identity) {
      // Onboarding names whichever persona this phone is playing.
      setUsers((current) => current.map((user) => user.id === currentUserId ? { ...user, ...identity } : user));
    },
    publicReports: snapshot.reports
      .filter((report) => report.status !== "closed" && (report.visibility === "public" || report.visibility === "trusted-only" && report.type === "found"))
      .map(toPublicReport),
    createReport(input) {
      const report = repository.create({ ...input, reporterId: currentUserId }, currentUserId);
      refresh();
      return report;
    },
    updateReport(id, updates) {
      const report = repository.update(id, currentUserId, updates);
      refresh();
      return report;
    },
    closeReport(id) {
      const report = repository.close(id, currentUserId);
      refresh();
      return report;
    },
    createClaim(reportId, privateProof) {
      const claim = repository.createClaim(reportId, currentUserId, privateProof);
      refresh();
      return claim;
    },
    getClaimAnswer(id) {
      return repository.getClaimAnswer(id, currentUserId);
    },
    updateClaim(id, status, handoffNote) {
      const claim = repository.updateClaim(id, status, currentUserId, handoffNote);
      refresh();
      return claim;
    },
    markNotificationRead(id) {
      repository.markNotificationRead(id, currentUserId);
      refresh();
    },
    notifyUser(userId, reportId, title, body) {
      repository.addNotification({ userId, reportId, title, body, read: false, demo: true });
      refresh();
    },
  }), [currentUser, currentUserId, repository, snapshot, users]);
  return <ReportContext.Provider value={value}>{children}</ReportContext.Provider>;
}

export function useReports() {
  const value = useContext(ReportContext);
  if (!value) throw new Error("useReports must be used within ReportProvider");
  return value;
}

export function reportStatusLabel(status: ReportStatus) {
  const labels: Record<ReportStatus, string> = {
    active: "Active",
    possible_match: "Possible match",
    claim_under_review: "Claim under review",
    returned: "Returned",
    closed: "Closed",
  };
  return labels[status];
}

export function categoryIcon(category: ReportCategory) {
  const icons: Record<ReportCategory, string> = {
    Electronics: "◉",
    "Wallets/IDs": "▣",
    Keys: "⌘",
    Bags: "▰",
    Clothing: "◇",
    Bottles: "◒",
    "School Supplies": "▤",
    Other: "⌁",
  };
  return icons[category];
}

export const reportCategories: ReportCategory[] = ["Electronics", "Wallets/IDs", "Keys", "Bags", "Clothing", "Bottles", "School Supplies", "Other"];
