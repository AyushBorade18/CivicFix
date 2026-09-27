import { Outlet } from "react-router-dom";
import { AdminSidebar, AdminTopBar } from "./components/AdminNav";
import { AssistantLauncher } from "../assistant/Assistant";
import "./admin.css";

export function AdminLayout() {
  return (
    <div className="w-screen h-screen overflow-hidden bg-ws-surface text-ws-on-surface font-ws-body antialiased">
      <AdminSidebar />
      <AdminTopBar />
      <main id="admin-main" className="absolute top-16 left-64 right-0 bottom-0 overflow-auto select-text">
        <Outlet />
      </main>
      <AssistantLauncher surface="admin" />
    </div>
  );
}
