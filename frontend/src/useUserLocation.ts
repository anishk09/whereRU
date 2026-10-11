import { useEffect, useState } from "react";
import type { LngLat } from "./nearby";

export type UserLocation = {
  /** off: not asked yet · asking: waiting for the first fix · on · denied · unavailable (no GPS, timeout, or no browser support) */
  status: "off" | "asking" | "on" | "denied" | "unavailable";
  position: LngLat | null;
  enable: () => void;
};

const KEY = "where-ru.location.on";

function remembered() {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

/** The phone's position, only after the person opts in (remembered on this phone). */
export function useUserLocation(): UserLocation {
  const supported = typeof navigator !== "undefined" && "geolocation" in navigator;
  const [attempt, setAttempt] = useState(() => (supported && remembered() ? 1 : 0));
  const [status, setStatus] = useState<UserLocation["status"]>(supported ? "off" : "unavailable");
  const [position, setPosition] = useState<LngLat | null>(null);

  useEffect(() => {
    if (!attempt || !supported) return;
    setStatus((current) => (current === "on" ? current : "asking"));
    const watch = navigator.geolocation.watchPosition(
      (fix) => {
        setPosition([fix.coords.longitude, fix.coords.latitude]);
        setStatus("on");
        try {
          localStorage.setItem(KEY, "1");
        } catch {
          // Only means the phone asks again next time.
        }
      },
      (error) => {
        setPosition(null);
        setStatus(error.code === error.PERMISSION_DENIED ? "denied" : "unavailable");
        if (error.code === error.PERMISSION_DENIED) {
          try {
            localStorage.removeItem(KEY);
          } catch {
            // Nothing to forget.
          }
        }
      },
      { enableHighAccuracy: false, maximumAge: 30_000, timeout: 15_000 },
    );
    return () => navigator.geolocation.clearWatch(watch);
  }, [attempt, supported]);

  return { status, position, enable: () => supported && setAttempt((n) => n + 1) };
}
