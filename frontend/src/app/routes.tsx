import type { RouteObject } from "react-router";

import { CurrentUserProvider } from "@/auth/CurrentUserProvider";
import { RequirePermission } from "@/auth/RequirePermission";
import { Home } from "@/pages/Home";
import { NotFound } from "@/pages/NotFound";
import { Placeholder } from "@/pages/Placeholder";
import { RouteError } from "@/pages/RouteError";

import { Shell } from "./Shell";

export const appRoutes: RouteObject[] = [
  {
    element: (
      <CurrentUserProvider>
        <Shell />
      </CurrentUserProvider>
    ),
    errorElement: <RouteError />,
    children: [
      {
        // A second boundary inside the shell keeps the navigation visible when a page fails.
        errorElement: <RouteError />,
        children: [
          { index: true, element: <Home /> },
          {
            path: "patients",
            element: (
              <RequirePermission permission="VIEW_DEMOGRAPHICS">
                <Placeholder title="Patients" note="Search and browse patients." />
              </RequirePermission>
            ),
          },
          {
            path: "patients/new",
            element: (
              <RequirePermission permission="CREATE_PATIENT">
                <Placeholder title="New patient" note="Register a patient." />
              </RequirePermission>
            ),
          },
          {
            path: "patients/:patientId",
            element: (
              <RequirePermission permission="VIEW_DEMOGRAPHICS">
                <Placeholder title="Patient chart" note="Demographics and clinical record." />
              </RequirePermission>
            ),
          },
          {
            path: "admin/audit",
            element: (
              <RequirePermission permission="VIEW_AUDIT_LOG">
                <Placeholder title="Audit log" note="Who accessed what, and when." />
              </RequirePermission>
            ),
          },
          { path: "*", element: <NotFound /> },
        ],
      },
    ],
  },
];
