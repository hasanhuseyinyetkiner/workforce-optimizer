import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "../api";
import { Button, Card, PageIntro } from "../components/ui";
import type { DemoLoadResult } from "../types";

export function ScenariosPage() {
  const queryClient = useQueryClient();

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

  return (
    <div>
      <PageIntro
        title="Scenarios"
        description="Replace the database with a synthetic feasible or intentionally infeasible planning problem."
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <h2 className="font-semibold">Feasible</h2>
          <p className="mt-2 text-sm text-stone-600 dark:text-stone-400">
            Balanced demand and skill coverage so a reproducible solve can reach OPTIMAL or FEASIBLE.
          </p>
          <Button className="mt-4" onClick={() => load.mutate("feasible")} disabled={load.isPending}>
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
          <pre className="mt-2 overflow-auto rounded-xl bg-stone-100 p-3 text-xs dark:bg-stone-900">
            {JSON.stringify(load.data, null, 2)}
          </pre>
        </Card>
      ) : null}
      {load.isError ? <p className="mt-4 text-sm text-rose-600">{load.error.message}</p> : null}
    </div>
  );
}
