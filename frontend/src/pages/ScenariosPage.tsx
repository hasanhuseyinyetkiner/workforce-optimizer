import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { api } from "../api";
import { Button, Card, EmptyState, LoadingState, PageIntro, StatusBadge } from "../components/ui";
import type { DemoLoadResult, ScheduleCompare, ScheduleSummary } from "../types";

export function ScenariosPage() {
  const queryClient = useQueryClient();
  const [leftId, setLeftId] = useState<number | "">("");
  const [rightId, setRightId] = useState<number | "">("");

  const schedules = useQuery({
    queryKey: ["schedules"],
    queryFn: () => api<ScheduleSummary[]>("/api/schedules"),
  });

  const load = useMutation({
    mutationFn: (scenario: "feasible" | "infeasible") =>
      api<DemoLoadResult>("/api/demo/load", {
        method: "POST",
        body: JSON.stringify({ scenario }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries();
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
        description="Load synthetic planning problems, then compare two stored schedules on objectives and assignments."
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <h2 className="font-semibold">Feasible</h2>
          <p className="mt-2 text-sm text-stone-600 dark:text-stone-400">
            Balanced demand and skill coverage so a reproducible solve can reach OPTIMAL or FEASIBLE.
          </p>
          <Button
            className="mt-4"
            data-testid="load-feasible"
            onClick={() => load.mutate("feasible")}
            disabled={load.isPending}
          >
            Load feasible scenario
          </Button>
        </Card>
        <Card className="border-rose-200 dark:border-rose-900">
          <h2 className="font-semibold text-rose-800 dark:text-rose-300">Infeasible</h2>
          <p className="mt-2 text-sm text-stone-600 dark:text-stone-400">
            Over-constrained demand designed so the solver returns INFEASIBLE. The Schedule page will flag it clearly.
          </p>
          <Button
            variant="danger"
            className="mt-4"
            data-testid="load-infeasible"
            onClick={() => load.mutate("infeasible")}
            disabled={load.isPending}
          >
            Load infeasible scenario
          </Button>
        </Card>
      </div>
      {load.isSuccess ? (
        <Card className="mt-4">
          <p className="text-sm">
            Loaded <span className="font-semibold">{load.data.scenario}</span> scenario
            {load.data.synthetic ? " (synthetic)" : ""}.
          </p>
        </Card>
      ) : null}
      {load.isError ? <p className="mt-4 text-sm text-rose-600">{load.error.message}</p> : null}

      <Card className="mt-6">
        <h2 className="font-semibold">Scenario compare</h2>
        <p className="mt-1 text-sm text-stone-500">
          Pick two stored schedule versions (baseline vs changed staffing or preferences after separate solves).
        </p>
        {schedules.isLoading ? <LoadingState label="Loading schedules…" /> : null}
        {!schedules.isLoading && options.length < 2 ? (
          <EmptyState
            title="Need two schedules"
            detail="Run at least two successful solves (for example after changing preferences or reloading a scenario), then compare them here."
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
