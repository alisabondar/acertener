/** The persona requests act as. In memory only: demo identity never touches storage. */
let current: string | null = null;

export const personaStore = {
  get: (): string | null => current,
  set: (personaId: string | null): void => {
    current = personaId;
  },
};
