import { useState } from "react";
import { api } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { CATEGORY_LABELS } from "../../api/types";
import type { CrewAssignment } from "../../api/types";
import { EvidenceUpload } from "../../evidence/EvidenceUpload";
import { captureAndUpload } from "../../evidence/pendingUploads";
import { useEvidencePhoto } from "../components/EvidenceTimeline";
import { Card, Icon, SectionLabel, Skeleton, fmtDate, issueCode } from "../components/ws";
import { useMe } from "../components/StaffGate";
import "../admin.css";

// What a crew member (field_worker) sees after signing in: the issues an
// officer assigned to them, the citizen's photo, and one action - upload the
// completion photo. The officer then reviews it and closes the issue.

export function CrewHome() {
  const me = useMe();
  const { data, loading, error, reload } = useApi(() => api.myAssignments(), []);
  const open = data?.filter((j) => j.status !== "closed") ?? [];
  const done = data?.filter((j) => j.status === "closed") ?? [];

  return (
    <div className="min-h-screen bg-ws-surface text-ws-on-surface font-ws-label">
      <header className="h-14 bg-ws-navy text-white flex items-center gap-2 px-4">
        <Icon name="engineering" className="text-[22px] text-ws-blue" />
        <span className="font-ws-headline text-sm font-semibold uppercase tracking-tight">WardSentry Crew</span>
        <span className="ml-auto text-xs text-ws-surface-variant">{me.display_name ?? me.email}</span>
      </header>
      <main className="max-w-3xl mx-auto p-4 flex flex-col gap-4 pb-16">
        <div className="flex items-center justify-between">
          <SectionLabel>My jobs</SectionLabel>
          <button onClick={reload} className="text-xs text-ws-blue font-semibold flex items-center gap-1">
            <Icon name="refresh" className="text-[16px]" /> Refresh
          </button>
        </div>
        {error && <Card className="p-4 text-sm text-ws-error">Couldn't load your jobs: {error}</Card>}
        {loading && !data && <Skeleton className="h-40" />}
        {data && open.length === 0 && (
          <Card className="p-6 text-sm text-[#535f74]">
            No open jobs assigned to you. An officer assigns jobs from the admin portal; tap Refresh to check again.
          </Card>
        )}
        {open.map((job) => <JobCard key={job.issue_id} job={job} onUploaded={reload} />)}
        {done.length > 0 && (
          <>
            <SectionLabel>Closed</SectionLabel>
            {done.map((job) => (
              <Card key={job.issue_id} className="p-3 text-xs text-[#535f74]">
                {issueCode(job.issue_id)} · {CATEGORY_LABELS[job.category] ?? job.category} · {job.ward_name ?? "Ward unknown"}
              </Card>
            ))}
          </>
        )}
      </main>
    </div>
  );
}

function JobCard({ job, onUploaded }: { job: CrewAssignment; onUploaded: () => void }) {
  const { data: evidence } = useApi(() => api.listEvidence(job.issue_id), [job.issue_id]);
  const before = evidence?.find((e) => e.evidence_type === "initial_report") ?? null;
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const maps = job.location ? `https://www.google.com/maps?q=${job.location.lat},${job.location.lon}` : null;

  return (
    <Card className="p-4 flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="px-1.5 py-0.5 rounded bg-ws-navy text-white font-bold">{issueCode(job.issue_id)}</span>
        <span className="font-semibold">{CATEGORY_LABELS[job.category] ?? job.category}</span>
        <span className="text-[#535f74]">{job.ward_name ?? "Ward unknown"}</span>
        <span className="ml-auto text-[#535f74]">Assigned {fmtDate(job.assigned_at)}</span>
      </div>
      {job.complaint_text && <p className="font-ws-body text-sm whitespace-pre-wrap break-words">{job.complaint_text}</p>}
      <div className="flex flex-wrap gap-3 text-xs">
        {job.location_phrase && <span><b>Landmark:</b> {job.location_phrase}</span>}
        {maps && (
          <a href={maps} target="_blank" rel="noreferrer" className="text-ws-blue font-semibold flex items-center gap-1">
            <Icon name="map" className="text-[16px]" /> Open in Maps
          </a>
        )}
      </div>
      {before && <BeforePhoto fileUrl={before.file_url} />}

      {job.resolution_submitted ? (
        <p className="text-xs text-ws-primary flex items-center gap-1">
          <Icon name="check_circle" className="text-[18px]" /> Completion photo sent. Waiting for the officer to review and close.
        </p>
      ) : (
        <button onClick={() => setUploading(true)}
          className="self-start px-4 py-2 rounded bg-ws-blue hover:bg-ws-primary text-white text-xs font-semibold flex items-center gap-1.5">
          <Icon name="upload" className="text-[18px]" /> Upload completion photo
        </button>
      )}
      {msg && <p className={`text-xs ${msg.ok ? "text-ws-primary" : "text-ws-error"}`}>{msg.text}</p>}

      {uploading && (
        <EvidenceUpload
          title={`Completion photo · ${issueCode(job.issue_id)}`}
          onCancel={() => setUploading(false)}
          onConfirm={async (pkg) => {
            setUploading(false);
            const result = await captureAndUpload(job.issue_id, pkg);
            setMsg(result.ok ? { ok: true, text: "Completion photo sent." } : { ok: false, text: result.message });
            if (result.ok) onUploaded();
          }}
        />
      )}
    </Card>
  );
}

function BeforePhoto({ fileUrl }: { fileUrl: string }) {
  const { src, failed } = useEvidencePhoto(fileUrl);
  if (failed) return <p className="text-xs text-ws-error">Citizen's photo couldn't be loaded.</p>;
  return (
    <figure className="flex flex-col gap-1">
      {src ? <img src={src} alt="Citizen's photo of the problem" className="max-h-64 rounded object-cover" />
        : <Skeleton className="h-40" />}
      <figcaption className="text-[11px] text-[#535f74]">Citizen's photo (before)</figcaption>
    </figure>
  );
}
