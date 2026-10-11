// Thin client for the Flask API (backend/). All requests go to /api, which the Vite dev
// server proxies to Flask on port 5001, so the session cookie is same-origin.
// When the backend isn't running (Figma preview, offline demo), isOnline() is false and the
// app keeps using its built-in demo data.

let csrfToken = "";
let lastEmail = "";
let online: boolean | null = null;
let offlineCheckedAt = 0;
let draftFoundId: number | null = null;

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(method: string, path: string, body?: unknown, timeoutMs = 30000): Promise<T> {
  const headers: Record<string, string> = {};
  let payload: BodyInit | undefined;
  if (body instanceof FormData) payload = body;
  else if (body !== undefined || method !== "GET") {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body ?? {});
  }
  if (method !== "GET" && csrfToken) headers["X-CSRF-Token"] = csrfToken;
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(path, { method, headers, body: payload, credentials: "include", signal: controller.signal });
  } catch (error) {
    if (controller.signal.aborted) throw new ApiError(408, "The server took too long to answer.");
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(response.status, data.message || data.error || `Request failed (${response.status})`);
  return data as T;
}

/** True when the Flask backend answers. A "yes" is remembered; a "no" is re-checked after a
 * few seconds, so starting the backend after the page loaded still works. */
export async function isOnline(): Promise<boolean> {
  if (online) return true;
  if (online === false && Date.now() - offlineCheckedAt < 5000) return false;
  try {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 4000);
    const response = await fetch("/api/health", { signal: controller.signal });
    window.clearTimeout(timer);
    const data = await response.json();
    online = response.ok && data.app === "WhereRU?";
  } catch {
    online = false;
  }
  if (!online) offlineCheckedAt = Date.now();
  return online;
}

export type ApiUser = { id: number; email: string; display_name: string; reputation: number };

/** Signs in for the demo. Uses the dev-only demo login so no email code is needed. */
export async function signIn(email: string, displayName = ""): Promise<ApiUser | null> {
  if (!(await isOnline())) return null;
  lastEmail = email;
  const data = await request<{ user: ApiUser; csrf_token: string }>("POST", "/api/auth/demo-login", { email, display_name: displayName });
  csrfToken = data.csrf_token;
  return data.user;
}

/** Makes sure there is a backend session, signing in as the demo user if needed. */
export async function ensureSession(): Promise<boolean> {
  if (!(await isOnline())) return false;
  if (csrfToken) return true;
  try {
    await signIn(lastEmail || "demo@scarletmail.rutgers.edu", "Demo");
    return true;
  } catch {
    return false;
  }
}

export async function updateName(displayName: string) {
  if (!(await ensureSession())) return;
  await request("PATCH", "/api/me", { display_name: displayName });
}

// ----- Reports -----

export type ApiCategory = "bottle" | "electronics" | "clothing" | "bag" | "keys" | "wallet" | "id_card" | "financial_card" | "cash" | "other";
const SENSITIVE: ApiCategory[] = ["keys", "wallet", "id_card", "financial_card", "cash"];

/** Maps the app's category labels to the backend's category values. */
export function toApiCategory(label: string): ApiCategory {
  const value = label.toLowerCase();
  if (value.includes("bottle")) return "bottle";
  if (value.includes("electronic") || value.includes("laptop") || value.includes("phone") || value.includes("airpod")) return "electronics";
  if (value.includes("cloth") || value.includes("hoodie") || value.includes("jacket")) return "clothing";
  if (value.includes("bag") || value.includes("backpack")) return "bag";
  if (value.includes("key")) return "keys";
  if (value.includes("wallet") || /\bid\b/.test(value)) return "wallet";
  return "other";
}

export type ApiListing = { id: number; type: "LOST" | "FOUND"; title: string; status: string; visibility: string; location: string; campus: string; category: ApiCategory };

type ReportFields = {
  title?: string;
  description?: string;
  private_description?: string;
  category?: ApiCategory;
  campus?: string;
  location?: string;
  visibility?: "PUBLIC" | "PRIVATE";
};

function withPrivacy<T extends ReportFields>(fields: T): T {
  // The backend requires sensitive categories to stay private.
  if (fields.category && SENSITIVE.includes(fields.category)) return { ...fields, visibility: "PRIVATE" };
  return fields;
}

/** A private FOUND report that holds the finder's photos while they fill in details. */
async function ensureDraftFound(): Promise<number> {
  if (draftFoundId) return draftFoundId;
  await ensureSession();
  const listing = await request<ApiListing>("POST", "/api/listings", {
    type: "FOUND",
    title: "Found item",
    category: "other",
    occurred_at: new Date().toISOString(),
    visibility: "PRIVATE",
  });
  draftFoundId = listing.id;
  return draftFoundId;
}

/** Call when the finder starts a new report, so photos don't attach to the previous one. */
export function startNewFoundReport() {
  draftFoundId = null;
}

async function uploadToDraft(photo: File): Promise<{ listingId: number; imageId: number }> {
  const listingId = await ensureDraftFound();
  const form = new FormData();
  form.append("image", photo);
  const image = await request<{ id: number }>("POST", `/api/listings/${listingId}/images`, form);
  return { listingId, imageId: image.id };
}

export type ApiItemSuggestion = { title: string; description: string; category: ApiCategory; attributes: { color: string | null } };

export async function analyzeItemPhoto(photo: File) {
  const { listingId, imageId } = await uploadToDraft(photo);
  return request<{ mode: string; suggestion: ApiItemSuggestion }>("POST", `/api/listings/${listingId}/analyze`, { consent_to_ai: true, image_ids: [imageId] });
}

export type ApiRoomCandidate = { room_id: string; building: string; room: string; campus: string; evidence: string[]; conflicts?: string[]; confident?: boolean };

export type ApiRoomResult = { mode: string; candidates: ApiRoomCandidate[]; message?: string };

/** Scans a room photo. The server compares it in memory and does not keep it. */
export async function recognizeRoomPhoto(photo: File, campus: string | null) {
  await ensureSession();
  const form = new FormData();
  form.append("image", photo);
  if (campus) form.append("campus", campus);
  return request<ApiRoomResult>("POST", "/api/recognize-room", form, 45000);
}

/** Fills in the draft found report and makes it visible to matching. Returns its ID. */
export async function publishFoundReport(fields: ReportFields): Promise<number | null> {
  if (!(await ensureSession())) return null;
  const listingId = await ensureDraftFound();
  await request("PATCH", `/api/listings/${listingId}`, withPrivacy({ visibility: "PUBLIC", ...fields }));
  draftFoundId = null;
  return listingId;
}

export async function createLostReport(fields: ReportFields): Promise<number | null> {
  if (!(await ensureSession())) return null;
  const listing = await request<ApiListing>("POST", "/api/listings", withPrivacy({
    type: "LOST",
    occurred_at: new Date().toISOString(),
    visibility: "PUBLIC",
    ...fields,
  }));
  return listing.id;
}

export type ApiMatch = {
  id: number;
  found_id: number;
  lost_id: number;
  reasons: string[];
  candidate: { title: string; location: string; campus: string; category: ApiCategory };
};

export async function myMatches(): Promise<ApiMatch[]> {
  if (!(await ensureSession())) return [];
  return (await request<{ matches: ApiMatch[] }>("GET", "/api/matches")).matches;
}

