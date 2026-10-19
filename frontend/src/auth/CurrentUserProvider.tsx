import { useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useCallback, useMemo, useSyncExternalStore } from "react";

import { api } from "@/api";
import { personaStore } from "@/api/persona";
import { queryKeys, useApiQuery } from "@/api/queries";
import { AppSkeleton } from "@/components/PageSkeleton";

import { type CurrentUser, CurrentUserContext } from "./context";

/**
 * Resolves who the app is acting as before rendering anything role-dependent. With no persona
 * chosen yet, it acts as the first one the API offers (Dr. Chen).
 */
export function CurrentUserProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const personaId = useSyncExternalStore(personaStore.subscribe, personaStore.get);

  const personas = useApiQuery(queryKeys.personas(), async (signal) => {
    const response = await api.GET("/api/v1/personas", { signal });
    const first = response.data?.[0];
    if (!first) throw new Error("No demo personas found; seed the database");
    if (!personaStore.get()) personaStore.set(first.id);
    return response;
  });
  const me = useApiQuery(
    queryKeys.me(personaId ?? ""),
    (signal) => api.GET("/api/v1/auth/me", { signal }),
    { enabled: personaId !== null, keepPrevious: true },
  );

  const switchPersona = useCallback(
    async (nextId: string) => {
      await queryClient.cancelQueries();
      personaStore.set(nextId);
      // The persona list is the same for everyone; everything else may be someone's data.
      queryClient.removeQueries({ predicate: ({ queryKey }) => queryKey[0] !== "personas" });
    },
    [queryClient],
  );

  const switchingTo = me.isPlaceholderData
    ? (personas.data?.find((persona) => persona.id === personaId) ?? null)
    : null;
  const value = useMemo<CurrentUser | null>(
    () =>
      me.data && personas.data
        ? { me: me.data, personas: personas.data, switchingTo, switchPersona }
        : null,
    [me.data, personas.data, switchingTo, switchPersona],
  );

  const error = personas.error ?? me.error;
  if (error) throw error;
  if (!value) return <AppSkeleton />;
  return <CurrentUserContext value={value}>{children}</CurrentUserContext>;
}
