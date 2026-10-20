import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "../api";
import { Button, Card, EmptyState, ErrorState, LoadingState, PageIntro, StatusBadge } from "../components/ui";
import type { Schedule, Validation } from "../types";

export function SchedulePage() {
  const queryClient = useQueryClient();
  const schedule = useQuery({
    queryKey: ["schedule", "latest"],
    queryFn: () => api<Schedule>("/api/schedules/latest"),
    retry: false,
  });

  const validate = useMutation({
    mutationFn: (id: number) =>
      api<Validation>(`/api/schedules/${id}/validate`, { method: "POST" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["schedule"] });
      void queryClient.invalidateQueries({ queryKey: ["overview"] });
    },
  });

  if (schedule.isLoading) return <LoadingState label="Loading schedule…" />;
  if (schedule.isError) {
    if (schedule.error instanceof ApiError && schedule.error.status === 404) {
      return (
        <div>
          <PageIntro title="Schedule" description="Roster grid for the latest stored schedule version." />
          <EmptyState title="No schedule stored" detail="Run a successful solve first, then return here." />
        </div>
      );
    }
    return <ErrorState error={schedule.error} />;
  }

  const data = schedule.data!;
  const days = data.days.length > 0 ? data.days : [...new Set(data.assignments.map((a) => a.local_date))].sort();
  const employees = data.employees;

  const cell = (employeeId: number, day: string) =>
    data.assignments.filter((a) => a.employee_id === employeeId && a.local_date === day);

  return (
    <div>
      <PageIntro
        title="Schedule"
        description={`${data.organization_name} · timezone ${data.planning_timezone}`}
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <StatusBadge status={data.solver_status} />
        <span className="text-sm text-stone-500">
          Schedule #{data.id} · run #{data.run_id} · objective {data.objective}
        </span>
        <Button
          variant="ghost"
          data-testid="revalidate"
          onClick={() => validate.mutate(data.id)}
          disabled={validate.isPending}
        >
          {validate.isPending ? "Validating…" : "Re-validate"}
        </Button>
        <a
          className="rounded-xl border border-stone-300 px-3 py-2 text-sm hover:bg-stone-50 dark:border-stone-700 dark:hover:bg-stone-900"
          href={`/api/schedules/${data.id}/export.csv`}
          data-testid="export-csv"
        >
          Export CSV
        </a>
        <a
          className="rounded-xl border border-stone-300 px-3 py-2 text-sm hover:bg-stone-50 dark:border-stone-700 dark:hover:bg-stone-900"
          href={`/api/schedules/${data.id}/export.ics`}
          data-testid="export-ics"
        >
          Export ICS
        </a>
      </div>

      {data.solver_status === "INFEASIBLE" ? (
        <Card className="mb-4 border-rose-300 bg-rose-50 text-rose-900 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
          <p className="font-semibold">INFEASIBLE scenario</p>
          <p className="mt-1 text-sm">
            No roster satisfies the configured hard constraints. That is a model status, not a legal or labor-law verdict.
          </p>
        </Card>
      ) : null}

      <Card className="mb-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold">Validator summary</h2>
          <span className={`text-xs font-semibold ${data.validation.valid ? "text-emerald-700" : "text-rose-700"}`}>
            {data.validation.valid ? "Valid" : `${data.validation.violations.length} violation(s)`}
          </span>
        </div>
        {data.validation.violations.length > 0 ? (
          <ul className="mt-3 max-h-40 space-y-1 overflow-auto text-sm">
            {data.validation.violations.map((v, i) => (
              <li key={`${v.code}-${i}`}>
                <span className="font-medium">{v.code}</span>: {v.message}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-stone-500">No hard-constraint violations.</p>
        )}
      </Card>

      <div className="overflow-x-auto rounded-2xl border border-stone-200/80 bg-white/80 dark:border-stone-800 dark:bg-stone-950/70">
        <div
          role="grid"
          aria-label={`Employee by day roster grid for ${data.organization_name}, ${days.length} days`}
          className="grid min-w-[720px] text-sm"
          style={{ gridTemplateColumns: `160px repeat(${Math.max(days.length, 1)}, minmax(120px, 1fr))` }}
        >
          <div className="sticky left-0 z-10 border-b border-r border-stone-200 bg-stone-50 px-3 py-2 font-medium dark:border-stone-800 dark:bg-stone-900">
            Employee
          </div>
          {days.map((day) => (
            <div
              key={day}
              className="border-b border-stone-200 px-3 py-2 text-xs font-medium uppercase tracking-wide text-stone-500 dark:border-stone-800"
            >
              {day}
            </div>
          ))}
          {employees.map((employee) => (
            <div key={employee.id} className="contents">
              <div className="sticky left-0 z-10 border-b border-r border-stone-100 bg-white px-3 py-2 font-medium dark:border-stone-900 dark:bg-stone-950">
                <p>{employee.display_alias}</p>
                <p className="text-xs text-stone-500 tabular">
                  {employee.hours}/{employee.weekly_hour_cap}h
                </p>
              </div>
              {days.map((day) => {
                const items = cell(employee.id, day);
                return (
                  <div key={`${employee.id}-${day}`} className="border-b border-stone-100 p-2 dark:border-stone-900">
                    {items.length === 0 ? (
                      <span className="text-xs text-stone-400">—</span>
                    ) : (
                      <ul className="space-y-1">
                        {items.map((item) => (
                          <li
                            key={`${item.shift_id}-${item.employee_id}`}
                            className="rounded-lg bg-amber-50 px-2 py-1 text-xs text-amber-950 dark:bg-amber-950/40 dark:text-amber-100"
                          >
                            <p className="font-medium">{item.label}</p>
                            <p>
                              {item.start_local}–{item.end_local}
                            </p>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
