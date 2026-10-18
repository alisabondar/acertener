import { Navigate } from "react-router";

import { usePermission } from "@/auth/context";

import { Placeholder } from "./Placeholder";

/** "My day" for anyone who works visits; admin has none, so lands on the audit log. */
export function Home() {
  const worksVisits = usePermission("SCHEDULE_VISITS");
  const canAudit = usePermission("VIEW_AUDIT_LOG");
  if (worksVisits) return <Placeholder title="My day" note="Today's visits and your patients." />;
  return <Navigate to={canAudit ? "/admin/audit" : "/patients"} replace />;
}
