import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { Icon } from "../admin/components/ws";
import { AssistantChat } from "./AssistantChat";
import type { Surface } from "./useAssistant";
import "./assistant.css";

const PAGE_PATH = "/citizen/assistant";

/** Floating CivicFix Assistant, on every page of an app except its own full page. */
export function AssistantLauncher({ surface }: { surface: Surface }) {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (pathname === PAGE_PATH || pathname === "/assistant") return null;
  return (
    <>
      {!open && (
        <button type="button" className="cfa-launcher" onClick={() => setOpen(true)} aria-expanded={false}
          aria-label="Open CivicFix Assistant">
          <Icon name="forum" /> <span>CivicFix Assistant</span>
        </button>
      )}
      {open && (
        <div className="cfa-panel" role="dialog" aria-label="CivicFix Assistant">
          <AssistantChat surface={surface} variant="floating" onClose={() => setOpen(false)} />
        </div>
      )}
    </>
  );
}

/** Full-page assistant. Shares the conversation with the floating one. */
export function AssistantPage({ surface = "citizen" }: { surface?: Surface }) {
  return (
    <section className="cfa-page">
      <div className="cfa-page__intro">
        <p className="cfa-kicker">Report it. Understand it. Track it. Verify it.</p>
        <h1>CivicFix Assistant</h1>
        <p className="cfa-lede">
          {surface === "admin"
            ? "Ask about today's priorities, why an issue ranks where it does, and what the evidence shows. Answers come only from CivicFix records; decisions stay with you."
            : "Don't just submit another complaint. Let CivicFix find the problem behind it."}
        </p>
        <ul className="cfa-page__points">
          <li><Icon name="translate" className="cfa-inline-icon" /> English, हिंदी, मराठी - or a mix</li>
          <li><Icon name="hub" className="cfa-inline-icon" /> Many reports, one Civic Issue</li>
          <li><Icon name="equalizer" className="cfa-inline-icon" /> Priority from a published formula</li>
          <li><Icon name="fact_check" className="cfa-inline-icon" /> Resolved is a status. Verified is evidence.</li>
        </ul>
      </div>
      <div className="cfa-page__chat">
        <AssistantChat surface={surface} variant="page" />
      </div>
    </section>
  );
}
