import { useQuery } from "@tanstack/react-query";

import { api } from "../api";
import { Card, ErrorState, LoadingState, PageIntro } from "../components/ui";
import type { Employee } from "../types";

export function EmployeesPage() {
  const employees = useQuery({
    queryKey: ["employees"],
    queryFn: () => api<Employee[]>("/api/employees"),
  });

  if (employees.isLoading) return <LoadingState label="Loading employees…" />;
  if (employees.isError) return <ErrorState error={employees.error} />;

  return (
    <div>
      <PageIntro
        title="Employees"
        description={`${employees.data!.length} synthetic people with skills, caps, and preferences.`}
      />
      <div className="overflow-x-auto rounded-2xl border border-stone-200/80 bg-white/80 dark:border-stone-800 dark:bg-stone-950/70">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-stone-200 text-xs uppercase tracking-wide text-stone-500 dark:border-stone-800">
            <tr>
              <th className="px-4 py-3 font-medium">Alias</th>
              <th className="px-4 py-3 font-medium">Weekly cap</th>
              <th className="px-4 py-3 font-medium">Cost/hr</th>
              <th className="px-4 py-3 font-medium">Night</th>
              <th className="px-4 py-3 font-medium">Weekend</th>
              <th className="px-4 py-3 font-medium">Skills</th>
            </tr>
          </thead>
          <tbody>
            {employees.data!.map((row) => (
              <tr key={row.id} className="border-b border-stone-100 dark:border-stone-900">
                <td className="px-4 py-3 font-medium">{row.display_alias}</td>
                <td className="px-4 py-3 tabular">{row.weekly_hour_cap}h</td>
                <td className="px-4 py-3 tabular">{row.cost_per_hour}</td>
                <td className="px-4 py-3">{row.night_preference}</td>
                <td className="px-4 py-3">{row.weekend_preference}</td>
                <td className="px-4 py-3 text-stone-600 dark:text-stone-400">{row.skills.join(", ") || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {employees.data!.length === 0 ? (
        <Card className="mt-4 text-sm text-stone-500">No employees loaded. Use Scenarios to seed demo data.</Card>
      ) : null}
    </div>
  );
}
