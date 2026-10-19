import { lazy } from "react";

// Pages load on first visit, so the first screen doesn't download every page.
export const PatientList = lazy(() =>
  import("@/patients/PatientList").then((m) => ({ default: m.PatientList })),
);
export const MyDay = lazy(() => import("@/home/MyDay").then((m) => ({ default: m.MyDay })));
export const PatientChart = lazy(() =>
  import("@/chart/PatientChart").then((m) => ({ default: m.PatientChart })),
);
export const NewPatient = lazy(() =>
  import("@/patients/PatientForm").then((m) => ({ default: m.NewPatient })),
);
export const EditPatient = lazy(() =>
  import("@/patients/PatientForm").then((m) => ({ default: m.EditPatient })),
);
export const AuditLog = lazy(() =>
  import("@/admin/AuditLog").then((m) => ({ default: m.AuditLog })),
);
