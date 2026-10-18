/** The persona requests act as. In memory only: demo identity never touches storage. */
let current: string | null = null;
const listeners = new Set<() => void>();

export const personaStore = {
  get: (): string | null => current,
  set: (personaId: string | null): void => {
    current = personaId;
    for (const listener of listeners) listener();
  },
  /** For useSyncExternalStore: re-render whenever the persona changes. */
  subscribe: (listener: () => void): (() => void) => {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};
