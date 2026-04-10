/**
 * Clinical Trial Dashboard — Main overview page.
 *
 * Displays:
 * - Trial overview (phase, status, enrollment progress)
 * - Site map by country with status indicators
 * - Enrollment chart (actual vs. forecast)
 * - Regulatory submission status cards
 */

import React, { useEffect, useState } from "react";

// Types
interface Trial {
  id: string;
  protocol_number: string;
  protocol_title: string;
  phase: string;
  indication: string;
  status: string;
  target_enrollment: number;
  current_enrollment: number;
  enrollment_pct: number;
  screen_failure_rate: number;
  site_count: number;
  sites_active: number;
  countries: string[];
  first_patient_in: string | null;
  last_patient_in: string | null;
}

interface Submission {
  id: string;
  submission_type: string;
  authority: string;
  country: string;
  status: string;
  review_days_remaining: number | null;
  is_overdue: boolean;
  section_count: number;
  sections_complete: number;
}

interface SiteByCountry {
  [country: string]: {
    target: number;
    actual: number;
    sites: number;
    active_sites: number;
  };
}

// Status badge colors
const STATUS_COLORS: Record<string, string> = {
  planning: "bg-gray-100 text-gray-700",
  ind_cta_prep: "bg-yellow-100 text-yellow-700",
  startup: "bg-blue-100 text-blue-700",
  enrolling: "bg-green-100 text-green-700",
  fully_enrolled: "bg-emerald-100 text-emerald-700",
  data_lock: "bg-purple-100 text-purple-700",
  completed: "bg-teal-100 text-teal-700",
  approved: "bg-green-100 text-green-700",
  submitted: "bg-blue-100 text-blue-700",
  under_review: "bg-yellow-100 text-yellow-700",
  clinical_hold: "bg-red-100 text-red-700",
  drafting: "bg-gray-100 text-gray-700",
};

// Components

function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status] || "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
    </span>
  );
}

function ProgressBar({ value, max, label }: { value: number; max: number; label?: string }) {
  const pct = max > 0 ? Math.round((100 * value) / max) : 0;
  const barColor = pct >= 75 ? "bg-green-500" : pct >= 50 ? "bg-yellow-500" : "bg-blue-500";

  return (
    <div>
      {label && (
        <div className="flex justify-between text-sm mb-1">
          <span className="text-gray-600">{label}</span>
          <span className="font-medium">
            {value} / {max} ({pct}%)
          </span>
        </div>
      )}
      <div className="w-full bg-gray-200 rounded-full h-2.5">
        <div className={`h-2.5 rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function TrialOverviewCard({ trial }: { trial: Trial }) {
  return (
    <div className="bg-white rounded-lg shadow p-6 border border-gray-200">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">{trial.protocol_number}</h2>
          <p className="text-sm text-gray-500">{trial.indication}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-700">{trial.phase}</span>
          <StatusBadge status={trial.status} />
        </div>
      </div>

      <ProgressBar
        value={trial.current_enrollment}
        max={trial.target_enrollment}
        label="Enrollment"
      />

      <div className="grid grid-cols-4 gap-4 mt-4">
        <div>
          <p className="text-xs text-gray-500">Sites</p>
          <p className="text-lg font-semibold">
            {trial.sites_active} / {trial.site_count}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Countries</p>
          <p className="text-lg font-semibold">{trial.countries.length}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Screen Failure</p>
          <p className="text-lg font-semibold">{trial.screen_failure_rate}%</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">First Patient In</p>
          <p className="text-lg font-semibold">
            {trial.first_patient_in || "—"}
          </p>
        </div>
      </div>
    </div>
  );
}

function SubmissionCard({ submission }: { submission: Submission }) {
  const completionPct =
    submission.section_count > 0
      ? Math.round((100 * submission.sections_complete) / submission.section_count)
      : 0;

  return (
    <div className="bg-white rounded-lg shadow p-4 border border-gray-200">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm">{submission.submission_type}</span>
          <span className="text-xs text-gray-500">{submission.authority}</span>
          <span className="text-xs text-gray-500">{submission.country}</span>
        </div>
        <StatusBadge status={submission.status} />
      </div>

      <ProgressBar
        value={submission.sections_complete}
        max={submission.section_count}
        label="Sections"
      />

      {submission.review_days_remaining !== null && (
        <div className="mt-2 flex items-center gap-1">
          <span className="text-xs text-gray-500">Review clock:</span>
          <span
            className={`text-xs font-medium ${
              submission.is_overdue ? "text-red-600" : submission.review_days_remaining <= 7 ? "text-yellow-600" : "text-green-600"
            }`}
          >
            {submission.is_overdue
              ? "OVERDUE"
              : `${submission.review_days_remaining} days remaining`}
          </span>
        </div>
      )}
    </div>
  );
}

function EnrollmentByCountry({ data }: { data: SiteByCountry }) {
  const countries = Object.entries(data).sort(([, a], [, b]) => b.actual - a.actual);

  return (
    <div className="bg-white rounded-lg shadow p-6 border border-gray-200">
      <h3 className="text-md font-semibold text-gray-900 mb-4">Enrollment by Country</h3>
      <div className="space-y-3">
        {countries.map(([country, stats]) => (
          <div key={country}>
            <div className="flex justify-between text-sm mb-1">
              <span className="font-medium">{country}</span>
              <span className="text-gray-500">
                {stats.actual} / {stats.target} ({stats.active_sites} active sites)
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="h-2 rounded-full bg-blue-500"
                style={{ width: `${stats.target > 0 ? (100 * stats.actual) / stats.target : 0}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Main Dashboard Component
export default function TrialDashboard({
  workspaceId,
}: {
  workspaceId: string;
}) {
  const [trials, setTrials] = useState<Trial[]>([]);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [enrollmentData, setEnrollmentData] = useState<SiteByCountry>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const [trialsRes, submissionsRes] = await Promise.all([
          fetch(`/api/clinical/workspaces/${workspaceId}/clinical/trials/`),
          fetch(`/api/clinical/workspaces/${workspaceId}/clinical/submissions/`),
        ]);

        if (trialsRes.ok) setTrials(await trialsRes.json());
        if (submissionsRes.ok) setSubmissions(await submissionsRes.json());

        // Fetch enrollment data for first trial
        const trialsData = await trialsRes.json().catch(() => []);
        if (trialsData.length > 0) {
          const enrollRes = await fetch(
            `/api/clinical/workspaces/${workspaceId}/clinical/trials/${trialsData[0].id}/enrollment/`
          );
          if (enrollRes.ok) {
            const enrollment = await enrollRes.json();
            setEnrollmentData(enrollment.by_country || {});
          }
        }
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [workspaceId]);

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
        <h1 className="text-2xl font-bold text-gray-900">Clinical Trial Dashboard</h1>
      </div>

      {/* Trial Overview Cards */}
      <div className="space-y-4">
        {trials.map((trial) => (
          <TrialOverviewCard key={trial.id} trial={trial} />
        ))}
        {trials.length === 0 && (
          <p className="text-gray-500 text-center py-8">
            No clinical trials configured. Create a trial to get started.
          </p>
        )}
      </div>

      {/* Enrollment by Country */}
      {Object.keys(enrollmentData).length > 0 && (
        <EnrollmentByCountry data={enrollmentData} />
      )}

      {/* Regulatory Submissions */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Regulatory Submissions</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {submissions.map((sub) => (
            <SubmissionCard key={sub.id} submission={sub} />
          ))}
          {submissions.length === 0 && (
            <p className="text-gray-500 col-span-3 text-center py-4">
              No regulatory submissions yet.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
