"use client";

import React from 'react';
import { Activity, FileText, Database } from 'lucide-react';
import Link from 'next/link';

export default function MetricsDashboard() {
  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 text-text">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-text mb-2">Metrics &amp; Observability</h1>
        <p className="text-muted text-sm">
          Tenant-scoped telemetry, extraction volume, and pipeline execution logs.
        </p>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-panel p-6 rounded-lg border border-border backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <span className="text-muted text-sm font-medium">Total Entities Extracted</span>
            <Database className="w-5 h-5 text-muted" />
          </div>
          <p className="text-3xl font-bold font-mono mt-3 text-text">0</p>
          <p className="text-xs text-muted mt-2">No entities extracted yet</p>
        </div>

        <div className="bg-panel p-6 rounded-lg border border-border backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <span className="text-muted text-sm font-medium">Ingested Documents</span>
            <FileText className="w-5 h-5 text-muted" />
          </div>
          <p className="text-3xl font-bold font-mono mt-3 text-text">0</p>
          <p className="text-xs text-muted mt-2">No documents ingested yet</p>
        </div>

        <div className="bg-panel p-6 rounded-lg border border-border backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <span className="text-muted text-sm font-medium">Pipeline Status</span>
            <Activity className="w-5 h-5 text-muted" />
          </div>
          <p className="text-3xl font-bold font-mono mt-3 text-teal">Idle</p>
          <p className="text-xs text-muted mt-2">Awaiting ingestion requests</p>
        </div>
      </div>

      {/* Chart and Feed Section with honest empty states */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Extraction Volume */}
        <div className="lg:col-span-2 bg-panel p-6 rounded-lg border border-border backdrop-blur-sm flex flex-col">
          <h2 className="text-lg font-semibold text-text mb-4">Extraction Volume over Time</h2>
          <div className="flex-1 min-h-[260px] flex flex-col items-center justify-center border border-dashed border-border rounded-lg p-8 text-center">
            <Activity className="w-10 h-10 text-muted mb-3" />
            <p className="text-sm font-medium text-text">No extraction volume recorded yet</p>
            <p className="text-xs text-muted mt-1 max-w-sm">
              Extraction volume metrics will display here once documents are processed through the extraction pipeline.
            </p>
            <Link
              href="/dashboard/explorer"
              className="mt-4 px-4 py-2 text-xs font-semibold rounded-lg bg-teal hover:bg-teal/80 text-page transition-colors"
            >
              Go to Graph Explorer
            </Link>
          </div>
        </div>

        {/* Activity Feed */}
        <div className="bg-panel p-6 rounded-lg border border-border backdrop-blur-sm flex flex-col">
          <h2 className="text-lg font-semibold text-text mb-4">Recent Activity</h2>
          <div className="flex-1 min-h-[260px] flex flex-col items-center justify-center border border-dashed border-border rounded-lg p-6 text-center">
            <FileText className="w-10 h-10 text-muted mb-3" />
            <p className="text-sm font-medium text-text">No recent activity</p>
            <p className="text-xs text-muted mt-1 max-w-xs">
              Document uploads, chunking runs, and entity resolutions will appear in this feed.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
