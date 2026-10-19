import { api } from "@/api";
import { queryKeys, useApiQuery } from "@/api/queries";

/** One part of a patient's chart; `enabled` false for roles that can't read it. */
export function useChartNotes(patientId: string, enabled: boolean) {
  return useApiQuery(
    queryKeys.patients.chart(patientId, "notes"),
    (signal) =>
      api.GET("/api/v1/patients/{patient_id}/notes", {
        params: { path: { patient_id: patientId } },
        signal,
      }),
    { enabled },
  );
}

export function useChartVitals(patientId: string, enabled: boolean) {
  return useApiQuery(
    queryKeys.patients.chart(patientId, "vitals"),
    (signal) =>
      api.GET("/api/v1/patients/{patient_id}/vitals", {
        params: { path: { patient_id: patientId } },
        signal,
      }),
    { enabled },
  );
}

export function useChartAllergies(patientId: string, enabled: boolean) {
  return useApiQuery(
    queryKeys.patients.chart(patientId, "allergies"),
    (signal) =>
      api.GET("/api/v1/patients/{patient_id}/allergies", {
        params: { path: { patient_id: patientId } },
        signal,
      }),
    { enabled },
  );
}

export function useChartConditions(patientId: string, enabled: boolean) {
  return useApiQuery(
    queryKeys.patients.chart(patientId, "conditions"),
    (signal) =>
      api.GET("/api/v1/patients/{patient_id}/conditions", {
        params: { path: { patient_id: patientId } },
        signal,
      }),
    { enabled },
  );
}
