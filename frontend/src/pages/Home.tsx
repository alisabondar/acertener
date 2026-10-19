import { Navigate } from "react-router";

import { MyDay } from "@/app/lazyPages";
import { usePermission } from "@/auth/context";

/** "My day" for anyone who works visits; admin has none, so lands on the audit log. */
export function Home() {
  const worksVisits = usePermission("SCHEDULE_VISITS");
  const canAudit = usePermission("VIEW_AUDIT_LOG");
  if (worksVisits) return <MyDay />;
  return <Navigate to={canAudit ? "/admin/audit" : "/patients"} replace />;
}
