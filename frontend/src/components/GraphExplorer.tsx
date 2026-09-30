"use client";

import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import ReactFlow, {
  Background,
  Controls,
  Node,
  Edge,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  ReactFlowProvider,
  useStoreApi,
} from "reactflow";
import { Network, FileText, Quote, Layers, Search, UploadCloud, AlertCircle } from "lucide-react";
import "reactflow/dist/style.css";

interface ApiProvenance {
  chunk_id: string;
  start_offset: number;
  end_offset: number;
  quote: string;
}

interface ApiNode {
  id: string;
  name: string;
  entity_type: string;
  kind: string;
  provenance?: ApiProvenance | null;
}

interface ApiEdge {
  id: string;
  source: string;
  target: string;
  edge_type: string;
  weight?: number;
  valid_from?: string | null;
  valid_to?: string | null;
  provenance?: ApiProvenance | null;
}

// Defined outside the component to eliminate the React Flow console warning
const nodeTypes = {};
const edgeTypes = {};

function FlowInit() {
  const store = useStoreApi();
  store.getState().onError = (id: string, message: string) => {
    if (id === "002") return;
    console.warn(`[React Flow]: ${message}`);
  };
  return null;
}

export function GraphExplorer() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<Edge | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [depth, setDepth] = useState(2);
  const [isTruncated, setIsTruncated] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);

  const abortControllerRef = useRef<AbortController | null>(null);
  const requestIdRef = useRef(0);

  const fetchGraph = useCallback(async (query: string, depthVal: number) => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;
    const currentRequestId = ++requestIdRef.current;

    setIsLoading(true);
    setHasError(false);

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "";
      const params = new URLSearchParams();
      if (query.trim()) {
        params.set("query", query.trim());
      }
      params.set("depth", String(depthVal));
      const url = `${apiBase ? apiBase : ""}/api/v1/graph?${params.toString()}`;
      const tenantId = process.env.NEXT_PUBLIC_TENANT_ID || "00000000-0000-0000-0000-000000000001";
      const response = await fetch(url, {
        signal: controller.signal,
        headers: {
          "X-Tenant-ID": tenantId,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
      }

      const data = await response.json();

      // Guard against out-of-order responses overwriting newer ones
      if (currentRequestId !== requestIdRef.current) {
        return;
      }

      const rawNodes: ApiNode[] = data.nodes || [];
      const rawEdges: ApiEdge[] = data.edges || [];
      setIsTruncated(Boolean(data.truncated));

      const numNodes = rawNodes.length;
      const radius = Math.max(160, numNodes * 28);
      const centerX = 360;
      const centerY = 280;

      const styledNodes: Node[] = rawNodes.map((node, index) => {
        const angle = numNodes > 1 ? (2 * Math.PI * index) / numNodes : 0;
        const x = numNodes === 1 ? 300 : Math.round(centerX + radius * Math.cos(angle));
        const y = numNodes === 1 ? 200 : Math.round(centerY + radius * Math.sin(angle));

        return {
          id: node.id,
          position: { x, y },
          data: {
            label: (
              <div className="flex flex-col gap-1 text-left select-none">
                <span className="font-semibold text-text text-xs leading-tight">{node.name}</span>
                <span className="text-[10px] text-teal uppercase tracking-wider font-mono">{node.entity_type}</span>
              </div>
            ),
            name: node.name,
            entity_type: node.entity_type,
            kind: node.kind,
            provenance: node.provenance,
          },
          style: {
            background: "var(--color-panel)",
            border: "1px solid var(--color-border)",
            color: "var(--color-text)",
            borderRadius: "8px",
            padding: "10px 14px",
            boxShadow: "0 4px 12px rgba(0, 0, 0, 0.4)",
            cursor: "pointer",
          },
        };
      });

      const styledEdges: Edge[] = rawEdges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.edge_type,
        data: {
          edge_type: edge.edge_type,
          weight: edge.weight,
          valid_from: edge.valid_from,
          valid_to: edge.valid_to,
          provenance: edge.provenance,
        },
        animated: false,
        style: {
          stroke: "var(--color-cyan)",
          strokeWidth: 1.5,
          cursor: "pointer",
        },
        labelStyle: {
          fill: "var(--color-cyan)",
          fontWeight: 500,
          fontSize: 11,
          fontFamily: "Inter, sans-serif",
        },
        labelBgStyle: {
          fill: "var(--color-panel)",
          fillOpacity: 0.95,
        },
        labelBgPadding: [6, 4] as [number, number],
        labelBgBorderRadius: 4,
      }));

      setNodes(styledNodes);
      setEdges(styledEdges);
    } catch (error: unknown) {
      if (error instanceof Error && error.name === "AbortError") {
        return;
      }
      if (currentRequestId === requestIdRef.current) {
        console.debug("Graph fetch error:", error);
        setHasError(true);
        // Retain existing nodes and edges so previous graph stays visible behind error state
      }
    } finally {
      if (currentRequestId === requestIdRef.current) {
        setIsLoading(false);
      }
    }
  }, [setNodes, setEdges]);

  // Debounced search / depth query
  useEffect(() => {
    const handler = setTimeout(() => {
      fetchGraph(searchQuery, depth);
    }, 250);
    return () => clearTimeout(handler);
  }, [searchQuery, depth, fetchGraph]);

  // Keyboard navigation & escape to clear selection
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setSelectedNode(null);
        setSelectedEdge(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node);
    setSelectedEdge(null);
  }, []);

  const onEdgeClick = useCallback((_: React.MouseEvent, edge: Edge) => {
    setSelectedEdge(edge);
    setSelectedNode(null);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
    setSelectedEdge(null);
  }, []);

  // Format timestamps: show a null valid_to as "not recorded", never "present"
  const formatValidTimestamp = (val?: string | null): string => {
    if (!val) return "not recorded";
    try {
      const d = new Date(val);
      if (isNaN(d.getTime())) return "not recorded";
      return d.toISOString();
    } catch {
      return "not recorded";
    }
  };

  // Same-name count calculation: raw entities are per mention, never merge silently
  const sameNameCount = useMemo(() => {
    if (!selectedNode) return 0;
    const currentName = (selectedNode.data?.name || "").trim().toLowerCase();
    if (!currentName) return 0;
    return nodes.filter(
      (n) => n.id !== selectedNode.id && (n.data?.name || "").trim().toLowerCase() === currentName
    ).length;
  }, [selectedNode, nodes]);

  const nodeProvenance = selectedNode?.data?.provenance as ApiProvenance | undefined;
  const edgeProvenance = selectedEdge?.data?.provenance as ApiProvenance | undefined;

  return (
    <div className="flex flex-col md:flex-row h-[760px] w-full border border-border rounded-lg overflow-hidden bg-page shadow-2xl relative">
      {/* 288px Left Sidebar - Controls */}
      <div className="w-full md:w-[288px] shrink-0 border-b md:border-b-0 md:border-r border-border bg-panel p-5 flex flex-col gap-5 text-muted z-10">
        <div>
          <h3 className="text-base font-bold text-text tracking-tight">Graph Controls</h3>
          <p className="text-[11px] text-muted uppercase tracking-wider mt-0.5">Subgraph Inspection</p>
        </div>

        {/* Search */}
        <div className="space-y-1.5">
          <label htmlFor="graph-search" className="text-xs font-medium text-text">
            Search Entities
          </label>
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input
              id="graph-search"
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search entities..."
              className="w-full bg-page border border-border rounded-lg pl-9 pr-3 py-1.5 text-xs text-text placeholder:text-muted focus:border-teal focus:outline-none focus:ring-1 focus:ring-teal/30"
            />
          </div>
        </div>

        {/* Depth Selector */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-text">Depth (Hops)</span>
            <span className="text-xs text-muted font-mono">{depth}</span>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {[1, 2, 3].map((hop) => (
              <button
                key={hop}
                type="button"
                onClick={() => setDepth(hop)}
                className={`py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                  depth === hop
                    ? "bg-teal text-page font-semibold border-teal"
                    : "bg-page border-border text-muted hover:text-text hover:bg-page/80"
                }`}
              >
                Hop {hop}
              </button>
            ))}
          </div>
        </div>

        {/* Graph Metrics */}
        <div className="bg-page/60 p-3.5 rounded-lg border border-border space-y-2 text-xs">
          <div className="text-[11px] font-semibold text-text uppercase tracking-wider">
            {isTruncated ? "Showing 200 entities" : `${nodes.length} nodes active · ${edges.length} edges`}
          </div>
          <div className="flex justify-between items-center py-1 border-b border-border/50 text-muted">
            <span>Entities</span>
            <span className="font-mono text-teal font-medium">{nodes.length}</span>
          </div>
          <div className="flex justify-between items-center py-1 text-muted">
            <span>Relationships</span>
            <span className="font-mono text-cyan font-medium">{edges.length}</span>
          </div>
        </div>
      </div>

      {/* Main Canvas with Distinct Empty States, Error Overlay, and Loading State */}
      <div className="flex-1 relative bg-page flex flex-col min-w-0">
        {/* Loading Indicator */}
        {isLoading && (
          <div className="absolute top-4 right-4 z-20 px-3 py-1 bg-panel/90 border border-border rounded-lg text-xs text-muted flex items-center gap-1.5 shadow">
            <span className="w-1.5 h-1.5 rounded-full bg-teal" />
            <span>Loading...</span>
          </div>
        )}

        {/* Truncated Notice Banner */}
        {isTruncated && !hasError && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20 px-4 py-2 bg-panel/90 border border-teal/40 rounded-lg text-xs text-text shadow-xl flex items-center gap-2 backdrop-blur pointer-events-none">
            <span className="w-2 h-2 rounded-full bg-teal shrink-0" />
            <span>Showing the first 200 entities. Narrow your search to see more.</span>
          </div>
        )}

        {/* Error State Overlay: keeps previous graph visible behind it if nodes exist */}
        {hasError && (
          <div className="absolute inset-0 z-30 bg-page/85 backdrop-blur-sm flex flex-col items-center justify-center p-6 text-center">
            <div className="w-10 h-10 rounded-full bg-error/10 border border-error/30 flex items-center justify-center mb-3 text-error">
              <AlertCircle className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-semibold text-text mb-1">Couldn&apos;t load the graph</h3>
            <p className="text-xs text-muted max-w-sm mb-4 leading-relaxed">
              An error occurred while communicating with the knowledge-graph API.
            </p>
            <button
              type="button"
              onClick={() => fetchGraph(searchQuery, depth)}
              className="px-4 py-2 bg-panel hover:bg-page border border-border text-text text-xs font-semibold rounded-lg transition-colors shadow"
            >
              Retry
            </button>
          </div>
        )}

        {/* Empty State: No query and no data */}
        {nodes.length === 0 && !searchQuery.trim() && !hasError ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-page min-h-[500px]">
            <div className="w-12 h-12 rounded-full bg-panel border border-border flex items-center justify-center mb-4 text-muted">
              <Network className="w-6 h-6" />
            </div>
            <h3 className="text-base font-semibold text-text mb-2">No graph yet</h3>
            <p className="text-xs text-muted max-w-md leading-relaxed mb-6">
              No graph yet. Upload a contract. Entities and relationships extracted from it appear here, each linked to its source text.
            </p>
            <button
              type="button"
              onClick={() => {
                const uploadEl = document.getElementById("document-upload-dropzone");
                if (uploadEl) {
                  uploadEl.scrollIntoView({ behavior: "smooth" });
                  uploadEl.click();
                }
              }}
              className="px-4 py-2 bg-teal hover:bg-teal/80 text-page text-xs font-semibold rounded-lg transition-colors shadow flex items-center gap-1.5"
            >
              <UploadCloud className="w-4 h-4" />
              Upload Document
            </button>
          </div>
        ) : nodes.length === 0 && searchQuery.trim() && !hasError ? (
          /* Empty State: Query matches nothing - NEVER show "No graph yet" */
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-page min-h-[500px]">
            <div className="w-12 h-12 rounded-full bg-panel border border-border flex items-center justify-center mb-4 text-muted">
              <Search className="w-6 h-6" />
            </div>
            <h3 className="text-base font-semibold text-text mb-2">
              No entities match &ldquo;{searchQuery.trim()}&rdquo;
            </h3>
            <p className="text-xs text-muted max-w-md leading-relaxed mb-6">
              Try searching for a different keyword or broaden your search criteria.
            </p>
            <button
              type="button"
              onClick={() => setSearchQuery("")}
              className="px-4 py-2 bg-panel hover:bg-page border border-border text-text text-xs font-semibold rounded-lg transition-colors shadow"
            >
              Clear search
            </button>
          </div>
        ) : (
          /* Canvas rendering with ReactFlow */
          <div className="flex-1 relative bg-page flex flex-col h-full">
            <ReactFlowProvider>
              <FlowInit />
              <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClick}
                onEdgeClick={onEdgeClick}
                onPaneClick={onPaneClick}
                nodeTypes={nodeTypes}
                edgeTypes={edgeTypes}
                fitView
              >
                <Background color="var(--color-border)" variant={BackgroundVariant.Dots} gap={20} size={1.5} />
                <Controls className="bg-panel border border-border shadow-lg fill-muted text-muted rounded-lg overflow-hidden" />
              </ReactFlow>
            </ReactFlowProvider>
          </div>
        )}
      </div>

      {/* 320px Right Properties Panel */}
      <div className="w-full md:w-[320px] shrink-0 border-t md:border-t-0 md:border-l border-border bg-panel p-6 flex flex-col text-text z-10 overflow-y-auto">
        <div>
          <h3 className="text-base font-bold text-text">Properties</h3>
          <p className="text-[11px] text-muted uppercase tracking-wider mt-0.5">
            {selectedNode
              ? "Node & Evidence Metadata"
              : selectedEdge
                ? "Edge & Evidence Metadata"
                : "Selection Details"}
          </p>
        </div>

        <div className="mt-5 flex-1">
          {selectedNode ? (
            <div className="space-y-4">
              {/* Node Fields Card */}
              <div className="bg-page/50 p-4 rounded-lg border border-border space-y-3">
                <div className="flex flex-col gap-0.5">
                  <span className="text-[11px] text-muted uppercase tracking-wider font-medium">Name</span>
                  <span className="text-sm font-semibold text-text break-words">
                    {selectedNode.data?.name || selectedNode.data?.label || "Unknown"}
                  </span>
                  <span className="text-[11px] text-muted">
                    {sameNameCount} other {sameNameCount === 1 ? "entity in this view shares" : "entities in this view share"} this name
                  </span>
                </div>

                <div className="flex flex-col gap-0.5">
                  <span className="text-[11px] text-muted uppercase tracking-wider font-medium">Type</span>
                  <span className="text-xs font-mono text-teal">
                    {selectedNode.data?.entity_type || "Unknown"}
                  </span>
                </div>

                <div className="flex flex-col gap-0.5">
                  <span className="text-[11px] text-muted uppercase tracking-wider font-medium flex items-center gap-1">
                    <Layers className="w-3 h-3 text-muted" /> Kind
                  </span>
                  <span className="text-xs font-mono text-muted">
                    {selectedNode.data?.kind || "not recorded"}
                  </span>
                </div>
              </div>

              {/* Provenance Card */}
              <div className="bg-teal/5 p-4 rounded-lg border border-teal/30 space-y-3">
                <div className="flex items-center gap-2 border-b border-teal/20 pb-2">
                  <Quote className="w-3.5 h-3.5 text-teal" />
                  <h4 className="text-xs font-bold text-teal uppercase tracking-wider">
                    Grounded Provenance
                  </h4>
                </div>

                {nodeProvenance ? (
                  <div className="space-y-3 text-xs">
                    <div>
                      <span className="text-muted block mb-1 flex items-center gap-1 font-medium">
                        <FileText className="w-3 h-3 text-teal" /> Chunk ID
                      </span>
                      <span className="font-mono text-text break-all text-[11px] block bg-page p-2 rounded border border-border">
                        {nodeProvenance.chunk_id}
                      </span>
                    </div>

                    <div className="flex justify-between items-center bg-page/60 p-2 rounded border border-border/50">
                      <span className="text-muted font-medium">Characters</span>
                      <span className="font-mono text-teal font-medium">
                        {nodeProvenance.start_offset}–{nodeProvenance.end_offset}
                      </span>
                    </div>

                    <div>
                      <span className="text-muted block mb-1 font-medium">Source quote</span>
                      <blockquote className="italic border-l-2 border-teal pl-3 py-1.5 bg-page/80 rounded-r text-text text-xs leading-relaxed break-words font-serif">
                        &ldquo;{nodeProvenance.quote}&rdquo;
                      </blockquote>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-muted italic">No provenance span recorded for this entity.</p>
                )}
              </div>
            </div>
          ) : selectedEdge ? (
            <div className="space-y-4">
              {/* Edge Fields Card */}
              <div className="bg-page/50 p-4 rounded-lg border border-border space-y-3">
                <div className="flex flex-col gap-0.5">
                  <span className="text-[11px] text-muted uppercase tracking-wider font-medium">Edge Type</span>
                  <span className="text-sm font-semibold text-cyan break-words">
                    {selectedEdge.data?.edge_type || selectedEdge.label || "Unknown"}
                  </span>
                </div>

                <div className="flex flex-col gap-0.5">
                  <span className="text-[11px] text-muted uppercase tracking-wider font-medium">Weight</span>
                  <span className="text-xs font-mono text-text">
                    {selectedEdge.data?.weight !== undefined && selectedEdge.data?.weight !== null
                      ? selectedEdge.data.weight
                      : "not recorded"}
                  </span>
                </div>

                <div className="flex flex-col gap-0.5">
                  <span className="text-[11px] text-muted uppercase tracking-wider font-medium">Valid From</span>
                  <span className="text-xs font-mono text-muted">
                    {formatValidTimestamp(selectedEdge.data?.valid_from)}
                  </span>
                </div>

                <div className="flex flex-col gap-0.5">
                  <span className="text-[11px] text-muted uppercase tracking-wider font-medium">Valid To</span>
                  <span className="text-xs font-mono text-muted">
                    {formatValidTimestamp(selectedEdge.data?.valid_to)}
                  </span>
                </div>
              </div>

              {/* Edge Provenance Card */}
              <div className="bg-teal/5 p-4 rounded-lg border border-teal/30 space-y-3">
                <div className="flex items-center gap-2 border-b border-teal/20 pb-2">
                  <Quote className="w-3.5 h-3.5 text-teal" />
                  <h4 className="text-xs font-bold text-teal uppercase tracking-wider">
                    Grounded Provenance
                  </h4>
                </div>

                {edgeProvenance ? (
                  <div className="space-y-3 text-xs">
                    <div>
                      <span className="text-muted block mb-1 flex items-center gap-1 font-medium">
                        <FileText className="w-3 h-3 text-teal" /> Chunk ID
                      </span>
                      <span className="font-mono text-text break-all text-[11px] block bg-page p-2 rounded border border-border">
                        {edgeProvenance.chunk_id}
                      </span>
                    </div>

                    <div className="flex justify-between items-center bg-page/60 p-2 rounded border border-border/50">
                      <span className="text-muted font-medium">Characters</span>
                      <span className="font-mono text-teal font-medium">
                        {edgeProvenance.start_offset}–{edgeProvenance.end_offset}
                      </span>
                    </div>

                    <div>
                      <span className="text-muted block mb-1 font-medium">Source quote</span>
                      <blockquote className="italic border-l-2 border-teal pl-3 py-1.5 bg-page/80 rounded-r text-text text-xs leading-relaxed break-words font-serif">
                        &ldquo;{edgeProvenance.quote}&rdquo;
                      </blockquote>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-muted italic">No provenance span recorded for this relationship.</p>
                )}
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-64 text-center text-muted space-y-3 my-auto">
              <Network className="h-10 w-10 text-muted opacity-40" />
              <p className="text-xs leading-relaxed max-w-[200px]">
                Select a node or edge in the graph to view its properties and source provenance.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
