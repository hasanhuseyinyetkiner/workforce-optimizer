import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { api } from "../api";
import { Button, Card, ErrorState, PageIntro, StatusBadge } from "../components/ui";
import type { ObjectiveBreakdown, OptimizationRun } from "../types";

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

  return (
    <div>
      <PageIntro
        title="Solve"
        description="Launch a reproducible optimization run, poll until finished, and show the exact solver status."
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
            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-stone-500">Status</dt>
                <dd className="font-medium">{current.status}</dd>
              </div>
              <div>
                <dt className="text-stone-500">Solver status</dt>
                <dd className="font-medium">{current.solver_status ?? "UNKNOWN"}</dd>
              </div>
              <div>
                <dt className="text-stone-500">Objective</dt>
                <dd className="tabular font-medium">{current.objective ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-stone-500">Runtime</dt>
                <dd className="tabular font-medium">
                  {current.runtime_seconds != null ? `${current.runtime_seconds.toFixed(2)}s` : "—"}
                </dd>
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
                Solver returned INFEASIBLE. Load the feasible scenario or relax rules, then solve again.
              </p>
            ) : null}
            {current.error_message ? (
              <p className="mt-3 text-sm text-rose-600">{current.error_message}</p>
            ) : null}
            {run.isError ? <ErrorState error={run.error} /> : null}
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
                Total objective: <span className="tabular font-medium text-stone-800 dark:text-stone-200">{current.objective_breakdown.total}</span>
              </p>
            ) : null}
          </Card>
        </div>
      ) : null}
    </div>
  );
}
