import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../api";
import { Button, Card, ErrorState, LoadingState, PageIntro } from "../components/ui";
import type { Ruleset } from "../types";

const WEIGHT_KEYS = [
  "cost",
  "preference",
  "fairness",
  "overtime",
  "night_imbalance",
  "weekend_imbalance",
  "understaff",
] as const;

type FormState = {
  name: string;
  min_rest_hours: number;
  max_shift_hours: number;
  max_consecutive_days: number | null;
  overtime_threshold_hours: number;
  relaxed_understaffing: boolean;
  weights: Record<(typeof WEIGHT_KEYS)[number], number>;
};

const DEFAULTS: FormState = {
  name: "Active rules",
  min_rest_hours: 11,
  max_shift_hours: 12,
  max_consecutive_days: 6,
  overtime_threshold_hours: 40,
  relaxed_understaffing: false,
  weights: {
    cost: 1,
    preference: 10,
    fairness: 5,
    overtime: 20,
    night_imbalance: 5,
    weekend_imbalance: 5,
    understaff: 100,
  },
};

function toForm(data: Ruleset | undefined): FormState {
  if (!data) return DEFAULTS;
  return {
    name: data.name,
    min_rest_hours: data.min_rest_hours,
    max_shift_hours: data.max_shift_hours,
    max_consecutive_days: data.max_consecutive_days,
    overtime_threshold_hours: data.overtime_threshold_hours,
    relaxed_understaffing: data.relaxed_understaffing,
    weights: { ...DEFAULTS.weights, ...data.weights },
  };
}

export function RulesPage() {
  const rules = useQuery({
    queryKey: ["rules"],
    queryFn: () => api<Ruleset>("/api/rulesets/active"),
    retry: false,
  });

  if (rules.isLoading) return <LoadingState label="Loading rules…" />;
  if (rules.isError && !(rules.error as { status?: number }).status) {
    return <ErrorState error={rules.error} />;
  }

  return <RulesEditor key={rules.dataUpdatedAt} initial={toForm(rules.data)} />;
}

function RulesEditor({ initial }: { initial: FormState }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState(initial);

  const save = useMutation({
    mutationFn: () =>
      api<Ruleset>("/api/rulesets", {
        method: "POST",
        body: JSON.stringify(form),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["rules"] });
      void queryClient.invalidateQueries({ queryKey: ["overview"] });
    },
  });

  return (
    <div>
      <PageIntro
        title="Rules"
        description="Hard constraints are enforced by CP-SAT. Soft weights only change the objective after feasibility."
      />
      <Card>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-sm sm:col-span-2">
            <span className="text-stone-500">Ruleset name</span>
            <input
              className="mt-1 w-full rounded-xl border border-stone-300 bg-transparent px-3 py-2 dark:border-stone-700"
              value={form.name}
              onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
            />
          </label>
          <NumberField
            label="Min rest hours (hard)"
            value={form.min_rest_hours}
            onChange={(min_rest_hours) => setForm((prev) => ({ ...prev, min_rest_hours }))}
          />
          <NumberField
            label="Max shift hours (hard)"
            value={form.max_shift_hours}
            onChange={(max_shift_hours) => setForm((prev) => ({ ...prev, max_shift_hours }))}
          />
          <NumberField
            label="Max consecutive days (hard)"
            value={form.max_consecutive_days ?? 0}
            onChange={(value) =>
              setForm((prev) => ({
                ...prev,
                max_consecutive_days: value <= 0 ? null : value,
              }))
            }
          />
          <NumberField
            label="Overtime threshold hours (soft)"
            value={form.overtime_threshold_hours}
            onChange={(overtime_threshold_hours) =>
              setForm((prev) => ({ ...prev, overtime_threshold_hours }))
            }
          />
          <label className="flex items-center gap-2 text-sm sm:col-span-2">
            <input
              type="checkbox"
              checked={form.relaxed_understaffing}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, relaxed_understaffing: e.target.checked }))
              }
            />
            <span>
              Relaxed understaffing scenario — shortfalls become soft penalties (labeled, not default)
            </span>
          </label>
        </div>

        <h2 className="mt-6 text-sm font-semibold">Soft objective weights</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {WEIGHT_KEYS.map((key) => (
            <NumberField
              key={key}
              label={key}
              value={form.weights[key]}
              onChange={(value) =>
                setForm((prev) => ({
                  ...prev,
                  weights: { ...prev.weights, [key]: value },
                }))
              }
            />
          ))}
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Button onClick={() => save.mutate()} disabled={save.isPending}>
            {save.isPending ? "Saving…" : "Save ruleset"}
          </Button>
          {save.isSuccess ? <span className="text-sm text-emerald-700">Saved.</span> : null}
          {save.isError ? <span className="text-sm text-rose-600">{save.error.message}</span> : null}
        </div>
      </Card>
    </div>
  );
}

function NumberField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block text-sm">
      <span className="text-stone-500">{label}</span>
      <input
        type="number"
        className="mt-1 w-full rounded-xl border border-stone-300 bg-transparent px-3 py-2 dark:border-stone-700"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  );
}
