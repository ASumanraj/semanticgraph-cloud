"use client";

import React, { useEffect, useState } from "react";
import { AlertCircle, AlertTriangle, Cpu, Database } from "lucide-react";

interface ExtractorInfo {
  kind: "placeholder" | "model";
  model_id: string | null;
  terms: "evaluation-only" | string | null;
}

interface SystemStatus {
  profile: "inmemory" | "postgres";
  persistent: boolean;
  extractor: ExtractorInfo;
}

export function StatusBanner() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;
    const fetchStatus = async () => {
      try {
        const res = await fetch("/api/v1/system");
        if (!res.ok) {
          throw new Error(`Failed to fetch system status: ${res.status}`);
        }
        const data: SystemStatus = await res.json();
        if (isMounted) {
          setStatus(data);
          setError(false);
          setLoading(false);
        }
      } catch {
        if (isMounted) {
          setError(true);
          setStatus(null);
          setLoading(false);
        }
      }
    };

    fetchStatus();
    return () => {
      isMounted = false;
    };
  }, []);

  if (loading) {
    return null;
  }

  // If /system fails, show "status unavailable", never a green state.
  if (error || !status) {
    return (
      <div
        data-testid="status-banner"
        className="w-full bg-error/15 border-b border-error/30 text-error px-4 py-2 text-xs flex items-center justify-between gap-2 shrink-0"
      >
        <div className="flex items-center gap-2 font-medium">
          <AlertCircle className="w-4 h-4 shrink-0 text-error" />
          <span>Status unavailable</span>
        </div>
        <span className="text-[11px] text-muted">API system status could not be reached</span>
      </div>
    );
  }

  const isPlaceholder = status.extractor?.kind === "placeholder";
  const modelId = status.extractor?.model_id;
  const terms = status.extractor?.terms;

  if (isPlaceholder) {
    return (
      <div
        data-testid="status-banner"
        className="w-full bg-panel/95 border-b border-border/80 px-4 py-2 text-xs flex flex-wrap items-center justify-between gap-x-4 gap-y-1 shrink-0 backdrop-blur-md"
      >
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-purple/10 border border-purple/30 text-purple font-mono font-semibold uppercase text-[10px]">
            <Cpu className="w-3 h-3" />
            Placeholder extractor
          </span>
          <span className="text-text font-medium">
            Placeholder extractor: entity names are not extracted from your document.
          </span>
          <span className="text-muted hidden md:inline">
            The graph shows quoted source text.
          </span>
        </div>
        <div className="flex items-center gap-3 text-muted text-[11px]">
          <span className="inline-flex items-center gap-1">
            <Database className="w-3 h-3 text-teal" />
            Storage: {status.persistent ? "Postgres durable" : "In-Memory"}
          </span>
        </div>
      </div>
    );
  }

  // Model extractor active
  return (
    <div
      data-testid="status-banner"
      className="w-full bg-panel/95 border-b border-border/80 px-4 py-2 text-xs flex flex-wrap items-center justify-between gap-x-4 gap-y-1 shrink-0 backdrop-blur-md"
    >
      <div className="flex items-center gap-2">
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-teal/10 border border-teal/30 text-teal font-mono font-semibold uppercase text-[10px]">
          <Cpu className="w-3 h-3" />
          Model extractor
        </span>
        <span className="text-text font-medium">
          Model: <span className="font-mono text-cyan">{modelId || "model"}</span>
        </span>
        {terms && (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-purple/15 text-purple text-[10px] border border-purple/20">
            <AlertTriangle className="w-3 h-3" />
            Evaluation endpoint: {terms}
          </span>
        )}
      </div>
      <div className="flex items-center gap-3 text-muted text-[11px]">
        <span className="inline-flex items-center gap-1">
          <Database className="w-3 h-3 text-teal" />
          Storage: {status.persistent ? "Postgres durable" : "In-Memory"}
        </span>
      </div>
    </div>
  );
}
