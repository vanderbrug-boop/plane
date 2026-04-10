/**
 * Regulatory Submission Tracker
 *
 * Kanban-style view of IND/CTA submissions with:
 * - Section-by-section completion tracking
 * - Review clock countdown timer
 * - AI-powered gap analysis
 */

import React, { useEffect, useState } from "react";

interface Section {
  id: string;
  section_key: string;
  section_name: string;
  status: string;
  completion_pct: number;
  due_date: string | null;
  assigned_to: string | null;
}

interface Submission {
  id: string;
  submission_type: string;
  authority: string;
  country: string;
  status: string;
  reference_number: string;
  review_days_remaining: number | null;
  is_overdue: boolean;
  sections: Section[];
  submitted_at: string | null;
  review_deadline: string | null;
}

const KANBAN_COLUMNS = [
  { key: "drafting", label: "Drafting" },
  { key: "internal_review", label: "Internal Review" },
  { key: "submitted", label: "Submitted" },
  { key: "under_review", label: "Under Review" },
  { key: "approved", label: "Approved" },
];

const STATUS_ICONS: Record<string, string> = {
  not_started: "bg-gray-300",
  in_progress: "bg-blue-400",
  draft_complete: "bg-yellow-400",
  review: "bg-purple-400",
  finalized: "bg-green-500",
};

function ReviewClock({ daysRemaining, isOverdue }: { daysRemaining: number | null; isOverdue: boolean }) {
  if (daysRemaining === null) return null;

  let color: string;
  if (isOverdue) color = "text-red-600 bg-red-50";
  else if (daysRemaining <= 7) color = "text-yellow-700 bg-yellow-50";
  else color = "text-green-700 bg-green-50";

  return (
    <div className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${color}`}>
      {isOverdue ? "OVERDUE" : `${daysRemaining}d remaining`}
    </div>
  );
}

function SectionChecklist({ sections }: { sections: Section[] }) {
  const completed = sections.filter((s) => s.status === "finalized").length;
  const total = sections.length;

  return (
    <div className="mt-2">
      <div className="flex justify-between text-xs text-gray-500 mb-1">
        <span>Sections</span>
        <span>
          {completed}/{total}
        </span>
      </div>
      <div className="space-y-1">
        {sections.map((section) => (
          <div key={section.id} className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${STATUS_ICONS[section.status] || "bg-gray-300"}`} />
            <span className="text-xs text-gray-700 flex-1 truncate">{section.section_name}</span>
            <span className="text-xs text-gray-400">{section.completion_pct}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function SubmissionKanbanCard({ submission }: { submission: Submission }) {
  const totalPct =
    submission.sections.length > 0
      ? Math.round(
          submission.sections.reduce((sum, s) => sum + s.completion_pct, 0) / submission.sections.length
        )
      : 0;

  return (
    <div className="bg-white rounded-lg shadow-sm p-4 border border-gray-200 mb-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <span className="font-semibold text-sm">{submission.submission_type}</span>
          <span className="text-xs text-gray-500">{submission.country}</span>
        </div>
        <span className="text-xs text-gray-400">{submission.authority}</span>
      </div>

      {submission.reference_number && (
        <p className="text-xs text-gray-500 mb-2">Ref: {submission.reference_number}</p>
      )}

      {/* Overall progress bar */}
      <div className="w-full bg-gray-200 rounded-full h-1.5 mb-2">
        <div className="h-1.5 rounded-full bg-blue-500" style={{ width: `${totalPct}%` }} />
      </div>
      <div className="text-xs text-gray-500 text-right mb-2">{totalPct}% complete</div>

      <ReviewClock daysRemaining={submission.review_days_remaining} isOverdue={submission.is_overdue} />

      <SectionChecklist sections={submission.sections} />
    </div>
  );
}

export default function SubmissionTracker({ workspaceId }: { workspaceId: string }) {
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [aiAnalysis, setAiAnalysis] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  useEffect(() => {
    async function fetchData() {
      try {
        const res = await fetch(`/api/v1/workspaces/${workspaceId}/clinical/submissions/`);
        if (res.ok) {
          const data = await res.json();
          // Fetch full details for each submission (with sections)
          const detailed = await Promise.all(
            (Array.isArray(data) ? data : data.results || []).map(async (sub: any) => {
              const detailRes = await fetch(
                `/api/v1/workspaces/${workspaceId}/clinical/submissions/${sub.id}/`
              );
              return detailRes.ok ? detailRes.json() : sub;
            })
          );
          setSubmissions(detailed);
        }
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [workspaceId]);

  async function handleRunGapAnalysis() {
    setAnalysisLoading(true);
    setAiAnalysis(null);
    try {
      const res = await fetch(`/api/v1/workspaces/${workspaceId}/ai/regulatory-analysis/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (res.ok) {
        const data = await res.json();
        setAiAnalysis(data.analysis);
      }
    } finally {
      setAnalysisLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Regulatory Submissions</h1>
        <button
          onClick={handleRunGapAnalysis}
          disabled={analysisLoading}
          className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 transition"
        >
          {analysisLoading ? "Analyzing..." : "AI Gap Analysis"}
        </button>
      </div>

      {/* AI Analysis Result */}
      {(analysisLoading || aiAnalysis) && (
        <div className="bg-white rounded-lg shadow p-6 border border-blue-200">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">AI Regulatory Gap Analysis</h2>
          {analysisLoading ? (
            <div className="flex items-center gap-2 text-gray-500">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600" />
              Analyzing submissions for gaps and risks...
            </div>
          ) : (
            <div className="prose prose-sm max-w-none whitespace-pre-wrap">{aiAnalysis}</div>
          )}
        </div>
      )}

      {/* Kanban Board */}
      <div className="flex gap-4 overflow-x-auto pb-4">
        {KANBAN_COLUMNS.map((col) => {
          const columnSubmissions = submissions.filter((s) => s.status === col.key);
          return (
            <div key={col.key} className="flex-shrink-0 w-72">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-700">{col.label}</h3>
                <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
                  {columnSubmissions.length}
                </span>
              </div>
              <div className="bg-gray-50 rounded-lg p-3 min-h-[200px]">
                {columnSubmissions.map((sub) => (
                  <SubmissionKanbanCard key={sub.id} submission={sub} />
                ))}
                {columnSubmissions.length === 0 && (
                  <p className="text-xs text-gray-400 text-center py-8">Empty</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
