import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { api } from "../api";
import { Button, Card, ErrorState, PageIntro, StatusBadge } from "../components/ui";
import type { Diagnostics, ObjectiveBreakdown, OptimizationRun } from "../types";

const TERMINAL = new Set(["SUCCEEDED", "FAILED", "CANCELLED"]);

function isTerminal(run: OptimizationRun | undefined) {
  if (!run) return false;
  return TERMINAL.has(run.status.toUpperCase());
}

function breakdownRows(breakdown: ObjectiveBreakdown | null | undefined) {
  if (!breakdown) return [];
  return Object.entries(breakdown)
    .filter(([key]) => key !== "total")
    .map(([name, value]) => ({ name, value }));
}

function wallMs(seconds: number | null | undefined) {
  if (seconds == null) return null;
  return Math.round(seconds * 1000);
}

function optimalityGap(objective: number | null | undefined, bound: number | null | undefined) {
  if (objective == null || bound == null) return null;
  return objective - bound;
}

function DiagnosticsPanel({ diagnostics }: { diagnostics: Diagnostics }) {
  return (
    <div className="mt-4 rounded-xl border border-rose-200 p-3 dark:border-rose-900">
      <h2 className="text-sm font-semibold">Conflict diagnostics</h2>
      <p className="mt-1 text-xs text-stone-500">{diagnostics.note}</p>

      {diagnostics.conflict_groups && diagnostics.conflict_groups.length > 0 ? (
        <div className="mt-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">
            Conflicting hard-constraint groups
          </p>
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {diagnostics.conflict_groups.map((g) => (
              <li
                key={g.group}
                className="rounded bg-rose-100 px-2 py-0.5 text-xs font-medium text-rose-900 dark:bg-rose-950 dark:text-rose-200"
              >
                {g.label}
              </li>
            ))}
          </ul>
          <p className="mt-1 text-xs text-stone-500">
            Method: {diagnostics.assumption_method ?? "n/a"} · kind {diagnostics.unsat_core_kind}
          </p>
        </div>
      ) : (
        <p className="mt-2 text-xs text-stone-500">
          {diagnostics.assumptions_available === false
            ? "Assumption API unavailable — structural findings and relaxations only."
            : "No refined assumption groups reported."}
        </p>
      )}

      {diagnostics.findings.length > 0 ? (
        <ul className="mt-3 max-h-36 space-y-1 overflow-auto text-sm">
          {diagnostics.findings.map((f, i) => (
            <li key={`${f.code}-${i}`}>
              <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs font-semibold text-amber-950 dark:bg-amber-950 dark:text-amber-100">
                {f.code}
              </span>{" "}
              {f.message}
            </li>
          ))}
        </ul>
      ) : null}

      {diagnostics.relaxations.length > 0 ? (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[320px] text-left text-xs">
            <thead>
              <tr className="border-b border-stone-200 text-stone-500 dark:border-stone-800">
                <th className="py-1 pr-2 font-medium">Relaxed</th>
                <th className="py-1 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {diagnostics.relaxations.map((row, i) => (
                <tr key={`${row.relaxed.join(",")}-${i}`} className="border-b border-stone-100 dark:border-stone-900">
                  <td className="py-1 pr-2">{row.relaxed.join(", ")}</td>
                  <td className="py-1">
                    <StatusBadge status={row.solver_status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

export function SolvePage() {
  const queryClient = useQueryClient();
  const [activeRunId, setActiveRunId] = useState<number | null>(null);
  const [seed, setSeed] = useState(1);
  const [label, setLabel] = useState("current");

  const launch = useMutation({
    mutationFn: () =>
      api<OptimizationRun>("/api/optimization-runs", {
        method: "POST",
        body: JSON.stringify({ mode: "reproducible", random_seed: seed, label }),
      }),
    onSuccess: (run) => {
      setActiveRunId(run.id);
      void queryClient.invalidateQueries({ queryKey: ["overview"] });
    },
  });

  const run = useQuery({
    queryKey: ["run", activeRunId],
    queryFn: () => api<OptimizationRun>(`/api/optimization-runs/${activeRunId}`),
    enabled: activeRunId != null,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 800;
      return isTerminal(data) ? false : 800;
    },
  });

  useEffect(() => {
    if (run.data && isTerminal(run.data)) {
      void queryClient.invalidateQueries({ queryKey: ["overview"] });
      void queryClient.invalidateQueries({ queryKey: ["schedule"] });
    }
  }, [run.data, queryClient]);

  const current = run.data ?? launch.data;
  const chart = breakdownRows(current?.objective_breakdown);
  const ms = wallMs(current?.runtime_seconds);
  const gap = optimalityGap(current?.objective, current?.best_bound);

  return (
    <div>
      <PageIntro
        title="Solve"
        description="Launch a reproducible optimization run, poll until finished, and inspect solver telemetry."
      />
      <Card>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="block text-sm">
            <span className="text-stone-500">Random seed</span>
            <input
              type="number"
              min={0}
              value={seed}
              onChange={(e) => setSeed(Number(e.target.value))}
              className="mt-1 w-full rounded-xl border border-stone-300 bg-transparent px-3 py-2 dark:border-stone-700"
            />
          </label>
          <label className="block text-sm sm:col-span-2">
            <span className="text-stone-500">Label</span>
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="mt-1 w-full rounded-xl border border-stone-300 bg-transparent px-3 py-2 dark:border-stone-700"
            />
          </label>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button
            data-testid="run-solve"
            onClick={() => launch.mutate()}
            disabled={launch.isPending || (activeRunId != null && run.data != null && !isTerminal(run.data))}
          >
            {launch.isPending ? "Starting…" : "Run reproducible solve"}
          </Button>
          <p className="text-xs text-stone-500">Mode is fixed to reproducible for portfolio demos.</p>
        </div>
        {launch.isError ? <p className="mt-3 text-sm text-rose-600">{launch.error.message}</p> : null}
      </Card>

      {current ? (
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold">Run #{current.id}</h2>
              <StatusBadge status={current.solver_status ?? current.status} />
            </div>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm" data-testid="solver-telemetry">
              <div>
                <dt className="text-stone-500">Status</dt>
                <dd className="font-medium">{current.status}</dd>
              </div>
              <div>
                <dt className="text-stone-500">Solver status</dt>
                <dd className="font-medium">{current.solver_status ?? "UNKNOWN"}</dd>
              </div>
              <div>
                <dt className="text-stone-500">Wall time</dt>
                <dd className="tabular font-medium">{ms != null ? `${ms} ms` : "—"}</dd>
              </div>
              <div>
                <dt className="text-stone-500">Objective</dt>
                <dd className="tabular font-medium">{current.objective ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-stone-500">Best bound</dt>
                <dd className="tabular font-medium">{current.best_bound ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-stone-500">Gap</dt>
                <dd className="tabular font-medium">{gap != null ? gap : "—"}</dd>
              </div>
              <div>
                <dt className="text-stone-500">Mode</dt>
                <dd className="font-medium">{current.mode_label ?? current.mode}</dd>
              </div>
              <div>
                <dt className="text-stone-500">Schedule</dt>
                <dd className="font-medium">{current.schedule_id ?? "none"}</dd>
              </div>
            </dl>
            {current.solver_status === "INFEASIBLE" ? (
              <p className="mt-4 rounded-xl bg-rose-100 px-3 py-2 text-sm text-rose-900 dark:bg-rose-950/50 dark:text-rose-200">
                INFEASIBLE — no assignment satisfies the configured hard rules (not a labor-law judgment).
                See conflict diagnostics below.
              </p>
            ) : null}
            {current.error_message ? (
              <p className="mt-3 text-sm text-rose-600">{current.error_message}</p>
            ) : null}
            {run.isError ? <ErrorState error={run.error} /> : null}
            {current.diagnostics && current.solver_status === "INFEASIBLE" ? (
              <DiagnosticsPanel diagnostics={current.diagnostics} />
            ) : null}
          </Card>
          <Card>
            <h2 className="text-sm font-semibold">Objective breakdown</h2>
            {chart.length === 0 ? (
              <p className="mt-3 text-sm text-stone-500">
                {isTerminal(current) ? "No breakdown available for this run." : "Waiting for solver…"}
              </p>
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
            {current.objective_breakdown ? (
              <p className="mt-2 text-sm text-stone-500">
                Total objective:{" "}
                <span className="tabular font-medium text-stone-800 dark:text-stone-200">
                  {current.objective_breakdown.total}
                </span>
              </p>
            ) : null}
          </Card>
        </div>
      ) : null}
    </div>
  );
}
