import type { ReactNode } from "react";

import { Forbidden } from "@/pages/Forbidden";

import { type Permission, usePermission } from "./context";

/** Route guard for the UI only; the API refuses the same requests regardless. */
export function RequirePermission({
  permission,
  children,
}: {
  permission: Permission;
  children: ReactNode;
}) {
  return usePermission(permission) ? children : <Forbidden />;
}
