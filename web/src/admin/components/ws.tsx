// Shared pieces of the Stitch "Municipal Spatial Intelligence" admin design.

export function Icon({ name, className = "" }: { name: string; className?: string }) {
  return <span className={`material-symbols-outlined ${className}`} aria-hidden="true">{name}</span>;
}

export const CATEGORY_ICON: Record<string, string> = {
  pothole_road: "add_road",
  drainage_sewage: "water_damage",
  water_supply: "water_drop",
  streetlight: "lightbulb",
  garbage_waste: "delete_sweep",
  footpath: "directions_walk",
  traffic_signage: "traffic",
  other: "priority_high",
};

export const SITE_ICON: Record<string, string> = {
  hospital: "local_hospital",
  school: "school",
  college: "school",
  clinic: "local_hospital",
  heritage: "account_balance",
  bus_stop: "directions_bus",
  water_body: "water",
};

export type Band = "high" | "med" | "low";

/** Same cut-offs the Issues page has always used: >= 0.70 high, >= 0.40 medium. */
export function band(score: number | null | undefined): Band {
  const s = score ?? 0;
  return s >= 0.7 ? "high" : s >= 0.4 ? "med" : "low";
}

export const BAND_CHIP: Record<Band, { label: string; solid: string; soft: string }> = {
  high: { label: "P1 High", solid: "bg-ws-error text-white", soft: "bg-red-100 text-red-800" },
  med: { label: "P2 Med", solid: "bg-amber-500 text-white", soft: "bg-amber-100 text-amber-800" },
  low: { label: "P3 Low", solid: "bg-ws-surface-highest text-ws-on-surface", soft: "bg-ws-surface-container text-ws-on-surface-variant" },
};

export function BandChip({ score, soft = false }: { score: number | null | undefined; soft?: boolean }) {
  const c = BAND_CHIP[band(score)];
  return (
    <span className={`px-1.5 py-0.5 rounded font-ws-label text-[10px] uppercase font-bold whitespace-nowrap ${soft ? c.soft : c.solid}`}>
      {c.label}
    </span>
  );
}

/** A report's landmark, or null when it only restates the ward ("Ward 31"). */
export function landmark(phrase: string | null | undefined) {
  return phrase && !/^ward\s*(no\.?\s*)?\d+$/i.test(phrase.trim()) ? phrase : null;
}

export function issueCode(id: number) {
  return `#PMC-${id}`;
}

export function inr(cost: number | null | undefined) {
  if (cost == null) return "—";
  if (cost >= 1e7) return `₹${(cost / 1e7).toFixed(2)} Cr`;
  if (cost >= 1e5) return `₹${(cost / 1e5).toFixed(1)} L`;
  return `₹${cost.toLocaleString("en-IN")}`;
}

export function fmtTime(iso: string | null | undefined) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function fmtDate(iso: string | number | null | undefined) {
  if (iso == null) return "—";
  return new Date(iso).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export function dms(v: number, pos: string, neg: string) {
  const a = Math.abs(v);
  const d = Math.floor(a);
  const m = Math.floor((a - d) * 60);
  const s = ((a - d - m / 60) * 3600).toFixed(1);
  return `${d}° ${m}' ${s}" ${v >= 0 ? pos : neg}`;
}

/** Great-circle distance in metres. */
export function metres(a: { lat: number; lon: number }, b: { lat: number; lon: number }) {
  const R = 6_371_000;
  const toRad = (x: number) => (x * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLon = toRad(b.lon - a.lon);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

/** Compass bearing from a to b, e.g. "NW". */
export function bearing(a: { lat: number; lon: number }, b: { lat: number; lon: number }) {
  const deg = (Math.atan2(b.lon - a.lon, b.lat - a.lat) * 180) / Math.PI;
  return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][Math.round(((deg + 360) % 360) / 45) % 8];
}

export function Card({ className = "", children }: { className?: string; children: React.ReactNode }) {
  return <div className={`bg-white rounded-xl shadow-[0_1px_3px_rgba(11,25,44,0.04),0_4px_12px_rgba(11,25,44,0.03)] ${className}`}>{children}</div>;
}

export function SectionLabel({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <span className={`font-ws-label text-[11px] text-ws-on-surface-variant uppercase font-semibold tracking-[0.06em] ${className}`}>{children}</span>;
}

export function Segmented<T extends string>({ value, options, onChange }: {
  value: T;
  options: { value: T; label: React.ReactNode }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="bg-ws-surface-container rounded-full p-1 flex items-center shadow-sm font-ws-label">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={`px-3.5 py-1 rounded-full text-xs font-semibold transition-all whitespace-nowrap flex items-center gap-1 ${
            value === o.value ? "bg-ws-blue text-white shadow-sm" : "text-[#535f74] hover:text-ws-on-surface"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** Page frame used by every non-map admin screen. */
export function Page({ children }: { children: React.ReactNode }) {
  return <div className="min-h-full bg-ws-surface font-ws-body text-ws-on-surface">{children}</div>;
}

export function Subheader({ children }: { children: React.ReactNode }) {
  return <div className="px-6 py-2 bg-ws-surface-low flex flex-wrap items-center justify-between gap-4">{children}</div>;
}

export function LivePill({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-ws-primary/10 text-ws-primary font-ws-label text-[11px] font-semibold">
      <span className="w-1.5 h-1.5 rounded-full bg-ws-primary animate-ping" />
      <span>{label}</span>
    </div>
  );
}

export function Skeleton({ className = "h-24" }: { className?: string }) {
  return <div className={`rounded-xl bg-ws-surface-container animate-pulse ${className}`} />;
}
