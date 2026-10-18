import { createContext, useContext } from "react";

import type { components } from "@/api/schema";

type Schemas = components["schemas"];
export type Me = Schemas["MeOut"];
export type Permission = Schemas["Permission"];
export type Persona = Schemas["UserOut"];

export type CurrentUser = {
  me: Me;
  personas: Persona[];
  /** Set while a switch is loading; `me` is still the previous persona until it finishes. */
  switchingTo: Persona | null;
  /** Act as someone else. Everything cached as the previous persona (except the persona list) is discarded first. */
  switchPersona: (personaId: string) => Promise<void>;
};

export const CurrentUserContext = createContext<CurrentUser | null>(null);

export function useCurrentUser(): CurrentUser {
  const user = useContext(CurrentUserContext);
  if (!user) throw new Error("useCurrentUser must be used inside <CurrentUserProvider>");
  return user;
}

/** Whether the current user may do something. UX only: the API enforces every permission. */
export function usePermission(permission: Permission): boolean {
  return useCurrentUser().me.permissions.includes(permission);
}
