import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";

import { api, ApiError } from "../api";
import { Button, Card, EmptyState, ErrorState, LoadingState, PageIntro, StatusBadge } from "../components/ui";
import type { Schedule, Validation } from "../types";

function wallMs(seconds: number | null | undefined) {
  if (seconds == null) return null;
  return Math.round(seconds * 1000);
}

function optimalityGap(objective: number | null | undefined, bound: number | null | undefined) {
  if (objective == null || bound == null) return null;
  return objective - bound;
}

function ViolationBadge({ code }: { code: string }) {
  return (
    <span className="inline-flex rounded bg-rose-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-rose-900 dark:bg-rose-950 dark:text-rose-200">
      {code}
    </span>
  );
}

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

  const data = schedule.data;
  const days = useMemo(() => {
    if (!data) return [];
    return data.days.length > 0 ? data.days : [...new Set(data.assignments.map((a) => a.local_date))].sort();
  }, [data]);

  const violationsByEmployee = useMemo(() => {
    const map = new Map<number, string[]>();
    if (!data) return map;
    for (const v of data.validation.violations) {
      if (v.employee_id == null) continue;
      const list = map.get(v.employee_id) ?? [];
      list.push(v.code);
      map.set(v.employee_id, list);
    }
    return map;
  }, [data]);

  const violationsByShiftDay = useMemo(() => {
    const map = new Map<string, string[]>();
    if (!data) return map;
    const shiftDay = new Map(data.shifts.map((s) => [s.id, s.local_date]));
    for (const v of data.validation.violations) {
      if (v.shift_id == null) continue;
      const day = shiftDay.get(v.shift_id);
      if (!day || v.employee_id == null) continue;
      const key = `${v.employee_id}:${day}`;
      const list = map.get(key) ?? [];
      list.push(v.code);
      map.set(key, list);
    }
    return map;
  }, [data]);

  if (schedule.isLoading) return <LoadingState label="Loading schedule…" />;
  if (schedule.isError) {
    if (schedule.error instanceof ApiError && schedule.error.status === 404) {
      return (
        <div>
          <PageIntro title="Schedule" description="Dense roster grid for the latest stored schedule version." />
          <EmptyState title="No schedule stored" detail="Run a successful solve first, then return here." />
        </div>
      );
    }
    return <ErrorState error={schedule.error} />;
  }

  const roster = data!;
  const employees = roster.employees;
  const ms = wallMs(roster.runtime_seconds);
  const gap = optimalityGap(roster.objective, roster.best_bound);

  const cell = (employeeId: number, day: string) =>
    roster.assignments.filter((a) => a.employee_id === employeeId && a.local_date === day);

  return (
    <div>
      <PageIntro
        title="Schedule"
        description={`${roster.organization_name} · timezone ${roster.planning_timezone}`}
      />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <StatusBadge status={roster.solver_status} />
        <span className="text-xs text-stone-500 tabular" data-testid="schedule-telemetry">
          #{roster.id} · run #{roster.run_id} · obj {roster.objective}
          {ms != null ? ` · ${ms} ms` : ""}
          {gap != null ? ` · gap ${gap}` : ""}
        </span>
        <Button
          variant="ghost"
          data-testid="revalidate"
          onClick={() => validate.mutate(roster.id)}
          disabled={validate.isPending}
        >
          {validate.isPending ? "Validating…" : "Re-validate"}
        </Button>
        <a
          className="rounded-lg border border-stone-300 px-2.5 py-1.5 text-xs hover:bg-stone-50 dark:border-stone-700 dark:hover:bg-stone-900"
          href={`/api/schedules/${roster.id}/export.csv`}
          data-testid="export-csv"
        >
          Export CSV
        </a>
        <a
          className="rounded-lg border border-stone-300 px-2.5 py-1.5 text-xs hover:bg-stone-50 dark:border-stone-700 dark:hover:bg-stone-900"
          href={`/api/schedules/${roster.id}/export.ics`}
          data-testid="export-ics"
        >
          Export ICS
        </a>
      </div>

      {roster.solver_status === "INFEASIBLE" ? (
        <Card className="mb-3 border-rose-300 bg-rose-50 text-rose-900 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
          <p className="font-semibold">INFEASIBLE scenario</p>
          <p className="mt-1 text-sm">
            No roster satisfies the configured hard constraints. That is a model status, not a legal verdict.
          </p>
        </Card>
      ) : null}

      <Card className="mb-3 !p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold">Validator summary</h2>
          <span className={`text-xs font-semibold ${roster.validation.valid ? "text-emerald-700" : "text-rose-700"}`}>
            {roster.validation.valid ? "Valid" : `${roster.validation.violations.length} violation(s)`}
          </span>
        </div>
        {roster.validation.violations.length > 0 ? (
          <ul className="mt-2 max-h-32 space-y-1 overflow-auto text-xs">
            {roster.validation.violations.map((v, i) => (
              <li key={`${v.code}-${i}`} className="flex flex-wrap items-center gap-1.5">
                <ViolationBadge code={v.code} />
                <span>{v.message}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-xs text-stone-500">No hard-constraint violations.</p>
        )}
      </Card>

      <div className="overflow-x-auto rounded-xl border border-stone-200/80 bg-white dark:border-stone-800 dark:bg-stone-950">
        <div
          role="grid"
          aria-label={`Employee by day roster grid for ${roster.organization_name}, ${days.length} days`}
          className="grid min-w-[640px] text-xs"
          style={{ gridTemplateColumns: `120px repeat(${Math.max(days.length, 1)}, minmax(88px, 1fr))` }}
        >
          <div className="sticky left-0 z-10 border-b border-r border-stone-200 bg-stone-50 px-2 py-1.5 font-medium dark:border-stone-800 dark:bg-stone-900">
            Employee
          </div>
          {days.map((day) => (
            <div
              key={day}
              className="border-b border-stone-200 px-1.5 py-1.5 text-[10px] font-medium uppercase tracking-wide text-stone-500 dark:border-stone-800"
            >
              {day.slice(5)}
            </div>
          ))}
          {employees.map((employee) => {
            const empViolations = [...new Set(violationsByEmployee.get(employee.id) ?? [])];
            return (
              <div key={employee.id} className="contents">
                <div className="sticky left-0 z-10 border-b border-r border-stone-100 bg-white px-2 py-1 dark:border-stone-900 dark:bg-stone-950">
                  <p className="truncate font-medium leading-tight">{employee.display_alias}</p>
                  <p className="text-[10px] text-stone-500 tabular leading-tight">
                    {employee.hours}/{employee.weekly_hour_cap}h
                  </p>
                  {empViolations.length > 0 ? (
                    <div className="mt-0.5 flex flex-wrap gap-0.5">
                      {empViolations.slice(0, 2).map((code) => (
                        <ViolationBadge key={code} code={code} />
                      ))}
                    </div>
                  ) : null}
                </div>
                {days.map((day) => {
                  const items = cell(employee.id, day);
                  const cellViolations = [...new Set(violationsByShiftDay.get(`${employee.id}:${day}`) ?? [])];
                  return (
                    <div
                      key={`${employee.id}-${day}`}
                      className={`border-b border-stone-100 p-1 dark:border-stone-900 ${
                        cellViolations.length > 0 ? "bg-rose-50/80 dark:bg-rose-950/30" : ""
                      }`}
                    >
                      {items.length === 0 ? (
                        <span className="text-[10px] text-stone-400">·</span>
                      ) : (
                        <ul className="space-y-0.5">
                          {items.map((item) => (
                            <li
                              key={`${item.shift_id}-${item.employee_id}`}
                              className="rounded bg-amber-50 px-1 py-0.5 text-[10px] leading-tight text-amber-950 dark:bg-amber-950/40 dark:text-amber-100"
                            >
                              <p className="font-medium truncate">{item.label}</p>
                              <p className="tabular">
                                {item.start_local}–{item.end_local}
                              </p>
                            </li>
                          ))}
                        </ul>
                      )}
                      {cellViolations.length > 0 ? (
                        <div className="mt-0.5 flex flex-wrap gap-0.5">
                          {cellViolations.map((code) => (
                            <ViolationBadge key={code} code={code} />
                          ))}
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
