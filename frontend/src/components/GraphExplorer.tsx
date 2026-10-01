"use client";

import React, {
  useState,
  useEffect,
  useCallback,
  useMemo,
  useRef,
} from "react";
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
import {
  Network,
  FileText,
  Quote,
  Layers,
  Search,
  UploadCloud,
  AlertCircle,
  Filter,
  X,
} from "lucide-react";
import {
  AnimatePresence,
  motion,
  useReducedMotion,
  type Variants,
} from "framer-motion";
import "reactflow/dist/style.css";

/* ------------------------------------------------------------------ */
/*  Domain types — only fields the API actually returns               */
/* ------------------------------------------------------------------ */

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

/* ------------------------------------------------------------------ */
/*  Stable references — outside the component tree                    */
/* ------------------------------------------------------------------ */

// Stable references: defined outside the component so React Flow does not
// see a new object on every render.
const nodeTypes = {};
const edgeTypes = {};

// React 19 dev mode double-invokes useMemo for purity checks. In
// @reactflow/core's useNodeOrEdgeTypes the second pass compares two empty
// arrays via shallow(), finds them "equal" and fires onError("002") —
// a false positive. FlowInit patches onError directly (no setState in
// render) to suppress it.
function FlowInit() {
  const store = useStoreApi();
  store.getState().onError = (id: string, message: string) => {
    if (id === "002") return;
    console.warn(`[React Flow]: ${message}`);
  };
  return null;
}

/* ------------------------------------------------------------------ */
/*  Component                                                         */
/* ------------------------------------------------------------------ */

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

  // Hover state
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);

  // Entity-type filter chips (client-side)
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set());

  // Track node IDs that appeared in the last expansion or upload so they
  // get a short "new" accent.
  const [newNodeIds, setNewNodeIds] = useState<Set<string>>(new Set());
  const newAccentTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const previousNodeIdsRef = useRef<Set<string>>(new Set());

  // Double-click expansion
  const [expandingNodeId, setExpandingNodeId] = useState<string | null>(null);
  const [expandError, setExpandError] = useState<string | null>(null);

  // Request management
  const abortControllerRef = useRef<AbortController | null>(null);
  const requestIdRef = useRef(0);

  // Keyboard ref
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Reduced motion support
  const shouldReduceMotion = useReducedMotion();

  const panelVariants: Variants = useMemo(
    () => ({
      hidden: { x: shouldReduceMotion ? 0 : 20, opacity: 0 },
      visible: {
        x: 0,
        opacity: 1,
        transition: {
          duration: shouldReduceMotion ? 0 : 0.2,
          ease: "easeOut",
        },
      },
      exit: {
        x: shouldReduceMotion ? 0 : 20,
        opacity: 0,
        transition: {
          duration: shouldReduceMotion ? 0 : 0.15,
          ease: "easeIn",
        },
      },
    }),
    [shouldReduceMotion],
  );

  /* ---------------------------------------------------------------- */
  /*  Fetch graph                                                     */
  /* ---------------------------------------------------------------- */

  const fetchGraph = useCallback(
    async (query: string, depthVal: number) => {
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
        const tenantId =
          process.env.NEXT_PUBLIC_TENANT_ID ||
          "00000000-0000-0000-0000-000000000001";
        const response = await fetch(url, {
          signal: controller.signal,
          headers: { "X-Tenant-ID": tenantId },
        });

        if (!response.ok) {
          throw new Error(`HTTP error ${response.status}`);
        }

        const data = await response.json();

        // Guard against out-of-order responses overwriting newer ones
        if (currentRequestId !== requestIdRef.current) return;

        const rawNodes: ApiNode[] = data.nodes || [];
        const rawEdges: ApiEdge[] = data.edges || [];
        setIsTruncated(Boolean(data.truncated));

        // Detect "new" nodes (appeared since last fetch / upload)
        const incomingIds = new Set(rawNodes.map((n) => n.id));
        const appeared = new Set<string>();
        if (previousNodeIdsRef.current.size > 0) {
          for (const id of incomingIds) {
            if (!previousNodeIdsRef.current.has(id)) {
              appeared.add(id);
            }
          }
        }
        previousNodeIdsRef.current = incomingIds;

        if (appeared.size > 0) {
          setNewNodeIds(appeared);
          if (newAccentTimerRef.current) clearTimeout(newAccentTimerRef.current);
          newAccentTimerRef.current = setTimeout(
            () => setNewNodeIds(new Set()),
            3500,
          );
        }

        const numNodes = rawNodes.length;
        const radius = Math.max(160, numNodes * 28);
        const centerX = 360;
        const centerY = 280;

        const styledNodes: Node[] = rawNodes.map((node, index) => {
          const angle =
            numNodes > 1 ? (2 * Math.PI * index) / numNodes : 0;
          const x =
            numNodes === 1
              ? 300
              : Math.round(centerX + radius * Math.cos(angle));
          const y =
            numNodes === 1
              ? 200
              : Math.round(centerY + radius * Math.sin(angle));

          return {
            id: node.id,
            position: { x, y },
            data: {
              label: (
                <div className="flex flex-col gap-1 text-left select-none">
                  <div className="flex items-center justify-between gap-1.5">
                    <span className="font-semibold text-text text-xs leading-tight">
                      {node.name}
                    </span>
                  </div>
                  <span className="text-[10px] text-teal uppercase tracking-wider font-mono">
                    {node.entity_type}
                  </span>
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
              boxShadow:
                "0 4px 12px color-mix(in srgb, var(--color-page) 80%, transparent)",
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
        if (error instanceof Error && error.name === "AbortError") return;
        if (currentRequestId === requestIdRef.current) {
          console.debug("Graph fetch error:", error);
          setHasError(true);
        }
      } finally {
        if (currentRequestId === requestIdRef.current) {
          setIsLoading(false);
        }
      }
    },
    [setNodes, setEdges],
  );

  // Debounced search / depth query
  useEffect(() => {
    const handler = setTimeout(() => {
      fetchGraph(searchQuery, depth);
    }, 250);
    return () => clearTimeout(handler);
  }, [searchQuery, depth, fetchGraph]);

  // Listen for upload completion events from DocumentUpload component
  useEffect(() => {
    const handleUploaded = () => {
      fetchGraph(searchQuery, depth);
    };
    window.addEventListener("document-uploaded", handleUploaded);
    return () =>
      window.removeEventListener("document-uploaded", handleUploaded);
  }, [fetchGraph, searchQuery, depth]);

  /* ---------------------------------------------------------------- */
  /*  Hover highlighting                                              */
  /* ---------------------------------------------------------------- */

  const neighbourIds = useMemo(() => {
    if (!hoveredNodeId) return new Set<string>();
    const ids = new Set<string>();
    ids.add(hoveredNodeId);
    for (const e of edges) {
      if (e.source === hoveredNodeId) ids.add(e.target);
      if (e.target === hoveredNodeId) ids.add(e.source);
    }
    return ids;
  }, [hoveredNodeId, edges]);

  // Apply filter, selection, hover, and "new" accent to nodes
  const displayNodes = useMemo(() => {
    let filtered = nodes;
    if (hiddenTypes.size > 0) {
      filtered = nodes.filter(
        (n) => !hiddenTypes.has(n.data?.entity_type || ""),
      );
    }

    return filtered.map((n) => {
      const isSelected = selectedNode?.id === n.id;
      const isNew = newNodeIds.has(n.id);

      if (hoveredNodeId) {
        const isHoveredOrNeighbour = neighbourIds.has(n.id);
        const isHoveredDirectly = hoveredNodeId === n.id;
        return {
          ...n,
          style: {
            ...n.style,
            opacity: isHoveredOrNeighbour ? 1 : 0.25,
            border: isHoveredDirectly
              ? "1.5px solid var(--color-cyan)"
              : isHoveredOrNeighbour
                ? "1.5px solid var(--color-teal)"
                : "1px solid var(--color-border)",
            boxShadow: isHoveredDirectly
              ? "0 0 16px color-mix(in srgb, var(--color-cyan) 40%, transparent)"
              : isHoveredOrNeighbour
                ? "0 0 12px color-mix(in srgb, var(--color-teal) 30%, transparent)"
                : undefined,
            transition: "opacity 0.15s ease, border-color 0.15s ease",
          },
        };
      }

      // Normal state with selection / new accent
      let border = "1px solid var(--color-border)";
      let boxShadow =
        "0 4px 12px color-mix(in srgb, var(--color-page) 80%, transparent)";

      if (isSelected) {
        border = "2px solid var(--color-teal)";
        boxShadow =
          "0 0 16px color-mix(in srgb, var(--color-teal) 40%, transparent)";
      } else if (isNew) {
        border = "1.5px solid var(--color-teal)";
        boxShadow =
          "0 0 14px color-mix(in srgb, var(--color-teal) 35%, transparent)";
      }

      return {
        ...n,
        style: {
          ...n.style,
          opacity: 1,
          border,
          boxShadow,
          transition: "opacity 0.15s ease, border-color 0.15s ease",
        },
      };
    });
  }, [nodes, hiddenTypes, hoveredNodeId, neighbourIds, selectedNode, newNodeIds]);

  // Apply hover and filter to edges
  const displayEdges = useMemo(() => {
    const visibleNodeIds = new Set(displayNodes.map((n) => n.id));
    const filtered = edges.filter(
      (e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target),
    );

    return filtered.map((e) => {
      const isSelected = selectedEdge?.id === e.id;

      if (hoveredNodeId) {
        const isConnected =
          e.source === hoveredNodeId || e.target === hoveredNodeId;
        return {
          ...e,
          style: {
            ...e.style,
            opacity: isConnected ? 1 : 0.15,
            strokeWidth: isConnected ? 2.5 : 1.5,
            stroke: isConnected
              ? "var(--color-cyan)"
              : "var(--color-border)",
            transition: "opacity 0.15s ease, stroke-width 0.15s ease",
          },
        };
      }

      return {
        ...e,
        style: {
          ...e.style,
          opacity: 1,
          strokeWidth: isSelected ? 2.5 : 1.5,
          stroke: "var(--color-cyan)",
          transition: "opacity 0.15s ease, stroke-width 0.15s ease",
        },
      };
    });
  }, [edges, displayNodes, hoveredNodeId, selectedEdge]);

  /* ---------------------------------------------------------------- */
  /*  Entity-type filter chips                                        */
  /* ---------------------------------------------------------------- */

  const typeCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const n of nodes) {
      const t = n.data?.entity_type || "Unknown";
      counts.set(t, (counts.get(t) || 0) + 1);
    }
    return counts;
  }, [nodes]);

  const toggleType = useCallback((entityType: string) => {
    setHiddenTypes((prev) => {
      const next = new Set(prev);
      if (next.has(entityType)) {
        next.delete(entityType);
      } else {
        next.add(entityType);
      }
      return next;
    });
  }, []);

  /* ---------------------------------------------------------------- */
  /*  Keyboard: / focuses search, arrows move between nodes, Esc clears */
  /* ---------------------------------------------------------------- */

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const isInput =
        target.tagName === "INPUT" || target.tagName === "TEXTAREA";

      if (e.key === "Escape") {
        setSelectedNode(null);
        setSelectedEdge(null);
        setHoveredNodeId(null);
        if (isInput && target === searchInputRef.current) {
          searchInputRef.current?.blur();
        }
        return;
      }

      if (e.key === "/" && !isInput) {
        e.preventDefault();
        searchInputRef.current?.focus();
        return;
      }

      // Arrow navigation between connected nodes
      if (
        (e.key === "ArrowUp" ||
          e.key === "ArrowDown" ||
          e.key === "ArrowLeft" ||
          e.key === "ArrowRight") &&
        !isInput
      ) {
        e.preventDefault();
        if (!selectedNode && displayNodes.length > 0) {
          setSelectedNode(displayNodes[0]);
          setSelectedEdge(null);
          return;
        }

        if (selectedNode) {
          const connectedIds: string[] = [];
          for (const edge of edges) {
            if (edge.source === selectedNode.id)
              connectedIds.push(edge.target);
            if (edge.target === selectedNode.id)
              connectedIds.push(edge.source);
          }

          if (connectedIds.length === 0) return;

          const direction =
            e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : -1;
          const currentIdx = connectedIds.indexOf(selectedNode.id);
          const nextIdx =
            (currentIdx + direction + connectedIds.length) %
            connectedIds.length;
          const nextId = connectedIds[nextIdx];
          const nextNode = nodes.find((n) => n.id === nextId);
          if (nextNode) {
            setSelectedNode(nextNode);
            setSelectedEdge(null);
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedNode, edges, nodes, displayNodes]);

  /* ---------------------------------------------------------------- */
  /*  Interaction handlers                                            */
  /* ---------------------------------------------------------------- */

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

  const onNodeMouseEnter = useCallback((_: React.MouseEvent, node: Node) => {
    setHoveredNodeId(node.id);
  }, []);

  const onNodeMouseLeave = useCallback(() => {
    setHoveredNodeId(null);
  }, []);

  /* ---------------------------------------------------------------- */
  /*  Double-click expand: loads neighbourhood via query route        */
  /*  NOTE: expansion by name is approximate — the route matches      */
  /*  names with ILIKE, so every same-name entity becomes a seed.     */
  /* ---------------------------------------------------------------- */

  const onNodeDoubleClick = useCallback(
    async (_: React.MouseEvent, node: Node) => {
      const name = node.data?.name;
      if (!name) return;

      setExpandingNodeId(node.id);
      setExpandError(null);

      try {
        const apiBase = process.env.NEXT_PUBLIC_API_URL || "";
        const params = new URLSearchParams({ query: name, depth: "1" });
        const url = `${apiBase ? apiBase : ""}/api/v1/graph?${params.toString()}`;
        const tenantId =
          process.env.NEXT_PUBLIC_TENANT_ID ||
          "00000000-0000-0000-0000-000000000001";
        const response = await fetch(url, {
          headers: { "X-Tenant-ID": tenantId },
        });

        if (!response.ok) {
          throw new Error(`HTTP error ${response.status}`);
        }

        const data = await response.json();
        const expandedNodes: ApiNode[] = data.nodes || [];
        const expandedEdges: ApiEdge[] = data.edges || [];

        const existingIds = new Set(nodes.map((n) => n.id));
        const brandNewNodes: Node[] = [];
        const brandNewIds = new Set<string>();

        expandedNodes.forEach((en, i) => {
          if (existingIds.has(en.id)) return;
          brandNewIds.add(en.id);
          const angle =
            (2 * Math.PI * i) / Math.max(expandedNodes.length, 1);
          brandNewNodes.push({
            id: en.id,
            position: {
              x: (node.position?.x || 300) + 130 * Math.cos(angle),
              y: (node.position?.y || 200) + 130 * Math.sin(angle),
            },
            data: {
              label: (
                <div className="flex flex-col gap-1 text-left select-none">
                  <div className="flex items-center justify-between gap-1.5">
                    <span className="font-semibold text-text text-xs leading-tight">
                      {en.name}
                    </span>
                  </div>
                  <span className="text-[10px] text-teal uppercase tracking-wider font-mono">
                    {en.entity_type}
                  </span>
                </div>
              ),
              name: en.name,
              entity_type: en.entity_type,
              kind: en.kind,
              provenance: en.provenance,
            },
            style: {
              background: "var(--color-panel)",
              border: "1.5px solid var(--color-teal)",
              color: "var(--color-text)",
              borderRadius: "8px",
              padding: "10px 14px",
              boxShadow:
                "0 0 14px color-mix(in srgb, var(--color-teal) 35%, transparent)",
              cursor: "pointer",
            },
          });
        });

        const existingEdgeIds = new Set(edges.map((e) => e.id));
        const brandNewEdges: Edge[] = expandedEdges
          .filter((ee) => !existingEdgeIds.has(ee.id))
          .map((ee) => ({
            id: ee.id,
            source: ee.source,
            target: ee.target,
            label: ee.edge_type,
            data: {
              edge_type: ee.edge_type,
              weight: ee.weight,
              valid_from: ee.valid_from,
              valid_to: ee.valid_to,
              provenance: ee.provenance,
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

        if (brandNewNodes.length > 0) {
          setNodes((prev) => [...prev, ...brandNewNodes]);
          setEdges((prev) => [...prev, ...brandNewEdges]);

          setNewNodeIds(brandNewIds);
          if (newAccentTimerRef.current)
            clearTimeout(newAccentTimerRef.current);
          newAccentTimerRef.current = setTimeout(
            () => setNewNodeIds(new Set()),
            3500,
          );

          for (const id of brandNewIds) {
            previousNodeIdsRef.current.add(id);
          }
        }
      } catch (error) {
        console.debug("Expand error:", error);
        setExpandError(
          error instanceof Error ? error.message : "Expansion failed",
        );
        setTimeout(() => setExpandError(null), 4000);
      } finally {
        setExpandingNodeId(null);
      }
    },
    [nodes, edges, setNodes, setEdges],
  );

  /* ---------------------------------------------------------------- */
  /*  Helpers                                                         */
  /* ---------------------------------------------------------------- */

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

  const sameNameCount = useMemo(() => {
    if (!selectedNode) return 0;
    const currentName = (selectedNode.data?.name || "").trim().toLowerCase();
    if (!currentName) return 0;
    return nodes.filter(
      (n) =>
        n.id !== selectedNode.id &&
        (n.data?.name || "").trim().toLowerCase() === currentName,
    ).length;
  }, [selectedNode, nodes]);

  const nodeProvenance = selectedNode?.data?.provenance as
    | ApiProvenance
    | undefined;
  const edgeProvenance = selectedEdge?.data?.provenance as
    | ApiProvenance
    | undefined;

  const hasSelection = Boolean(selectedNode || selectedEdge);

  /* ---------------------------------------------------------------- */
  /*  Render                                                          */
  /* ---------------------------------------------------------------- */

  return (
    <div
      className="flex flex-col lg:flex-row w-full lg:h-[760px] border border-border rounded-lg overflow-hidden bg-page shadow-2xl relative"
      data-testid="graph-explorer"
    >
      {/* ---- Left Sidebar (288px) ---- */}
      <div className="w-full lg:w-[288px] shrink-0 border-b lg:border-b-0 lg:border-r border-border bg-panel p-5 flex flex-col gap-5 text-muted z-10">
        <div>
          <h3 className="text-base font-bold text-text tracking-tight">
            Graph Controls
          </h3>
          <p className="text-[11px] text-muted uppercase tracking-wider mt-0.5">
            Subgraph Inspection
          </p>
        </div>

        {/* Search */}
        <div className="space-y-1.5">
          <label
            htmlFor="graph-search"
            className="text-xs font-medium text-text flex items-center justify-between"
          >
            <span>Search Entities</span>
            <kbd className="text-[10px] font-mono text-muted bg-page px-1.5 py-0.5 rounded border border-border">
              /
            </kbd>
          </label>
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input
              id="graph-search"
              ref={searchInputRef}
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
            <span className="text-xs font-medium text-text">
              Depth (Hops)
            </span>
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

        {/* Entity-type filter chips */}
        {typeCounts.size > 0 && (
          <div className="space-y-1.5" data-testid="type-filters">
            <div className="flex items-center gap-1.5 text-xs font-medium text-text">
              <Filter className="w-3 h-3 text-teal" />
              <span>Entity Types</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {Array.from(typeCounts.entries()).map(([type, count]) => {
                const active = !hiddenTypes.has(type);
                return (
                  <button
                    key={type}
                    type="button"
                    onClick={() => toggleType(type)}
                    data-testid={`type-chip-${type}`}
                    className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-mono uppercase tracking-wider border transition-colors ${
                      active
                        ? "bg-teal/10 border-teal/40 text-teal"
                        : "bg-page/50 border-border text-muted/60 line-through"
                    }`}
                  >
                    <span>{type}</span>
                    <span className="font-semibold px-1 rounded bg-panel text-text">
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Graph Metrics */}
        <div className="bg-page/60 p-3.5 rounded-lg border border-border space-y-2 text-xs mt-auto">
          <div className="text-[11px] font-semibold text-text uppercase tracking-wider">
            {isTruncated
              ? "Showing 200 entities"
              : `${displayNodes.length} nodes active · ${displayEdges.length} edges`}
          </div>
          <div className="flex justify-between items-center py-1 border-b border-border/50 text-muted">
            <span>Entities</span>
            <span className="font-mono text-teal font-medium">
              {displayNodes.length}
            </span>
          </div>
          <div className="flex justify-between items-center py-1 text-muted">
            <span>Relationships</span>
            <span className="font-mono text-cyan font-medium">
              {displayEdges.length}
            </span>
          </div>
        </div>
      </div>

      {/* ---- Main Canvas ---- */}
      <div className="flex-1 relative bg-page flex flex-col min-w-0 w-full h-[520px] lg:h-full">
        {/* Loading Indicator */}
        {isLoading && (
          <div className="absolute top-4 right-4 z-20 px-3 py-1 bg-panel/90 border border-border rounded-lg text-xs text-muted flex items-center gap-1.5 shadow">
            <span className="w-1.5 h-1.5 rounded-full bg-teal" />
            <span>Loading...</span>
          </div>
        )}

        {/* Expand loading overlay badge */}
        {expandingNodeId && (
          <div
            data-testid="expanding-indicator"
            className="absolute top-4 left-1/2 -translate-x-1/2 z-20 px-3.5 py-1.5 bg-panel/95 border border-teal/40 rounded-lg text-xs text-teal shadow-xl flex items-center gap-2 backdrop-blur"
          >
            <span className="w-2 h-2 rounded-full bg-teal shrink-0" />
            <span>
              Expanding neighbourhood... (same-name query matches all mentions)
            </span>
          </div>
        )}

        {/* Expand error banner */}
        {expandError && (
          <div
            data-testid="expand-error"
            className="absolute top-4 left-1/2 -translate-x-1/2 z-20 px-3.5 py-1.5 bg-panel/95 border border-error/40 rounded-lg text-xs text-error shadow-xl flex items-center gap-2 backdrop-blur"
          >
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>Expand failed: {expandError}</span>
          </div>
        )}

        {/* Truncated Notice Banner */}
        {isTruncated && !hasError && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20 px-4 py-2 bg-panel/90 border border-teal/40 rounded-lg text-xs text-text shadow-xl flex items-center gap-2 backdrop-blur pointer-events-none">
            <span className="w-2 h-2 rounded-full bg-teal shrink-0" />
            <span>
              Showing the first 200 entities. Narrow your search to see
              more.
            </span>
          </div>
        )}

        {/* Error State Overlay */}
        {hasError && (
          <div className="absolute inset-0 z-30 bg-page/85 backdrop-blur-sm flex flex-col items-center justify-center p-6 text-center">
            <div className="w-10 h-10 rounded-full bg-error/10 border border-error/30 flex items-center justify-center mb-3 text-error">
              <AlertCircle className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-semibold text-text mb-1">
              Couldn&apos;t load the graph
            </h3>
            <p className="text-xs text-muted max-w-sm mb-4 leading-relaxed">
              An error occurred while communicating with the
              knowledge-graph API.
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
            <h3 className="text-base font-semibold text-text mb-2">
              No graph yet
            </h3>
            <p className="text-xs text-muted max-w-md leading-relaxed mb-6">
              No graph yet. Upload a contract. Entities and relationships
              extracted from it appear here, each linked to its source
              text.
            </p>
            <button
              type="button"
              onClick={() => {
                const uploadEl = document.getElementById(
                  "document-upload-dropzone",
                );
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
          /* Empty State: Query matches nothing */
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-page min-h-[500px]">
            <div className="w-12 h-12 rounded-full bg-panel border border-border flex items-center justify-center mb-4 text-muted">
              <Search className="w-6 h-6" />
            </div>
            <h3 className="text-base font-semibold text-text mb-2">
              No entities match &ldquo;{searchQuery.trim()}&rdquo;
            </h3>
            <p className="text-xs text-muted max-w-md leading-relaxed mb-6">
              Try searching for a different keyword or broaden your search
              criteria.
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
          <div className="w-full h-[520px] lg:h-full relative bg-page">
            <ReactFlowProvider>
              <FlowInit />
              <ReactFlow
                style={{ width: "100%", height: "100%" }}
                nodes={displayNodes}
                edges={displayEdges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClick}
                onEdgeClick={onEdgeClick}
                onPaneClick={onPaneClick}
                onNodeMouseEnter={onNodeMouseEnter}
                onNodeMouseLeave={onNodeMouseLeave}
                onNodeDoubleClick={onNodeDoubleClick}
                nodeTypes={nodeTypes}
                edgeTypes={edgeTypes}
                fitView
              >
                <Background
                  color="var(--color-border)"
                  variant={BackgroundVariant.Dots}
                  gap={20}
                  size={1.5}
                />
                <Controls className="bg-panel border border-border shadow-lg fill-muted text-muted rounded-lg overflow-hidden" />
              </ReactFlow>
            </ReactFlowProvider>
          </div>
        )}
      </div>

      {/* ---- Right Properties Panel (320px, slides in with framer-motion) ---- */}
      <AnimatePresence mode="wait">
        {hasSelection ? (
          <motion.div
            key={
              selectedNode
                ? `node-${selectedNode.id}`
                : `edge-${selectedEdge?.id}`
            }
            variants={panelVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            className="w-full lg:w-[320px] shrink-0 border-t lg:border-t-0 lg:border-l border-border bg-panel p-6 flex flex-col text-text z-10 overflow-y-auto"
          >
            <div>
              <div className="flex items-center justify-between">
                <h3 className="text-base font-bold text-text">
                  Properties
                </h3>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedNode(null);
                    setSelectedEdge(null);
                  }}
                  className="p-1 rounded hover:bg-page text-muted hover:text-text transition-colors"
                  aria-label="Close panel"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <p className="text-[11px] text-muted uppercase tracking-wider mt-0.5">
                {selectedNode
                  ? "Node & Evidence Metadata"
                  : "Edge & Evidence Metadata"}
              </p>
            </div>

            <div className="mt-5 flex-1">
              {selectedNode ? (
                <div className="space-y-4">
                  {/* Node Fields Card */}
                  <div className="bg-page/50 p-4 rounded-lg border border-border space-y-3">
                    <div className="flex flex-col gap-0.5">
                      <span className="text-[11px] text-muted uppercase tracking-wider font-medium">
                        Name
                      </span>
                      <span className="text-sm font-semibold text-text break-words">
                        {selectedNode.data?.name ||
                          selectedNode.data?.label ||
                          "Unknown"}
                      </span>
                      <span className="text-[11px] text-muted">
                        {sameNameCount} other{" "}
                        {sameNameCount === 1
                          ? "entity in this view shares"
                          : "entities in this view share"}{" "}
                        this name
                      </span>
                    </div>

                    <div className="flex flex-col gap-0.5">
                      <span className="text-[11px] text-muted uppercase tracking-wider font-medium">
                        Type
                      </span>
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
                            <FileText className="w-3 h-3 text-teal" />{" "}
                            Chunk ID
                          </span>
                          <span className="font-mono text-text break-all text-[11px] block bg-page p-2 rounded border border-border">
                            {nodeProvenance.chunk_id}
                          </span>
                        </div>

                        <div className="flex justify-between items-center bg-page/60 p-2 rounded border border-border/50">
                          <span className="text-muted font-medium">
                            Characters
                          </span>
                          <span className="font-mono text-teal font-medium">
                            {nodeProvenance.start_offset}–
                            {nodeProvenance.end_offset}
                          </span>
                        </div>

                        <div>
                          <span className="text-muted block mb-1 font-medium">
                            Source quote
                          </span>
                          <blockquote className="italic border-l-2 border-teal pl-3 py-1.5 bg-page/80 rounded-r text-text text-xs leading-relaxed break-words font-serif">
                            &ldquo;{nodeProvenance.quote}&rdquo;
                          </blockquote>
                        </div>
                      </div>
                    ) : (
                      <p className="text-xs text-muted italic">
                        No provenance span recorded for this entity.
                      </p>
                    )}
                  </div>
                </div>
              ) : selectedEdge ? (
                <div className="space-y-4">
                  {/* Edge Fields Card */}
                  <div className="bg-page/50 p-4 rounded-lg border border-border space-y-3">
                    <div className="flex flex-col gap-0.5">
                      <span className="text-[11px] text-muted uppercase tracking-wider font-medium">
                        Edge Type
                      </span>
                      <span className="text-sm font-semibold text-cyan break-words">
                        {selectedEdge.data?.edge_type ||
                          selectedEdge.label ||
                          "Unknown"}
                      </span>
                    </div>

                    <div className="flex flex-col gap-0.5">
                      <span className="text-[11px] text-muted uppercase tracking-wider font-medium">
                        Weight
                      </span>
                      <span className="text-xs font-mono text-text">
                        {selectedEdge.data?.weight !== undefined &&
                        selectedEdge.data?.weight !== null
                          ? selectedEdge.data.weight
                          : "not recorded"}
                      </span>
                    </div>

                    <div className="flex flex-col gap-0.5">
                      <span className="text-[11px] text-muted uppercase tracking-wider font-medium">
                        Valid From
                      </span>
                      <span className="text-xs font-mono text-muted">
                        {formatValidTimestamp(
                          selectedEdge.data?.valid_from,
                        )}
                      </span>
                    </div>

                    <div className="flex flex-col gap-0.5">
                      <span className="text-[11px] text-muted uppercase tracking-wider font-medium">
                        Valid To
                      </span>
                      <span className="text-xs font-mono text-muted">
                        {formatValidTimestamp(
                          selectedEdge.data?.valid_to,
                        )}
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
                            <FileText className="w-3 h-3 text-teal" />{" "}
                            Chunk ID
                          </span>
                          <span className="font-mono text-text break-all text-[11px] block bg-page p-2 rounded border border-border">
                            {edgeProvenance.chunk_id}
                          </span>
                        </div>

                        <div className="flex justify-between items-center bg-page/60 p-2 rounded border border-border/50">
                          <span className="text-muted font-medium">
                            Characters
                          </span>
                          <span className="font-mono text-teal font-medium">
                            {edgeProvenance.start_offset}–
                            {edgeProvenance.end_offset}
                          </span>
                        </div>

                        <div>
                          <span className="text-muted block mb-1 font-medium">
                            Source quote
                          </span>
                          <blockquote className="italic border-l-2 border-teal pl-3 py-1.5 bg-page/80 rounded-r text-text text-xs leading-relaxed break-words font-serif">
                            &ldquo;{edgeProvenance.quote}&rdquo;
                          </blockquote>
                        </div>
                      </div>
                    ) : (
                      <p className="text-xs text-muted italic">
                        No provenance span recorded for this
                        relationship.
                      </p>
                    )}
                  </div>
                </div>
              ) : null}
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="empty-panel"
            variants={panelVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            className="w-full lg:w-[320px] shrink-0 border-t lg:border-t-0 lg:border-l border-border bg-panel p-6 flex flex-col text-text z-10 overflow-y-auto"
          >
            <div>
              <h3 className="text-base font-bold text-text">Properties</h3>
              <p className="text-[11px] text-muted uppercase tracking-wider mt-0.5">
                Selection Details
              </p>
            </div>
            <div className="mt-5 flex-1 flex flex-col items-center justify-center h-64 text-center text-muted space-y-3 my-auto">
              <Network className="h-10 w-10 text-muted opacity-40" />
              <p className="text-xs leading-relaxed max-w-[200px]">
                Select a node or edge in the graph to view its properties
                and source provenance.
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
