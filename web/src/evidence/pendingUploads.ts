import { api, ApiError, type EvidencePackage } from "../api/client";
import type { EvidenceItem } from "../api/types";

// A captured package is written to IndexedDB before upload and removed only
// once the server has it, so a dropped connection or a closed tab never
// silently loses the photo or its coordinates. Re-sending is safe: the
// package's client id makes the server return the first row, not a copy.

export interface PendingUpload {
  id: string; // = pkg.clientSubmissionId
  issueId: number;
  reportId?: number;
  pkg: EvidencePackage;
  savedAt: string;
}

const DB_NAME = "wardsentry-evidence";
const STORE = "pending";
const memory = new Map<string, PendingUpload>(); // if IndexedDB is unavailable

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: "id" });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function withStore<T>(mode: IDBTransactionMode, run: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await openDb();
  try {
    return await new Promise<T>((resolve, reject) => {
      const req = run(db.transaction(STORE, mode).objectStore(STORE));
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  } finally {
    db.close();
  }
}

export async function savePending(entry: PendingUpload): Promise<void> {
  memory.set(entry.id, entry);
  try {
    await withStore("readwrite", (s) => s.put(entry));
  } catch {
    /* kept in memory for this session */
  }
}

async function removePending(id: string): Promise<void> {
  memory.delete(id);
  try {
    await withStore("readwrite", (s) => s.delete(id));
  } catch {
    /* nothing persisted */
  }
}

export async function listPending(): Promise<PendingUpload[]> {
  try {
    const stored = await withStore<PendingUpload[]>("readonly", (s) => s.getAll());
    stored.forEach((e) => memory.set(e.id, e));
  } catch {
    /* memory only */
  }
  return [...memory.values()].sort((a, b) => a.savedAt.localeCompare(b.savedAt));
}

export type UploadResult =
  | { ok: true; item: EvidenceItem }
  | { ok: false; retryable: boolean; message: string };

/** Sends one saved package. Network and server errors keep it for retry;
 * a definite refusal (window closed, already has a photo) discards it. */
export async function uploadPending(entry: PendingUpload): Promise<UploadResult> {
  try {
    const item = await api.submitEvidence(entry.issueId, entry.pkg, entry.reportId);
    await removePending(entry.id);
    return { ok: true, item };
  } catch (err) {
    if (err instanceof ApiError && err.status >= 400 && err.status < 500 && err.status !== 401 && err.status !== 408) {
      await removePending(entry.id);
      return { ok: false, retryable: false, message: err.message };
    }
    const offline = typeof navigator !== "undefined" && !navigator.onLine;
    return {
      ok: false,
      retryable: true,
      message: offline
        ? "You're offline. The photo and its location are saved on this device - send them when you're back online."
        : "The photo couldn't be sent. It's saved on this device - try again.",
    };
  }
}

export async function captureAndUpload(issueId: number, pkg: EvidencePackage, reportId?: number): Promise<UploadResult> {
  const entry: PendingUpload = { id: pkg.clientSubmissionId, issueId, reportId, pkg, savedAt: new Date().toISOString() };
  await savePending(entry);
  return uploadPending(entry);
}
