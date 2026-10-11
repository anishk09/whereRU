// Keeps this phone's report catalog in step with the backend's shared demo catalog, so a sender
// phone and a receiver phone see the same reports, claims and notifications.
// - Off automatically when the backend isn't running (Figma preview) or demo sync is disabled.
// - Local changes are pushed right away; the server merges by record, newest wins.
// - Other phones' changes arrive by polling every few seconds.
// - Re-seeding the server (python tools/seed_demo.py) starts a new generation; phones on an
//   older generation drop their local copy and take the server's.
import * as api from "./api";
import type { AppNotification, Claim, ItemReport } from "./reports";

export type SyncCatalog = { reports: ItemReport[]; claims: Claim[]; notifications: AppNotification[] };

export interface SyncableRepository {
  syncExport(): { catalog: SyncCatalog; claimAnswers: Record<string, string> };
  syncReplace(catalog: SyncCatalog, claimAnswers: Record<string, string>): void;
}

const GENERATION_KEY = "where-ru.sync.generation";
const POLL_MS = 2500;

function savedGeneration(): string | null {
  try {
    return localStorage.getItem(GENERATION_KEY);
  } catch {
    return null;
  }
}

function saveGeneration(value: string) {
  try {
    localStorage.setItem(GENERATION_KEY, value);
  } catch {
    // Without storage the phone simply re-adopts the server copy after a reload.
  }
}

export function startDemoSync(repository: SyncableRepository, onRemoteChange: () => void) {
  let generation = savedGeneration();
  let version = -1;
  let dirty = false;
  let disabled = false;
  let stopped = false;
  let chain: Promise<void> = Promise.resolve();

  const apply = (state: api.DemoCatalogState) => {
    if (stopped || !state.generation || !state.catalog) return;
    const sameGeneration = state.generation === generation;
    generation = state.generation;
    saveGeneration(state.generation);
    if (sameGeneration && state.version === version) return;
    version = state.version;
    repository.syncReplace(state.catalog as SyncCatalog, state.claim_answers ?? {});
    onRemoteChange();
  };

  const push = async () => {
    if (disabled || stopped || !dirty) return;
    dirty = false;
    const { catalog, claimAnswers } = repository.syncExport();
    const state = await api.pushDemoCatalog({ generation, catalog, claim_answers: claimAnswers });
    if (!state) {
      dirty = true;
      return;
    }
    if (state.accepted === false) {
      // The server was re-seeded: its data replaces this phone's.
      dirty = false;
      apply(state);
      return;
    }
    if (!dirty) apply(state);
  };

  const pull = async () => {
    if (disabled || stopped) return;
    const state = await api.getDemoCatalog(generation && version >= 0 ? { generation, version } : undefined);
    if (!state || state.unchanged) return;
    if (!state.generation) {
      // Nothing on the server yet: share this phone's catalog as the starting point.
      dirty = true;
      await push();
      return;
    }
    if (state.generation !== generation) {
      dirty = false;
      apply(state);
      return;
    }
    if (!dirty) apply(state);
  };

  const run = (task: () => Promise<void>) => {
    chain = chain.then(task).catch((error) => {
      if (error instanceof api.ApiError && error.status === 404) disabled = true;
      else console.warn("Demo sync skipped:", error);
    });
  };

  const tick = () => run(() => (dirty ? push() : pull()));
  const onVisible = () => {
    if (document.visibilityState === "visible") tick();
  };
  const timer = window.setInterval(tick, POLL_MS);
  document.addEventListener("visibilitychange", onVisible);
  tick();

  return {
    notifyLocalChange() {
      dirty = true;
      run(push);
    },
    stop() {
      stopped = true;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    },
  };
}
