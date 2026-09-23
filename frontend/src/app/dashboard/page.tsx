"use client";

import React from 'react';
import { Activity, FileText, Database } from 'lucide-react';
import Link from 'next/link';

export default function MetricsDashboard() {
  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 text-gray-100">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-white mb-2">Metrics &amp; Observability</h1>
        <p className="text-gray-400 text-sm">
          Tenant-scoped telemetry, extraction volume, and pipeline execution logs.
        </p>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-gray-900/40 p-6 rounded-xl border border-gray-800 backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <span className="text-gray-400 text-sm font-medium">Total Entities Extracted</span>
            <Database className="w-5 h-5 text-gray-500" />
          </div>
          <p className="text-3xl font-bold font-mono mt-3 text-white">0</p>
          <p className="text-xs text-gray-500 mt-2">No entities extracted yet</p>
        </div>

        <div className="bg-gray-900/40 p-6 rounded-xl border border-gray-800 backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <span className="text-gray-400 text-sm font-medium">Ingested Documents</span>
            <FileText className="w-5 h-5 text-gray-500" />
          </div>
          <p className="text-3xl font-bold font-mono mt-3 text-white">0</p>
          <p className="text-xs text-gray-500 mt-2">No documents ingested yet</p>
        </div>

        <div className="bg-gray-900/40 p-6 rounded-xl border border-gray-800 backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <span className="text-gray-400 text-sm font-medium">Pipeline Status</span>
            <Activity className="w-5 h-5 text-gray-500" />
          </div>
          <p className="text-3xl font-bold font-mono mt-3 text-teal-400">Idle</p>
          <p className="text-xs text-gray-500 mt-2">Awaiting ingestion requests</p>
        </div>
      </div>

      {/* Chart and Feed Section with honest empty states */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Extraction Volume */}
        <div className="lg:col-span-2 bg-gray-900/40 p-6 rounded-xl border border-gray-800 backdrop-blur-sm flex flex-col">
          <h2 className="text-lg font-semibold text-white mb-4">Extraction Volume over Time</h2>
          <div className="flex-1 min-h-[260px] flex flex-col items-center justify-center border border-dashed border-gray-800 rounded-lg p-8 text-center">
            <Activity className="w-10 h-10 text-gray-600 mb-3" />
            <p className="text-sm font-medium text-gray-300">No extraction volume recorded yet</p>
            <p className="text-xs text-gray-500 mt-1 max-w-sm">
              Extraction volume metrics will display here once documents are processed through the extraction pipeline.
            </p>
            <Link
              href="/dashboard/explorer"
              className="mt-4 px-4 py-2 text-xs font-medium rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors"
            >
              Go to Graph Explorer
            </Link>
          </div>
        </div>

        {/* Activity Feed */}
        <div className="bg-gray-900/40 p-6 rounded-xl border border-gray-800 backdrop-blur-sm flex flex-col">
          <h2 className="text-lg font-semibold text-white mb-4">Recent Activity</h2>
          <div className="flex-1 min-h-[260px] flex flex-col items-center justify-center border border-dashed border-gray-800 rounded-lg p-6 text-center">
            <FileText className="w-10 h-10 text-gray-600 mb-3" />
            <p className="text-sm font-medium text-gray-300">No recent activity</p>
            <p className="text-xs text-gray-500 mt-1 max-w-xs">
              Document uploads, chunking runs, and entity resolutions will appear in this feed.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
