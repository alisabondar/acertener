import { lazy } from "react";

// Pages load on first visit, so the first screen doesn't download every page.
export const PatientList = lazy(() =>
  import("@/patients/PatientList").then((m) => ({ default: m.PatientList })),
);
export const MyDay = lazy(() => import("@/home/MyDay").then((m) => ({ default: m.MyDay })));
