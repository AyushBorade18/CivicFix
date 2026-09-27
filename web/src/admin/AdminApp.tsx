import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AdminLayout } from "./AdminLayout";
import { CommandCenter } from "./pages/CommandCenter";
import { Overview } from "./pages/Overview";
import { IssueExplorer } from "./pages/IssueExplorer";
import { IssueDetail } from "./pages/IssueDetail";
import { MapView } from "./pages/MapView";
import { WardExplorer } from "./pages/WardExplorer";
import { WardDetail } from "./pages/WardDetail";
import { PublicWorks } from "./pages/PublicWorks";
import { WorkDetail } from "./pages/WorkDetail";
import { Verification } from "./pages/Verification";
import { Analytics } from "./pages/Analytics";
import { HeldReports } from "./pages/HeldReports";
import { RoleDashboard } from "./pages/RoleDashboard";
import { AuditLog, StaffRoles } from "./pages/StaffRoles";
import { StaffGate, useMe } from "./components/StaffGate";

/** Pages only a system administrator may open (the API refuses others too). */
function AdminOnly({ children }: { children: React.ReactNode }) {
  return useMe().role === "system_admin" ? <>{children}</> : <Navigate to="/" replace />;
}

export function AdminApp() {
  return (
    <StaffGate>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AdminLayout />}>
          <Route index element={<RoleDashboard />} />
          <Route path="command" element={<CommandCenter />} />
          <Route path="staff" element={<AdminOnly><StaffRoles /></AdminOnly>} />
          <Route path="audit" element={<AdminOnly><AuditLog /></AdminOnly>} />
          <Route path="overview" element={<Overview />} />
          <Route path="issues" element={<IssueExplorer />} />
          <Route path="issues/:issueId" element={<IssueDetail />} />
          <Route path="map" element={<MapView />} />
          <Route path="wards" element={<WardExplorer />} />
          <Route path="wards/:wardId" element={<WardDetail />} />
          <Route path="works" element={<PublicWorks />} />
          <Route path="works/:workId" element={<WorkDetail />} />
          <Route path="verification" element={<Verification />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="held" element={<HeldReports />} />
          {/* Catch-all redirect to the role dashboard */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
    </StaffGate>
  );
}
export default AdminApp;
