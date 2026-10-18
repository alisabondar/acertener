import type { RouteObject } from "react-router";

import { NotFound } from "@/pages/NotFound";
import { Placeholder } from "@/pages/Placeholder";
import { RouteError } from "@/pages/RouteError";

import { Shell } from "./Shell";

export const appRoutes: RouteObject[] = [
  {
    element: <Shell />,
    errorElement: <RouteError />,
    children: [
      {
        // A second boundary inside the shell keeps the navigation visible when a page fails.
        errorElement: <RouteError />,
        children: [
          {
            index: true,
            element: <Placeholder title="My day" note="Today's visits and your patients." />,
          },
          {
            path: "patients",
            element: <Placeholder title="Patients" note="Search and browse patients." />,
          },
          {
            path: "patients/new",
            element: <Placeholder title="New patient" note="Register a patient." />,
          },
          {
            path: "patients/:patientId",
            element: <Placeholder title="Patient chart" note="Demographics and clinical record." />,
          },
          {
            path: "admin/audit",
            element: <Placeholder title="Audit log" note="Who accessed what, and when." />,
          },
          { path: "*", element: <NotFound /> },
        ],
      },
    ],
  },
];
