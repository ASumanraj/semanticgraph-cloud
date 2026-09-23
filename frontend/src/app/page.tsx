import React from 'react';
import Link from 'next/link';

export default function Home() {
  return (
    <div className="min-h-screen bg-gray-950 text-white selection:bg-cyan-500/30">
      {/* Background gradients */}
      <div className="fixed inset-0 z-0 flex justify-center items-center pointer-events-none">
        <div className="absolute top-0 w-full h-[500px] bg-gradient-to-b from-blue-900/20 to-transparent"></div>
        <div className="w-[800px] h-[600px] bg-cyan-600/10 rounded-full blur-[120px]"></div>
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-6 pt-32 pb-24">
        {/* Hero Section */}
        <section className="flex flex-col items-center text-center mb-32">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 backdrop-blur-md mb-8">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
            <span className="text-sm font-medium text-gray-300">SemanticGraph Cloud substrate is active</span>
          </div>
          
          <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight mb-8">
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 via-blue-500 to-purple-600 drop-shadow-[0_0_15px_rgba(34,211,238,0.4)]">
              Enterprise AI Data
            </span>
            <br />
            Resolved &amp; Verified.
          </h1>
          
          <p className="text-lg md:text-xl text-gray-400 max-w-2xl mb-12 leading-relaxed">
            Ontology-constrained extraction and non-destructive resolution into Golden Records with mandatory provenance spans.
          </p>
          
          <div className="flex flex-col sm:flex-row gap-4">
            <Link
              href="/dashboard"
              className="px-8 py-4 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-gray-950 font-bold transition-all shadow-[0_0_20px_rgba(6,182,212,0.5)]"
            >
              Open Console
            </Link>
            <Link
              href="/dashboard/explorer"
              className="px-8 py-4 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 backdrop-blur-md font-semibold transition-all"
            >
              Graph Explorer
            </Link>
          </div>
        </section>

        {/* Feature Bento Grid */}
        <section>
          <h2 className="text-3xl font-bold text-center mb-16">
            The substrate for <span className="text-cyan-400">Knowledge-Graph Extraction</span>
          </h2>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Feature 1 */}
            <div className="md:col-span-2 p-8 rounded-2xl bg-white/[0.03] border border-white/10 backdrop-blur-xl hover:bg-white/[0.05] transition-colors relative overflow-hidden group">
              <div className="absolute top-0 right-0 w-64 h-64 bg-cyan-500/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/3 group-hover:bg-cyan-500/20 transition-all"></div>
              <h3 className="text-2xl font-bold mb-4 text-gray-100">Ontology-Constrained Extraction</h3>
              <p className="text-gray-400 leading-relaxed max-w-md">
                Build deep modules that map complex documents into strictly typed entities and relationships, enforced against versioned domain ontologies.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="p-8 rounded-2xl bg-white/[0.03] border border-white/10 backdrop-blur-xl hover:bg-white/[0.05] transition-colors">
              <h3 className="text-2xl font-bold mb-4 text-gray-100">Asynchronous Pipeline</h3>
              <p className="text-gray-400 leading-relaxed">
                Offload heavy computation. Process semantic chunks, entity extraction, and disambiguation seamlessly with retry-safe, idempotent steps.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="md:col-span-3 p-8 rounded-2xl bg-gradient-to-br from-white/[0.05] to-transparent border border-white/10 backdrop-blur-xl relative overflow-hidden">
              <div className="absolute bottom-0 left-1/2 w-full h-32 bg-purple-600/20 blur-3xl -translate-x-1/2 translate-y-1/2"></div>
              <div className="relative z-10 flex flex-col items-center text-center">
                <h3 className="text-2xl font-bold mb-4 text-gray-100">Grounded Extraction &amp; Provenance</h3>
                <p className="text-gray-400 leading-relaxed max-w-3xl mb-8">
                  Never guess on truth. Every fact in your knowledge graph is bound to its exact source chunk ID and character span, enabling deterministic deletion and citation.
                </p>
                <div className="w-full max-w-4xl h-32 rounded-xl bg-gray-950/50 border border-white/5 flex items-center justify-center font-mono text-sm text-cyan-400">
                  <span className="opacity-70">{"{"}</span>
                  <span className="mx-2">&quot;status&quot;: &quot;ready&quot;, &quot;resolution&quot;: &quot;golden_records&quot;, &quot;provenance&quot;: &quot;enforced&quot;</span>
                  <span className="opacity-70">{"}"}</span>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
