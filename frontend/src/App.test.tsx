import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import App from "./App";

vi.stubGlobal(
  "fetch",
  vi.fn(async () =>
    Response.json({
      demo: true,
      synthetic_data: true,
      organization_name: "Demo Org",
      planning_timezone: "UTC",
      counts: { employees: 0, shifts: 0, skills: 0 },
      latest_run: null,
      recent_runs: [],
      schedule: null,
    }),
  ),
);

describe("App smoke", () => {
  it("renders shell navigation and demo banner", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <App />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByTestId("demo-banner")).toHaveTextContent("Local demo · synthetic data");
    expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Overview" })).toBeInTheDocument();
  });
});
