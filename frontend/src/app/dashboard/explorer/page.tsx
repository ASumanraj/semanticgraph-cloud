import { GraphExplorer } from "@/components/GraphExplorer";
import { DocumentUpload } from "@/components/DocumentUpload";

export default function ExplorerPage() {
  return (
    <main className="min-h-screen bg-page text-text p-3 sm:p-6 md:p-8">
      <div className="max-w-7xl mx-auto space-y-6 sm:space-y-8">
        <header className="bg-panel p-4 sm:p-6 md:p-8 rounded-lg border border-border">
          <h1 className="text-xl sm:text-2xl md:text-3xl font-bold text-text tracking-tight">
            Semantic Graph Explorer
          </h1>
          <p className="text-muted mt-2 text-xs sm:text-sm md:text-base max-w-2xl">
            Extract ontology-constrained entities and relationships, explore connected subgraphs, and verify character-level source provenance.
          </p>
        </header>
        
        <section className="bg-panel border border-border rounded-lg p-4 sm:p-6">
          <DocumentUpload />
        </section>
        
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
              Graph Visualization
            </h2>
          </div>
          
          <div className="border border-border rounded-lg overflow-hidden bg-page">
            <GraphExplorer />
          </div>
        </section>
      </div>
    </main>
  );
}
