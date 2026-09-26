import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles/global.css";
import App from "./App";
import { api } from "./api/client";
import { initAuth } from "./lib/auth";

// Offline shell and install support. Production builds only: in dev the
// service worker would cache Vite's live modules.
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => undefined));
}

// Restore the session before first render, so pages don't flash "sign in".
initAuth()
  .then((devTokenFromUrl) => {
    // Dev sign-in link: make sure a citizen account exists (idempotent).
    if (devTokenFromUrl) api.register().catch(() => undefined);
  })
  .finally(() =>
    createRoot(document.getElementById("root")!).render(
      <StrictMode>
        <App />
      </StrictMode>,
    ),
  );
