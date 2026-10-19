import { useParams } from "react-router";

import { api } from "@/api";
import { queryKeys, useApiQuery } from "@/api/queries";
import { usePermission } from "@/auth/context";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { ComponentProps } from "react";
import { ListError } from "@/patients/ListStates";

import { AccessHistoryTab } from "./AccessHistoryTab";
import { AllergiesConditionsTab } from "./AllergiesConditionsTab";
import { ChartHeader } from "./ChartHeader";
import { ContactTab } from "./ContactTab";
import { NotesTab } from "./NotesTab";
import { OverviewTab } from "./OverviewTab";
import { VitalsTab } from "./VitalsTab";

export function PatientChart() {
  const { patientId = "" } = useParams();
  const clinical = usePermission("VIEW_CLINICAL");
  const canSeeAccess = usePermission("VIEW_PATIENT_ACCESS_LOG");
  const detail = useApiQuery(queryKeys.patients.detail(patientId), (signal) =>
    api.GET("/api/v1/patients/{patient_id}", {
      params: { path: { patient_id: patientId } },
      signal,
    }),
  );

  if (detail.error) {
    return (
      <ListError error={detail.error} what="this chart" onRetry={() => void detail.refetch()} />
    );
  }
  if (!detail.data) {
    return (
      <div role="status" aria-label="Loading chart" className="space-y-4">
        <Skeleton className="h-20 w-full rounded-xl" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }
  const patient = detail.data;

  return (
    <div className="space-y-5">
      <ChartHeader patient={patient} showAllergies={clinical} />
      {/* Front desk has no clinical overview, so their chart opens on Contact. */}
      <Tabs defaultValue={clinical ? "overview" : "contact"}>
        <TabsList>
          {clinical && <ChartTab value="overview">Overview</ChartTab>}
          <ChartTab value="contact">Contact</ChartTab>
          {clinical && <ChartTab value="notes">Notes</ChartTab>}
          {clinical && <ChartTab value="vitals">Vitals</ChartTab>}
          {clinical && <ChartTab value="allergies">Allergies & conditions</ChartTab>}
          {canSeeAccess && <ChartTab value="access">Access history</ChartTab>}
        </TabsList>
        {clinical && (
          <TabsContent value="overview" className="pt-4">
            <OverviewTab patientId={patient.id} />
          </TabsContent>
        )}
        <TabsContent value="contact" className="pt-4">
          <ContactTab patient={patient} />
        </TabsContent>
        {clinical && (
          <>
            <TabsContent value="notes" className="pt-4">
              <NotesTab patientId={patient.id} />
            </TabsContent>
            <TabsContent value="vitals" className="pt-4">
              <VitalsTab patientId={patient.id} />
            </TabsContent>
            <TabsContent value="allergies" className="pt-4">
              <AllergiesConditionsTab patientId={patient.id} />
            </TabsContent>
          </>
        )}
        {canSeeAccess && (
          <TabsContent value="access" className="pt-4">
            <AccessHistoryTab patientId={patient.id} />
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}

/** A chart tab whose selected state is unmistakable: raised, white, and in the accent colour. */
function ChartTab(props: ComponentProps<typeof TabsTrigger>) {
  return (
    <TabsTrigger
      {...props}
      className="data-[state=active]:bg-card data-[state=active]:text-brand data-[state=active]:shadow-sm"
    />
  );
}
