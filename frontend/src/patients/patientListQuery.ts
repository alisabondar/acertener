import { api } from "@/api";
import { queryKeys } from "@/api/queries";

import type { SearchTerms } from "./searchTerms";
import type { PatientListParams } from "./usePatientListParams";

/** The list request for these params: a search when there are terms, otherwise a browse. */
export function patientListQuery(params: PatientListParams, terms: SearchTerms | null) {
  return {
    queryKey: terms ? queryKeys.patients.search(params, terms) : queryKeys.patients.list(params),
    call: (signal: AbortSignal) =>
      terms
        ? api.POST("/api/v1/patients/search", { params: { query: params }, body: terms, signal })
        : api.GET("/api/v1/patients", { params: { query: params }, signal }),
  };
}
