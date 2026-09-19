"use client";

import React, { useState, useEffect, useCallback } from "react";
import ReactFlow, { Background, Controls, Node, Edge, BackgroundVariant, useNodesState, useEdgesState } from "reactflow";
import "reactflow/dist/style.css";

export function GraphExplorer() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  
  useEffect(() => {
    const fetchGraph = async () => {
      try {
        const response = await fetch("http://localhost:8000/graph", {
          headers: {
            "tenant_id": "tenant-123"
          }
        });
        if (response.ok) {
          const data = await response.json();
          // Apply premium dark/glassmorphic styling to nodes
          const styledNodes = (data.nodes || []).map((node: Node) => ({
            ...node,
            style: {
              ...node.style,
              background: 'rgba(10, 15, 30, 0.85)',
              backdropFilter: 'blur(12px)',
              border: '1px solid rgba(0, 255, 255, 0.6)',
              boxShadow: '0 0 20px rgba(0, 255, 255, 0.25)',
              color: '#f8fafc',
              borderRadius: '8px',
              padding: '12px',
            }
          }));
          
          // Apply neon styling to edges
          const styledEdges = (data.edges || []).map((edge: Edge) => ({
            ...edge,
            animated: true,
            style: {
              ...edge.style,
              stroke: '#00ffff',
              strokeWidth: 2,
              filter: 'drop-shadow(0 0 8px rgba(0, 255, 255, 0.8))'
            }
          }));

          setNodes(styledNodes);
          setEdges(styledEdges);
        }
      } catch (error) {
        console.error("Failed to fetch graph", error);
      }
    };
    fetchGraph();
  }, [setNodes, setEdges]);

  const onNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    setSelectedNode(node);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  return (
    <div className="flex flex-col md:flex-row h-[700px] w-full border border-gray-800 rounded-xl overflow-hidden bg-gray-950 shadow-2xl">
      {/* Left Sidebar - Controls */}
      <div className="w-full md:w-72 bg-[#050810] border-b md:border-b-0 md:border-r border-gray-800 p-6 flex flex-col gap-6 text-gray-200 z-10 shadow-lg shrink-0">
        <div>
          <h3 className="text-xl font-bold text-teal-400 mb-1">Graph Controls</h3>
          <p className="text-xs text-gray-500 uppercase tracking-wider">Premium Dashboard</p>
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

      {/* Main Canvas */}
      <div className="flex-1 relative bg-[#02040a]">
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
      </div>

      {/* Right Sidebar - Properties Panel */}
      <div className="w-full md:w-80 bg-[#050810] border-t md:border-t-0 md:border-l border-gray-800 p-6 flex flex-col text-gray-200 z-10 shadow-lg shrink-0 overflow-y-auto">
        <div>
          <h3 className="text-xl font-bold text-purple-400 mb-1">Properties</h3>
          <p className="text-xs text-gray-500 uppercase tracking-wider">Node Metadata</p>
        </div>
        
        <div className="mt-6 flex-1">
          {selectedNode ? (
            <div className="space-y-4 animate-in fade-in duration-300">
              <div className="bg-gray-800/40 p-4 rounded-xl border border-gray-700/50 backdrop-blur">
                <div className="flex flex-col gap-1 mb-4">
                  <span className="text-xs text-gray-400 uppercase tracking-wider">ID</span>
                  <span className="text-sm font-mono text-gray-200">{selectedNode.id}</span>
                </div>
                
                <div className="flex flex-col gap-1 mb-4">
                  <span className="text-xs text-gray-400 uppercase tracking-wider">Label</span>
                  <span className="text-sm font-medium text-teal-300">{selectedNode.data?.label || 'Unknown'}</span>
                </div>
                
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-gray-400 uppercase tracking-wider">Type</span>
                  <span className="text-sm text-purple-300 capitalize">{selectedNode.type || 'default'}</span>
                </div>
              </div>

              <div className="bg-gray-800/40 p-4 rounded-xl border border-gray-700/50 backdrop-blur">
                <h4 className="text-sm font-semibold mb-3 text-gray-300">Mock Metadata</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between border-b border-gray-700/50 pb-1">
                    <span className="text-gray-400">Confidence</span>
                    <span className="text-green-400">98.5%</span>
                  </div>
                  <div className="flex justify-between border-b border-gray-700/50 pb-1">
                    <span className="text-gray-400">Source</span>
                    <span className="text-blue-400">Document_A.pdf</span>
                  </div>
                  <div className="flex justify-between pb-1">
                    <span className="text-gray-400">Extracted</span>
                    <span className="text-gray-200">2 mins ago</span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center text-gray-500 space-y-3 opacity-60">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
              </svg>
              <p className="text-sm">Select a node in the graph to view its properties and metadata.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
