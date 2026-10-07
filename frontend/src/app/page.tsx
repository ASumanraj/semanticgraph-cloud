import React from 'react';
import Link from 'next/link';

export default function Home() {
  return (
    <div className="min-h-screen bg-page text-text selection:bg-teal/30">
      {/* Background gradients */}
      <div className="fixed inset-0 z-0 flex justify-center items-center pointer-events-none">
        <div className="absolute top-0 w-full h-[500px] bg-gradient-to-b from-teal/10 to-transparent"></div>
        <div className="w-[800px] h-[600px] bg-cyan/10 rounded-full blur-[120px]"></div>
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-6 pt-32 pb-24">
        {/* Hero Section */}
        <section className="flex flex-col items-center text-center mb-32">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-panel border border-border backdrop-blur-md mb-8">
            <span className="w-2 h-2 rounded-full bg-cyan"></span>
            <span className="text-sm font-medium text-muted">SemanticGraph Cloud substrate is active</span>
          </div>
          
          <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight mb-8">
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-cyan via-teal to-purple">
              Enterprise AI Data
            </span>
            <br />
            Resolved &amp; Verified.
          </h1>
          
          <p className="text-lg md:text-xl text-muted max-w-2xl mb-12 leading-relaxed">
            Ontology-constrained extraction and non-destructive resolution into Golden Records with mandatory provenance spans.
          </p>
          
          <div className="flex flex-col sm:flex-row gap-4">
            <Link
              href="/dashboard"
              className="px-8 py-4 rounded-lg bg-teal hover:bg-teal/80 text-page font-bold transition-all shadow-lg"
            >
              Open Console
            </Link>
            <Link
              href="/dashboard/explorer"
              className="px-8 py-4 rounded-lg bg-panel hover:bg-panel/80 border border-border backdrop-blur-md font-semibold text-text transition-all"
            >
              Graph Explorer
            </Link>
          </div>
        </section>

        {/* Feature Bento Grid */}
        <section>
          <h2 className="text-3xl font-bold text-center mb-16">
            The substrate for <span className="text-cyan">Knowledge-Graph Extraction</span>
          </h2>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Feature 1 */}
            <div className="md:col-span-2 p-8 rounded-lg bg-panel border border-border backdrop-blur-xl relative overflow-hidden group">
              <div className="absolute top-0 right-0 w-64 h-64 bg-cyan/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/3 group-hover:bg-cyan/20 transition-all"></div>
              <h3 className="text-2xl font-bold mb-4 text-text">Ontology-Constrained Extraction</h3>
              <p className="text-muted leading-relaxed max-w-md">
                Build deep modules that map complex documents into strictly typed entities and relationships, enforced against versioned domain ontologies.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="p-8 rounded-lg bg-panel border border-border backdrop-blur-xl">
              <h3 className="text-2xl font-bold mb-4 text-text">Asynchronous Pipeline</h3>
              <p className="text-muted leading-relaxed">
                Offload heavy computation. Process semantic chunks, entity extraction, and disambiguation seamlessly with retry-safe, idempotent steps.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="md:col-span-3 p-8 rounded-lg bg-panel border border-border backdrop-blur-xl relative overflow-hidden">
              <div className="absolute bottom-0 left-1/2 w-full h-32 bg-purple/20 blur-3xl -translate-x-1/2 translate-y-1/2"></div>
              <div className="relative z-10 flex flex-col items-center text-center">
                <h3 className="text-2xl font-bold mb-4 text-text">Grounded Extraction &amp; Provenance</h3>
                <p className="text-muted leading-relaxed max-w-3xl mb-8">
                  Never guess on truth. Every fact in your knowledge graph is bound to its exact source chunk ID and character span, enabling deterministic deletion and citation.
                </p>
                <div className="w-full max-w-4xl h-32 rounded-lg bg-page border border-border flex items-center justify-center font-mono text-sm text-cyan">
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
