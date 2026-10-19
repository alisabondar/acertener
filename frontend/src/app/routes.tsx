import type { RouteObject } from "react-router";

import { CurrentUserProvider } from "@/auth/CurrentUserProvider";
import { RequirePermission } from "@/auth/RequirePermission";
import { Home } from "@/pages/Home";
import { NotFound } from "@/pages/NotFound";
import { RouteError } from "@/pages/RouteError";

import { AuditLog, EditPatient, NewPatient, PatientChart, PatientList } from "./lazyPages";
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
                <PatientList />
              </RequirePermission>
            ),
          },
          {
            path: "patients/new",
            element: (
              <RequirePermission permission="CREATE_PATIENT">
                <NewPatient />
              </RequirePermission>
            ),
          },
          {
            path: "patients/:patientId/edit",
            element: (
              <RequirePermission permission="EDIT_DEMOGRAPHICS">
                <EditPatient />
              </RequirePermission>
            ),
          },
          {
            path: "patients/:patientId",
            element: (
              <RequirePermission permission="VIEW_DEMOGRAPHICS">
                <PatientChart />
              </RequirePermission>
            ),
          },
          {
            path: "admin/audit",
            element: (
              <RequirePermission permission="VIEW_AUDIT_LOG">
                <AuditLog />
              </RequirePermission>
            ),
          },
          { path: "*", element: <NotFound /> },
        ],
      },
    ],
  },
];
