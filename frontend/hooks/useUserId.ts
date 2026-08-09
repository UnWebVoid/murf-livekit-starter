'use client';

import { useEffect, useState } from 'react';

const STORAGE_KEY = 'jan_sathi_user_id';

/** Generate a UUID v4 using crypto.randomUUID when available, Math.random as fallback. */
function generateUUID(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * React hook — returns the stable UUID for the current browser/device.
 *
 * On first visit: generates a new UUID v4 and persists it in localStorage.
 * On subsequent visits: returns the same UUID from localStorage.
 *
 * This UUID becomes the LiveKit participantIdentity so Jan Sathi can link
 * memory records to the same caller across completely separate calls.
 *
 * Returns null during SSR / before hydration.
 */
export function useUserId(): string | null {
  const [userId, setUserId] = useState<string | null>(null);

  useEffect(() => {
    setUserId(getUserId());
  }, []);

  return userId;
}

/**
 * Synchronous getter — safe to call inside async callbacks and useMemo.
 * Creates and persists the UUID on first call (client-side only).
 * Returns a transient UUID if localStorage is unavailable (e.g. private mode).
 */
export function getUserId(): string {
  try {
    let id = localStorage.getItem(STORAGE_KEY);
    if (!id) {
      id = generateUUID();
      localStorage.setItem(STORAGE_KEY, id);
    }
    return id;
  } catch {
    // localStorage unavailable — return a transient UUID for this session
    return generateUUID();
  }
}
