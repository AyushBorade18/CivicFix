import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles/global.css";
import App from "./App";
import { api } from "./api/client";
import { currentToken, initAuth } from "./lib/auth";

// Offline shell and install support. Production builds only: in dev the
// service worker would cache Vite's live modules.
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => undefined));
}

// Restore the session before first render, so pages don't flash "sign in".
initAuth()
  .then(() => {
    // Signed in without typing a code (emailed link, dev #token= link, restored
    // session): make sure a citizen account exists before pages call the API.
    // Idempotent, so an existing account is untouched.
    if (currentToken()) return api.register().then(() => undefined, () => undefined);
  })
  .finally(() =>
    createRoot(document.getElementById("root")!).render(
      <StrictMode>
        <App />
      </StrictMode>,
    ),
  );
