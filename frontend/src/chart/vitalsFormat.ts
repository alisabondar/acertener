import type { components } from "@/api/schema";

type Vitals = components["schemas"]["VitalsOut"];

export function formatBp(v: Pick<Vitals, "bp_systolic" | "bp_diastolic">): string {
  return v.bp_systolic && v.bp_diastolic ? `${v.bp_systolic}/${v.bp_diastolic}` : "—";
}

/** Adult reference ranges, for flagging readings worth a second look (not for diagnosis). */
export function isAbnormal(field: keyof Vitals, value: number | string | null): boolean {
  if (value === null || value === undefined) return false;
  const n = Number(value);
  switch (field) {
    case "bp_systolic":
      return n >= 140 || n < 90;
    case "bp_diastolic":
      return n >= 90 || n < 60;
    case "heart_rate":
      return n > 100 || n < 50;
    case "respiratory_rate":
      return n > 20 || n < 12;
    case "spo2":
      return n < 92;
    case "temperature_c":
      return n >= 38 || n < 35;
    default:
      return false;
  }
}
