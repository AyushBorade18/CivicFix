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
import { StaffGate } from "./components/StaffGate";

export function AdminApp() {
  return (
    <StaffGate>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AdminLayout />}>
          <Route index element={<CommandCenter />} />
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
          {/* Catch-all redirect to CommandCenter */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
    </StaffGate>
  );
}
export default AdminApp;
