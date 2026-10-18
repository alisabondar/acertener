import { createApiClient } from "./client";
import { personaStore } from "./persona";

/** The app's single API client. */
export const api = createApiClient({ getPersona: personaStore.get });
