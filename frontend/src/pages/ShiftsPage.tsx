import { useQuery } from "@tanstack/react-query";

import { api } from "../api";
import { Card, ErrorState, LoadingState, PageIntro } from "../components/ui";
import type { Shift } from "../types";

export function ShiftsPage() {
  const shifts = useQuery({
    queryKey: ["shifts"],
    queryFn: () => api<Shift[]>("/api/shifts"),
  });

  if (shifts.isLoading) return <LoadingState label="Loading shifts…" />;
  if (shifts.isError) return <ErrorState error={shifts.error} />;

  return (
    <div>
      <PageIntro title="Shifts" description={`${shifts.data!.length} shift instances from the API.`} />
      <div className="grid gap-3">
        {shifts.data!.map((shift) => (
          <Card key={shift.id}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-semibold">{shift.label}</p>
                <p className="mt-1 text-sm text-stone-600 dark:text-stone-400">
                  {shift.local_date} · {shift.start_local}–{shift.end_local}
                  {shift.overnight ? " (overnight)" : ""}
                </p>
              </div>
              <div className="text-right text-sm">
                <p className="tabular font-medium">need {shift.required_count}</p>
                <p className="text-stone-500">{shift.duration_hours}h</p>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-2 text-xs">
              {shift.is_night ? <span className="rounded-full bg-stone-900/10 px-2 py-0.5 dark:bg-white/10">night</span> : null}
              {shift.is_weekend ? <span className="rounded-full bg-stone-900/10 px-2 py-0.5 dark:bg-white/10">weekend</span> : null}
              {shift.skill_requirements.map((req, index) => (
                <span
                  key={`${shift.id}-${index}`}
                  className="rounded-full bg-amber-100 px-2 py-0.5 text-amber-900 dark:bg-amber-950 dark:text-amber-200"
                >
                  {req.label} ×{req.min_count}
                </span>
              ))}
            </div>
          </Card>
        ))}
        {shifts.data!.length === 0 ? (
          <Card className="text-sm text-stone-500">No shifts loaded. Use Scenarios to seed demo data.</Card>
        ) : null}
      </div>
    </div>
  );
}
