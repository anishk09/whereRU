// Distances and "near you" counts, shared by match alerts and the map screen.
import type { CampusId } from "./roomRecognition";

export type LngLat = [number, number];

/** Walking pace used across the app for "N min walk". */
export const WALK_METERS_PER_MIN = 80;
/** "Near you" = within a 5 minute walk. */
export const NEAR_RADIUS_METERS = 5 * WALK_METERS_PER_MIN;
/** Farther than this from every campus counts as off campus; the map then uses the chosen campus instead. */
export const OFF_CAMPUS_METERS = 3000;

export function metersBetween([lng1, lat1]: LngLat, [lng2, lat2]: LngLat) {
  const rad = Math.PI / 180, dLat = (lat2 - lat1) * rad, dLng = (lng2 - lng1) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * 6_371_000 * Math.asin(Math.sqrt(h));
}

export function walkMinutes(meters: number) {
  return Math.max(1, Math.round(meters / WALK_METERS_PER_MIN));
}

export function nearestCampusTo(point: LngLat, centers: Record<CampusId, LngLat>) {
  let best: { campus: CampusId; meters: number } | null = null;
  for (const [campus, center] of Object.entries(centers) as [CampusId, LngLat][]) {
    const meters = metersBetween(point, center);
    if (!best || meters < best.meters) best = { campus, meters };
  }
  return best;
}

type Locatable = { type: "lost" | "found"; status: string; location: { approximateCoordinates?: LngLat } | null };

/** Open reports (not returned or closed) within `radius` of `origin`, nearest first. */
export function reportsNear<T extends Locatable>(reports: T[], origin: LngLat, radius = NEAR_RADIUS_METERS) {
  return reports
    .filter((report) => !["returned", "closed"].includes(report.status) && report.location?.approximateCoordinates)
    .map((report) => ({ report, meters: metersBetween(origin, report.location!.approximateCoordinates!) }))
    .filter(({ meters }) => meters <= radius)
    .sort((a, b) => a.meters - b.meters);
}
