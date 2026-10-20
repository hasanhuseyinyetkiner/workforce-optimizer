import {
  CalendarDays,
  Clock3,
  FlaskConical,
  LayoutDashboard,
  Moon,
  Scale,
  Sun,
  Users,
  Wand2,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

const NAV = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/employees", label: "Employees", icon: Users },
  { to: "/shifts", label: "Shifts", icon: Clock3 },
  { to: "/rules", label: "Rules", icon: Scale },
  { to: "/solve", label: "Solve", icon: Wand2 },
  { to: "/schedule", label: "Schedule", icon: CalendarDays },
  { to: "/scenarios", label: "Scenarios", icon: FlaskConical },
];

export function Shell() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));

  function toggleTheme() {
    const next = !dark;
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("workforce-theme", next ? "dark" : "light");
    setDark(next);
  }

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[240px_minmax(0,1fr)]">
      <aside className="flex flex-col bg-[#1c1410] text-stone-100 lg:min-h-screen">
        <div className="px-5 pb-4 pt-6">
          <div className="flex items-center gap-3">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-accent text-sm font-bold text-white">W</span>
            <div>
              <p className="text-sm font-semibold tracking-tight">Workforce Optimizer</p>
              <p className="text-xs text-stone-400">Shift roster solver</p>
            </div>
          </div>
        </div>
        <nav aria-label="Primary" className="flex gap-1 overflow-x-auto px-3 pb-4 lg:flex-col">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-2 rounded-xl px-3 py-2 text-sm ${
                  isActive ? "bg-white/10 text-white" : "text-stone-300 hover:bg-white/5"
                }`
              }
            >
              <item.icon size={16} aria-hidden="true" />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto px-4 py-4">
          <button
            type="button"
            onClick={toggleTheme}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/10 px-3 py-2 text-sm"
            aria-pressed={dark}
            data-testid="theme-toggle"
          >
            {dark ? <Sun size={16} aria-hidden="true" /> : <Moon size={16} aria-hidden="true" />}
            {dark ? "Light theme" : "Dark theme"}
          </button>
        </div>
      </aside>
      <div className="min-w-0">
        <div
          className="bg-accent px-4 py-2 text-center text-sm font-medium text-white"
          data-testid="demo-banner"
        >
          Local demo · synthetic data
        </div>
        <main id="main" className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
