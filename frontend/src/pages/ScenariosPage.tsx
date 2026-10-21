import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { api } from "../api";
import { Button, Card, EmptyState, LoadingState, PageIntro, StatusBadge } from "../components/ui";
import type {
  DemoLoadResult,
  DemoScenario,
  OptimizationRun,
  ScheduleCompare,
  ScheduleSummary,
  ScenarioTiming,
} from "../types";

const SCENARIOS: Array<{
  id: DemoScenario;
  title: string;
  expected: "OPTIMAL" | "FEASIBLE" | "INFEASIBLE";
  detail: string;
  danger?: boolean;
}> = [
  {
    id: "optimal",
    title: "OPTIMAL",
    expected: "OPTIMAL",
    detail: "Small ward slice that proves optimum under the reproducible budget.",
  },
  {
    id: "feasible",
    title: "FEASIBLE",
    expected: "FEASIBLE",
    detail: "Full Northwind week — usually FEASIBLE with a positive gap before proof.",
  },
  {
    id: "infeasible",
    title: "INFEASIBLE",
    expected: "INFEASIBLE",
    detail: "Over-constrained demand (e.g. missing CRNA). Model status, not a legal ban.",
    danger: true,
  },
];

const TERMINAL = new Set(["SUCCEEDED", "FAILED", "CANCELLED"]);

async function waitRun(id: number): Promise<OptimizationRun> {
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    const run = await api<OptimizationRun>(`/api/optimization-runs/${id}`);
    if (TERMINAL.has(run.status.toUpperCase())) return run;
    await new Promise((r) => setTimeout(r, 400));
  }
  throw new Error(`Timed out waiting for run #${id}`);
}

export function ScenariosPage() {
  const queryClient = useQueryClient();
  const [leftId, setLeftId] = useState<number | "">("");
  const [rightId, setRightId] = useState<number | "">("");
  const [active, setActive] = useState<DemoScenario>("feasible");
  const [timing, setTiming] = useState<ScenarioTiming | null>(null);

  const schedules = useQuery({
    queryKey: ["schedules"],
    queryFn: () => api<ScheduleSummary[]>("/api/schedules"),
  });

  const runScenario = useMutation({
    mutationFn: async (scenario: DemoScenario) => {
      setActive(scenario);
      const expected = SCENARIOS.find((s) => s.id === scenario)!.expected;
      await api<DemoLoadResult>("/api/demo/load", {
        method: "POST",
        body: JSON.stringify({ scenario }),
      });
      const created = await api<OptimizationRun>("/api/optimization-runs", {
        method: "POST",
        body: JSON.stringify({
          mode: "reproducible",
          random_seed: 1,
          label: `scenario-${scenario}`,
        }),
      });
      const finished = await waitRun(created.id);
      const wall_ms =
        finished.runtime_seconds != null ? Math.round(finished.runtime_seconds * 1000) : null;
      const gap =
        finished.objective != null && finished.best_bound != null
          ? finished.objective - finished.best_bound
          : null;
      const row: ScenarioTiming = {
        scenario,
        expected,
        solver_status: finished.solver_status,
        wall_ms,
        objective: finished.objective,
        best_bound: finished.best_bound,
        gap,
        run_id: finished.id,
      };
      return row;
    },
    onSuccess: (row) => {
      setTiming(row);
      void queryClient.invalidateQueries();
    },
    onError: (err, scenario) => {
      const expected = SCENARIOS.find((s) => s.id === scenario)!.expected;
      setTiming({
        scenario,
        expected,
        solver_status: null,
        wall_ms: null,
        objective: null,
        best_bound: null,
        gap: null,
        run_id: null,
        error: err instanceof Error ? err.message : String(err),
      });
    },
  });

  const compare = useQuery({
    queryKey: ["schedule-compare", leftId, rightId],
    queryFn: () =>
      api<ScheduleCompare>(`/api/schedules/compare?left_id=${leftId}&right_id=${rightId}`),
    enabled: typeof leftId === "number" && typeof rightId === "number" && leftId !== rightId,
  });

  const options = useMemo(() => schedules.data ?? [], [schedules.data]);

  return (
    <div>
      <PageIntro
        title="Scenarios"
        description="Toggle OPTIMAL / FEASIBLE / INFEASIBLE demos, solve immediately, and compare wall-clock telemetry."
      />

      <Card className="mb-4">
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="Scenario status toggle">
          {SCENARIOS.map((s) => {
            const selected = active === s.id;
            return (
              <Button
                key={s.id}
                variant={s.danger ? "danger" : selected ? "primary" : "ghost"}
                data-testid={`scenario-${s.id}`}
                aria-pressed={selected}
                disabled={runScenario.isPending}
                onClick={() => runScenario.mutate(s.id)}
              >
                {runScenario.isPending && active === s.id ? `Running ${s.title}…` : s.title}
              </Button>
            );
          })}
        </div>
        <p className="mt-3 text-sm text-stone-600 dark:text-stone-400">
          {SCENARIOS.find((s) => s.id === active)?.detail}
        </p>
        {runScenario.isPending ? (
          <p className="mt-3 text-sm text-stone-500">Loading scenario and solving…</p>
        ) : null}
        {timing ? (
          <dl
            className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4"
            data-testid="scenario-timing"
          >
            <div>
              <dt className="text-stone-500">Expected</dt>
              <dd>
                <StatusBadge status={timing.expected} />
              </dd>
            </div>
            <div>
              <dt className="text-stone-500">Got</dt>
              <dd>
                <StatusBadge status={timing.solver_status ?? "UNKNOWN"} />
              </dd>
            </div>
            <div>
              <dt className="text-stone-500">Wall</dt>
              <dd className="tabular font-medium">
                {timing.wall_ms != null ? `${timing.wall_ms} ms` : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-stone-500">Obj / gap</dt>
              <dd className="tabular font-medium">
                {timing.objective ?? "—"}
                {timing.gap != null ? ` / ${timing.gap}` : ""}
              </dd>
            </div>
          </dl>
        ) : null}
        {timing?.error ? <p className="mt-2 text-sm text-rose-600">{timing.error}</p> : null}
      </Card>

      <Card className="mt-6">
        <h2 className="font-semibold">Schedule compare</h2>
        <p className="mt-1 text-sm text-stone-500">
          Pick two stored schedule versions after separate solves.
        </p>
        {schedules.isLoading ? <LoadingState label="Loading schedules…" /> : null}
        {!schedules.isLoading && options.length < 2 ? (
          <EmptyState
            title="Need two schedules"
            detail="Run at least two successful OPTIMAL/FEASIBLE solves, then compare them here."
          />
        ) : null}
        {options.length >= 2 ? (
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="text-stone-500">Baseline</span>
              <select
                data-testid="compare-left"
                className="mt-1 w-full rounded-xl border border-stone-300 bg-transparent px-3 py-2 dark:border-stone-700"
                value={leftId}
                onChange={(e) => setLeftId(e.target.value ? Number(e.target.value) : "")}
              >
                <option value="">Select…</option>
                {options.map((row) => (
                  <option key={row.id} value={row.id}>
                    #{row.id} · {row.label || "run"} · {row.solver_status} · obj {row.objective ?? "—"}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-stone-500">Candidate</span>
              <select
                data-testid="compare-right"
                className="mt-1 w-full rounded-xl border border-stone-300 bg-transparent px-3 py-2 dark:border-stone-700"
                value={rightId}
                onChange={(e) => setRightId(e.target.value ? Number(e.target.value) : "")}
              >
                <option value="">Select…</option>
                {options.map((row) => (
                  <option key={row.id} value={row.id}>
                    #{row.id} · {row.label || "run"} · {row.solver_status} · obj {row.objective ?? "—"}
                  </option>
                ))}
              </select>
            </label>
          </div>
        ) : null}

        {compare.isFetching ? <p className="mt-3 text-sm text-stone-500">Comparing…</p> : null}
        {compare.isError ? <p className="mt-3 text-sm text-rose-600">{compare.error.message}</p> : null}
        {compare.data ? <CompareResult data={compare.data} /> : null}
      </Card>
    </div>
  );
}

function CompareResult({ data }: { data: ScheduleCompare }) {
  const deltaEntries = Object.entries(data.objective_delta).filter(([key]) => key !== "total");
  return (
    <div className="mt-4 space-y-4" data-testid="compare-result">
      <div className="grid gap-3 sm:grid-cols-2">
        <SideCard title="Baseline" side={data.left} />
        <SideCard title="Candidate" side={data.right} />
      </div>
      <div className="rounded-xl bg-stone-100 p-3 text-sm dark:bg-stone-900">
        <p>
          Objective delta (candidate − baseline):{" "}
          <span className="tabular font-semibold">{data.objective_delta.total ?? 0}</span>
        </p>
        <p className="mt-1 text-stone-500">
          Rules {data.rules_match ? "match" : "differ"} · shared assignments{" "}
          {data.assignment_diff.shared_count} · only baseline {data.assignment_diff.only_left_count} ·
          only candidate {data.assignment_diff.only_right_count}
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[420px] text-left text-sm">
          <thead>
            <tr className="border-b border-stone-200 text-xs uppercase tracking-wide text-stone-500 dark:border-stone-800">
              <th className="py-2 pr-3">Component</th>
              <th className="py-2 pr-3">Δ</th>
            </tr>
          </thead>
          <tbody>
            {deltaEntries.map(([name, value]) => (
              <tr key={name} className="border-b border-stone-100 dark:border-stone-900">
                <td className="py-2 pr-3">{name}</td>
                <td className="py-2 pr-3 tabular">{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SideCard({
  title,
  side,
}: {
  title: string;
  side: ScheduleCompare["left"];
}) {
  return (
    <div className="rounded-xl border border-stone-200 p-3 dark:border-stone-800">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        <StatusBadge status={side.solver_status} />
      </div>
      <p className="mt-2 text-sm">
        Schedule #{side.id} · {side.label || "unlabeled"} · objective{" "}
        <span className="tabular font-medium">{side.objective}</span>
      </p>
      <p className="text-xs text-stone-500">{side.mode_label ?? "—"}</p>
    </div>
  );
}
