import { Link } from "react-router-dom";
import type { ChatCard } from "../api/types";
import { Icon } from "../admin/components/ws";

const CARD_ICON: Record<ChatCard["type"], string> = {
  issue: "hub",
  priority: "equalizer",
  work: "construction",
  outcome: "timeline",
  summary: "edit_note",
  briefing: "today",
  verification: "fact_check",
  history: "history",
  list: "list",
};

/** One structured answer. Everything on it came from a CivicFix record; the
 * "View evidence" fold names those records. */
export function CardView({ card, onItem, disabled }: {
  card: ChatCard;
  onItem: (action: string, value: string | null, label: string) => void;
  disabled: boolean;
}) {
  return (
    <article className={`cfa-card cfa-tone-${card.tone ?? "neutral"}`}>
      <header className="cfa-card__head">
        <Icon name={CARD_ICON[card.type]} className="cfa-card__icon" />
        <div className="cfa-card__titles">
          <h4>{card.title}</h4>
          {card.subtitle && <p>{card.subtitle}</p>}
        </div>
        {card.badge && <span className="cfa-badge">{card.badge}</span>}
      </header>

      {card.rows.length > 0 && (
        <dl className="cfa-rows">
          {card.rows.map((r, i) => (
            <div key={i}><dt>{r.label}</dt><dd>{r.value}</dd></div>
          ))}
        </dl>
      )}

      {card.factors.length > 0 && (
        <ul className="cfa-factors">
          {card.factors.map((f, i) => (
            <li key={i}><span>{f.label}</span>{f.points != null && <b>+{f.points}</b>}</li>
          ))}
        </ul>
      )}

      {card.steps.length > 0 && (
        <ol className="cfa-steps">
          {card.steps.map((s, i) => (
            <li key={i}><span>{s.label}</span><b>{s.value}</b></li>
          ))}
        </ol>
      )}

      {card.items.length > 0 && (
        <ul className="cfa-items">
          {card.items.map((item, i) => (
            <li key={i}>
              {item.action ? (
                <button type="button" disabled={disabled} onClick={() => onItem(item.action!, item.value, item.title)}>
                  <span>{item.title}</span><small>{item.meta}</small>
                </button>
              ) : (
                <div><span>{item.title}</span><small>{item.meta}</small></div>
              )}
            </li>
          ))}
        </ul>
      )}

      {card.note && <p className="cfa-note">{card.note}</p>}

      {card.evidence.length > 0 && (
        <details className="cfa-evidence">
          <summary>View evidence ({card.evidence.length})</summary>
          <ul>
            {card.evidence.map((e, i) => (
              <li key={i}><b>{e.label}</b><p>{e.detail}</p></li>
            ))}
          </ul>
        </details>
      )}

      {card.href && (
        <Link to={card.href} className="cfa-card__link">
          {card.href_label ?? "Open"} <Icon name="arrow_forward" className="cfa-inline-icon" />
        </Link>
      )}
    </article>
  );
}
