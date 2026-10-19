import type { components } from "@/api/schema";
import { Fields, Panel } from "@/components/Fields";

type Patient = components["schemas"]["PatientDetail"];

export function ContactTab({ patient }: { patient: Patient }) {
  const cityLine = [patient.city, [patient.state, patient.postal_code].filter(Boolean).join(" ")]
    .filter(Boolean)
    .join(", ");
  const address = [patient.address_line1, patient.address_line2, cityLine].filter(Boolean);
  return (
    <Panel title="Contact">
      <Fields
        items={[
          { label: "Phone", value: patient.phone },
          { label: "Email", value: patient.email },
          {
            label: "Address",
            value: address.length > 0 && address.map((line) => <div key={line}>{line}</div>),
          },
        ]}
      />
    </Panel>
  );
}
