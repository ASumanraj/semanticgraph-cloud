"use client";

import React, { useState, useEffect, useCallback } from "react";
import ReactFlow, { Background, Controls, Node, Edge, BackgroundVariant, useNodesState, useEdgesState } from "reactflow";
import { Network, FileText, Quote, Layers } from "lucide-react";
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

export function GraphExplorer() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);

  useEffect(() => {
    const fetchGraph = async () => {
      try {
        const apiBase = process.env.NEXT_PUBLIC_API_URL || "";
        const url = apiBase ? `${apiBase}/api/v1/graph` : "/api/v1/graph";
        const tenantId = process.env.NEXT_PUBLIC_TENANT_ID || "00000000-0000-0000-0000-000000000001";
        const response = await fetch(url, {
          headers: {
            "X-Tenant-ID": tenantId,
          },
        });
        if (response.ok) {
          const data = await response.json();
          const rawNodes: ApiNode[] = data.nodes || [];
          const rawEdges: ApiEdge[] = data.edges || [];

          const numNodes = rawNodes.length;
          const radius = Math.max(160, numNodes * 28);
          const centerX = 350;
          const centerY = 250;

          const styledNodes: Node[] = rawNodes.map((node, index) => {
            const angle = numNodes > 1 ? (2 * Math.PI * index) / numNodes : 0;
            const x = numNodes === 1 ? 300 : Math.round(centerX + radius * Math.cos(angle));
            const y = numNodes === 1 ? 200 : Math.round(centerY + radius * Math.sin(angle));

            return {
              id: node.id,
              position: { x, y },
              data: {
                label: node.name,
                name: node.name,
                entity_type: node.entity_type,
                kind: node.kind,
                provenance: node.provenance,
              },
              style: {
                background: "rgba(10, 15, 30, 0.85)",
                backdropFilter: "blur(12px)",
                border: "1px solid rgba(0, 255, 255, 0.6)",
                boxShadow: "0 0 20px rgba(0, 255, 255, 0.25)",
                color: "#f8fafc",
                borderRadius: "8px",
                padding: "12px",
                fontWeight: 600,
                fontSize: "13px",
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
              provenance: edge.provenance,
            },
            animated: true,
            style: {
              stroke: "#00ffff",
              strokeWidth: 2,
              filter: "drop-shadow(0 0 8px rgba(0, 255, 255, 0.8))",
            },
            labelStyle: {
              fill: "#a5f3fc",
              fontWeight: 500,
              fontSize: "11px",
            },
            labelBgStyle: {
              fill: "#050810",
              fillOpacity: 0.85,
            },
          }));

          setNodes(styledNodes);
          setEdges(styledEdges);
        }
      } catch (error) {
        console.debug("No graph data retrieved from API endpoint", error);
      }
    };
    fetchGraph();
  }, [setNodes, setEdges]);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  const provenance = selectedNode?.data?.provenance as ApiProvenance | undefined;

  return (
    <div className="flex flex-col md:flex-row h-[700px] w-full border border-gray-800 rounded-xl overflow-hidden bg-gray-950 shadow-2xl">
      {/* Left Sidebar - Controls */}
      <div className="w-full md:w-72 bg-[#050810] border-b md:border-b-0 md:border-r border-gray-800 p-6 flex flex-col gap-6 text-gray-200 z-10 shadow-lg shrink-0">
        <div>
          <h3 className="text-xl font-bold text-teal-400 mb-1">Graph Controls</h3>
          <p className="text-xs text-gray-500 uppercase tracking-wider">Subgraph Inspection</p>
        </div>
        <div className="space-y-5">
          <div className="bg-gray-800/40 p-4 rounded-xl border border-gray-700/50 backdrop-blur">
            <h4 className="text-sm font-semibold mb-3 text-gray-300">Filters</h4>
            <div className="space-y-3">
              <label className="flex items-center gap-3 text-sm text-gray-400 hover:text-gray-200 transition-colors cursor-pointer">
                <input type="checkbox" className="accent-teal-500 w-4 h-4" defaultChecked /> Show Entities
              </label>
              <label className="flex items-center gap-3 text-sm text-gray-400 hover:text-gray-200 transition-colors cursor-pointer">
                <input type="checkbox" className="accent-teal-500 w-4 h-4" defaultChecked /> Show Relationships
              </label>
            </div>
          </div>
          <div className="bg-gray-800/40 p-4 rounded-xl border border-gray-700/50 backdrop-blur">
            <h4 className="text-sm font-semibold mb-3 text-gray-300">Graph Metrics</h4>
            <div className="flex justify-between text-sm py-1 border-b border-gray-700/50">
              <span className="text-gray-400">Total Nodes</span>
              <span className="text-teal-300 font-mono">{nodes.length}</span>
            </div>
            <div className="flex justify-between text-sm py-1 pt-2">
              <span className="text-gray-400">Total Edges</span>
              <span className="text-purple-400 font-mono">{edges.length}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Canvas or Truthful Empty State */}
      <div className="flex-1 relative bg-[#02040a] flex flex-col">
        {nodes.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-[#02040a]">
            <Network className="w-16 h-16 text-gray-600 mb-4 opacity-50" />
            <h3 className="text-lg font-semibold text-gray-200 mb-2">No graph data available</h3>
            <p className="text-sm text-gray-400 max-w-md leading-relaxed">
              Ingest documents above to construct subgraphs and explore extracted knowledge.
            </p>
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            fitView
          >
            <Background color="#1f2937" variant={BackgroundVariant.Dots} gap={20} size={1.5} />
            <Controls className="bg-gray-800 border-gray-700 shadow-lg fill-gray-300" />
          </ReactFlow>
        )}
      </div>

      {/* Right Sidebar - Properties Panel with Provenance Evidence */}
      <div className="w-full md:w-80 bg-[#050810] border-t md:border-t-0 md:border-l border-gray-800 p-6 flex flex-col text-gray-200 z-10 shadow-lg shrink-0 overflow-y-auto">
        <div>
          <h3 className="text-xl font-bold text-purple-400 mb-1">Properties</h3>
          <p className="text-xs text-gray-500 uppercase tracking-wider">Node &amp; Evidence Metadata</p>
        </div>

        <div className="mt-6 flex-1">
          {selectedNode ? (
            <div className="space-y-4 animate-in fade-in duration-300">
              <div className="bg-gray-800/40 p-4 rounded-xl border border-gray-700/50 backdrop-blur space-y-4">
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-gray-400 uppercase tracking-wider">ID</span>
                  <span className="text-xs font-mono text-gray-200 break-all">{selectedNode.id}</span>
                </div>

                <div className="flex flex-col gap-1">
                  <span className="text-xs text-gray-400 uppercase tracking-wider">Label</span>
                  <span className="text-sm font-semibold text-teal-300">
                    {selectedNode.data?.name || selectedNode.data?.label || "Unknown"}
                  </span>
                </div>

                <div className="flex flex-col gap-1">
                  <span className="text-xs text-gray-400 uppercase tracking-wider">Entity Type</span>
                  <span className="text-sm text-purple-300 font-medium">
                    {selectedNode.data?.entity_type || selectedNode.type || "Unknown"}
                  </span>
                </div>

                {selectedNode.data?.kind && (
                  <div className="flex flex-col gap-1">
                    <span className="text-xs text-gray-400 uppercase tracking-wider flex items-center gap-1">
                      <Layers className="w-3 h-3 text-gray-400" /> Kind
                    </span>
                    <span className="text-xs text-zinc-300 font-mono">
                      {selectedNode.data.kind}
                    </span>
                  </div>
                )}
              </div>

              {/* Provenance Evidence Panel */}
              <div className="bg-teal-950/20 p-4 rounded-xl border border-teal-800/40 backdrop-blur space-y-3">
                <div className="flex items-center gap-2 border-b border-teal-800/40 pb-2">
                  <Quote className="w-4 h-4 text-teal-400" />
                  <h4 className="text-xs font-bold text-teal-300 uppercase tracking-wider">
                    Grounded Provenance
                  </h4>
                </div>

                {provenance ? (
                  <div className="space-y-3 text-xs">
                    <div>
                      <span className="text-gray-400 block mb-1 flex items-center gap-1">
                        <FileText className="w-3 h-3 text-teal-400" /> Chunk ID
                      </span>
                      <span className="font-mono text-zinc-300 break-all text-[11px] block bg-black/40 p-1.5 rounded border border-gray-800">
                        {provenance.chunk_id}
                      </span>
                    </div>

                    <div className="flex justify-between items-center bg-black/30 p-2 rounded">
                      <span className="text-gray-400">Span Offsets</span>
                      <span className="font-mono text-teal-300 font-medium">
                        [{provenance.start_offset}, {provenance.end_offset}]
                      </span>
                    </div>

                    <div>
                      <span className="text-gray-400 block mb-1">Exact Quote</span>
                      <blockquote className="italic border-l-2 border-teal-500 pl-2.5 py-1.5 bg-black/50 rounded-r text-teal-200 text-xs leading-relaxed break-words font-serif">
                        &ldquo;{provenance.quote}&rdquo;
                      </blockquote>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-gray-500 italic">No provenance span recorded for this node.</p>
                )}
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center text-gray-500 space-y-3 opacity-60">
              <Network className="h-10 w-10 text-gray-600" />
              <p className="text-sm">Select a node in the graph to view its properties and evidence provenance.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
