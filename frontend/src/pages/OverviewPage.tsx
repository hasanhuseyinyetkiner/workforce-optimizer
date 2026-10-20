import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { api } from "../api";
import { Card, ErrorState, LoadingState, PageIntro, Stat, StatusBadge } from "../components/ui";
import type { ObjectiveBreakdown, Overview } from "../types";

function breakdownRows(breakdown: ObjectiveBreakdown | null | undefined) {
  if (!breakdown) return [];
  return [
    { name: "cost", value: breakdown.cost },
    { name: "preference", value: breakdown.preference },
    { name: "fairness", value: breakdown.fairness },
    { name: "overtime", value: breakdown.overtime },
    { name: "night", value: breakdown.night_imbalance },
    { name: "weekend", value: breakdown.weekend_imbalance },
    { name: "understaff", value: breakdown.understaff },
  ];
}

export function OverviewPage() {
  const overview = useQuery({
    queryKey: ["overview"],
    queryFn: () => api<Overview>("/api/overview"),
  });

  if (overview.isLoading) return <LoadingState label="Loading overview…" />;
  if (overview.isError) return <ErrorState error={overview.error} />;
  const data = overview.data!;
  const latest = data.latest_run;
  const chart = breakdownRows(data.schedule?.objective_breakdown ?? latest?.objective_breakdown);

  return (
    <div>
      <PageIntro
        eyebrow={data.organization_name ?? "Workspace"}
        title="Overview"
        description={`Planning timezone ${data.planning_timezone ?? "—"}. Counts and run status come from the live API.`}
      />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Employees" value={data.counts.employees} />
        <Stat label="Shifts" value={data.counts.shifts} />
        <Stat label="Skills" value={data.counts.skills} />
        <Stat
          label="Latest run"
          value={<StatusBadge status={latest?.solver_status ?? latest?.status ?? "UNKNOWN"} />}
          hint={latest ? `Run #${latest.id} · ${latest.status}` : "No runs yet"}
        />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="text-sm font-semibold">Objective breakdown</h2>
          {chart.length === 0 ? (
            <p className="mt-3 text-sm text-stone-500">Solve a schedule to see component costs.</p>
          ) : (
            <div className="mt-3 h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chart}>
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="value" fill="#D97706" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
        <Card>
          <h2 className="text-sm font-semibold">Recent runs</h2>
          <ul className="mt-3 divide-y divide-stone-200 dark:divide-stone-800">
            {data.recent_runs.length === 0 ? (
              <li className="py-3 text-sm text-stone-500">No optimization runs yet.</li>
            ) : (
              data.recent_runs.map((run) => (
                <li key={run.id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                  <div>
                    <p className="font-medium">#{run.id} · {run.label}</p>
                    <p className="text-xs text-stone-500">
                      {run.mode_label ?? run.mode} · seed {run.random_seed}
                    </p>
                  </div>
                  <StatusBadge status={run.solver_status ?? run.status} />
                </li>
              ))
            )}
          </ul>
        </Card>
      </div>

      {data.schedule?.validation ? (
        <Card className="mt-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold">Latest schedule validation</h2>
            <span
              className={`text-xs font-semibold ${
                data.schedule.validation.valid ? "text-emerald-700 dark:text-emerald-300" : "text-rose-700 dark:text-rose-300"
              }`}
            >
              {data.schedule.validation.valid ? "Valid" : "Violations present"}
            </span>
          </div>
          {data.schedule.solver_status === "INFEASIBLE" ? (
            <p className="mt-2 rounded-xl bg-rose-100 px-3 py-2 text-sm text-rose-900 dark:bg-rose-950/50 dark:text-rose-200">
              Latest schedule is flagged INFEASIBLE by the solver (configured hard rules conflict — not a labor-law verdict).
            </p>
          ) : null}
          {data.schedule.validation.violations.length > 0 ? (
            <ul className="mt-3 space-y-1 text-sm text-stone-600 dark:text-stone-400">
              {data.schedule.validation.violations.slice(0, 5).map((v, i) => (
                <li key={`${v.code}-${i}`}>
                  <span className="font-medium text-stone-800 dark:text-stone-200">{v.code}</span>: {v.message}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-stone-500">No hard-constraint violations reported.</p>
          )}
        </Card>
      ) : null}
    </div>
  );
}
