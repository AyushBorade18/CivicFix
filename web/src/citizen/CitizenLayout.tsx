import { Outlet } from "react-router-dom";
import { SiteHeader, SiteFooter } from "./Shell";

export function CitizenLayout() {
  return (
    <div className="se-root min-h-screen bg-se-surface text-se-on font-se-sans antialiased">
      <a href="#main" className="skip-link">Skip to content</a>
      <SiteHeader />
      <main id="main">
        <Outlet />
      </main>
      <SiteFooter />
    </div>
  );
}
