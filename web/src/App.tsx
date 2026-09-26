import { Navigate, Route, BrowserRouter, Routes } from "react-router-dom";
import { Landing } from "./pages/Landing";
import { CitizenLayout } from "./citizen/CitizenLayout";
import { ReportIssue } from "./citizen/pages/ReportIssue";
import { PublicIssues } from "./citizen/pages/PublicIssues";
import { PublicIssueDetail } from "./citizen/pages/PublicIssueDetail";
import { MyReports } from "./citizen/pages/MyReports";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Citizen site: one shell (Stitch "Sentry Editorial Civic") for every page */}
        <Route element={<CitizenLayout />}>
          <Route path="/" element={<Landing />} />
          <Route path="/citizen" element={<Navigate to="/" replace />} />
          <Route path="/citizen/report" element={<ReportIssue />} />
          <Route path="/citizen/my-reports" element={<MyReports />} />
          <Route path="/citizen/issues" element={<PublicIssues />} />
          <Route path="/citizen/issues/:issueId" element={<PublicIssueDetail />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
