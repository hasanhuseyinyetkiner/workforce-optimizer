import { Navigate, Route, Routes } from "react-router-dom";

import { Shell } from "./components/Shell";
import { EmployeesPage } from "./pages/EmployeesPage";
import { OverviewPage } from "./pages/OverviewPage";
import { SchedulePage } from "./pages/SchedulePage";
import { ScenariosPage } from "./pages/ScenariosPage";
import { ShiftsPage } from "./pages/ShiftsPage";
import { SolvePage } from "./pages/SolvePage";

export default function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<OverviewPage />} />
        <Route path="employees" element={<EmployeesPage />} />
        <Route path="shifts" element={<ShiftsPage />} />
        <Route path="solve" element={<SolvePage />} />
        <Route path="schedule" element={<SchedulePage />} />
        <Route path="scenarios" element={<ScenariosPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
