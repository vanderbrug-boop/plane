/**
 * CRO Management Dashboard
 *
 * Displays:
 * - CRO cards with health scores (AI-generated)
 * - Deliverable timeline with status
 * - KPI trends and comparisons
 * - Budget tracking per CRO
 */

import React, { useEffect, useState } from "react";

interface CROSummary {
  cro_id: string;
  cro_name: string;
  status: string;
  total_deliverables: number;
  completed_deliverables: number;
  overdue_deliverables: number;
  kpis_on_target: number;
  kpis_total: number;
  avg_quality_score: number | null;
  contract_value: string | null;
  dpa_signed: boolean;
}

interface Deliverable {
  id: string;
  cro_name: string;
  title: string;
  status: string;
  due_date: string;
  is_overdue: boolean;
  days_until_due: number;
  quality_score: number | null;
}

function HealthIndicator({ overdue, total, kpisOnTarget, kpisTotal }: {
  overdue: number;
  total: number;
  kpisOnTarget: number;
  kpisTotal: number;
}) {
  const deliveryRate = total > 0 ? (total - overdue) / total : 1;
  const kpiRate = kpisTotal > 0 ? kpisOnTarget / kpisTotal : 1;
  const score = (deliveryRate + kpiRate) / 2;

  let color: string;
  let label: string;
  if (score >= 0.8) {
    color = "bg-green-500";
    label = "Healthy";
  } else if (score >= 0.6) {
    color = "bg-yellow-500";
    label = "At Risk";
  } else {
    color = "bg-red-500";
    label = "Critical";
  }

  return (
    <div className="flex items-center gap-2">
      <div className={`w-3 h-3 rounded-full ${color}`} />
      <span className="text-sm font-medium">{label}</span>
    </div>
  );
}

function CROCard({ cro, onGenerateScorecard }: {
  cro: CROSummary;
  onGenerateScorecard: (croId: string) => void;
}) {
  const completionPct =
    cro.total_deliverables > 0
      ? Math.round((100 * cro.completed_deliverables) / cro.total_deliverables)
      : 0;

  return (
    <div className="bg-white rounded-lg shadow p-5 border border-gray-200">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="font-semibold text-gray-900">{cro.cro_name}</h3>
          <span className="text-xs text-gray-500 capitalize">{cro.status}</span>
        </div>
        <HealthIndicator
          overdue={cro.overdue_deliverables}
          total={cro.total_deliverables}
          kpisOnTarget={cro.kpis_on_target}
          kpisTotal={cro.kpis_total}
        />
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm mb-3">
        <div>
          <p className="text-gray-500">Deliverables</p>
          <p className="font-medium">
            {cro.completed_deliverables} / {cro.total_deliverables} ({completionPct}%)
          </p>
        </div>
        <div>
          <p className="text-gray-500">Overdue</p>
          <p className={`font-medium ${cro.overdue_deliverables > 0 ? "text-red-600" : "text-green-600"}`}>
            {cro.overdue_deliverables}
          </p>
        </div>
        <div>
          <p className="text-gray-500">KPIs On Target</p>
          <p className="font-medium">
            {cro.kpis_on_target} / {cro.kpis_total}
          </p>
        </div>
        <div>
          <p className="text-gray-500">Avg Quality</p>
          <p className="font-medium">
            {cro.avg_quality_score ? `${cro.avg_quality_score.toFixed(1)} / 5` : "—"}
          </p>
        </div>
      </div>

      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-1">
          {cro.dpa_signed ? (
            <span className="text-green-600">DPA Signed</span>
          ) : (
            <span className="text-red-600">DPA Missing</span>
          )}
        </div>
        {cro.contract_value && (
          <span className="text-gray-500">
            Contract: ${parseFloat(cro.contract_value).toLocaleString()}
          </span>
        )}
      </div>

      <button
        onClick={() => onGenerateScorecard(cro.cro_id)}
        className="mt-3 w-full text-center text-sm py-1.5 bg-blue-50 text-blue-600 rounded hover:bg-blue-100 transition"
      >
        Generate AI Scorecard
      </button>
    </div>
  );
}

function DeliverableRow({ deliverable }: { deliverable: Deliverable }) {
  const statusColors: Record<string, string> = {
    pending: "text-gray-500",
    in_progress: "text-blue-600",
    delivered: "text-purple-600",
    under_review: "text-yellow-600",
    accepted: "text-green-600",
    rejected: "text-red-600",
    overdue: "text-red-600",
  };

  return (
    <tr className={deliverable.is_overdue ? "bg-red-50" : ""}>
      <td className="px-4 py-2 text-sm">{deliverable.title}</td>
      <td className="px-4 py-2 text-sm text-gray-500">{deliverable.cro_name}</td>
      <td className="px-4 py-2 text-sm">{deliverable.due_date}</td>
      <td className={`px-4 py-2 text-sm font-medium ${statusColors[deliverable.status] || ""}`}>
        {deliverable.is_overdue ? "OVERDUE" : deliverable.status.replace(/_/g, " ")}
      </td>
      <td className="px-4 py-2 text-sm text-center">
        {deliverable.quality_score ? `${deliverable.quality_score}/5` : "—"}
      </td>
    </tr>
  );
}

export default function CRODashboard({ workspaceId }: { workspaceId: string }) {
  const [cros, setCros] = useState<CROSummary[]>([]);
  const [deliverables, setDeliverables] = useState<Deliverable[]>([]);
  const [aiScorecard, setAiScorecard] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [scorecardLoading, setScorecardLoading] = useState(false);

  useEffect(() => {
    async function fetchData() {
      try {
        const [dashRes, delivRes] = await Promise.all([
          fetch(`/api/v1/workspaces/${workspaceId}/clinical/cro-dashboard/`),
          fetch(`/api/v1/workspaces/${workspaceId}/clinical/cro-deliverables/`),
        ]);

        if (dashRes.ok) setCros(await dashRes.json());
        if (delivRes.ok) {
          const data = await delivRes.json();
          setDeliverables(Array.isArray(data) ? data : data.results || []);
        }
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [workspaceId]);

  async function handleGenerateScorecard(croId: string) {
    setScorecardLoading(true);
    setAiScorecard(null);
    try {
      const res = await fetch(`/api/v1/workspaces/${workspaceId}/ai/cro-scorecard/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cro_id: croId }),
      });
      if (res.ok) {
        const data = await res.json();
        setAiScorecard(data.scorecard);
      }
    } finally {
      setScorecardLoading(false);
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
      <h1 className="text-2xl font-bold text-gray-900">CRO Management</h1>

      {/* CRO Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {cros.map((cro) => (
          <CROCard key={cro.cro_id} cro={cro} onGenerateScorecard={handleGenerateScorecard} />
        ))}
        {cros.length === 0 && (
          <p className="text-gray-500 col-span-3 text-center py-8">No active CROs.</p>
        )}
      </div>

      {/* AI Scorecard Result */}
      {(scorecardLoading || aiScorecard) && (
        <div className="bg-white rounded-lg shadow p-6 border border-blue-200">
          <h2 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
            AI-Generated CRO Scorecard
          </h2>
          {scorecardLoading ? (
            <div className="flex items-center gap-2 text-gray-500">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600" />
              Analyzing CRO performance...
            </div>
          ) : (
            <div className="prose prose-sm max-w-none whitespace-pre-wrap">{aiScorecard}</div>
          )}
        </div>
      )}

      {/* Deliverables Table */}
      <div className="bg-white rounded-lg shadow border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Deliverables</h2>
        </div>
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Title</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">CRO</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Due Date</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
              <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">Quality</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {deliverables.map((d) => (
              <DeliverableRow key={d.id} deliverable={d} />
            ))}
          </tbody>
        </table>
        {deliverables.length === 0 && (
          <p className="text-gray-500 text-center py-8">No deliverables tracked.</p>
        )}
      </div>
    </div>
  );
}
