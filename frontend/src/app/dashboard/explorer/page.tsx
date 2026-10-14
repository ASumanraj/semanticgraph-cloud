import { GraphExplorer } from "@/components/GraphExplorer";
import { DocumentUpload } from "@/components/DocumentUpload";

export default function ExplorerPage() {
  return (
    <div className="h-full flex flex-col p-3 sm:p-4 gap-3 bg-page text-text overflow-y-auto lg:overflow-hidden">
      {/* Compact Top Bar: Title & Summary + Inline Slim Upload */}
      <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3 bg-panel px-4 py-2.5 rounded-lg border border-border shrink-0 shadow-sm">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="text-sm sm:text-base font-bold text-text tracking-tight whitespace-nowrap">
              Semantic Graph Explorer
            </h1>
          </div>
          <p className="text-muted text-[11px] hidden sm:block truncate mt-0.5">
            Explore connected subgraphs and inspect character-level provenance spans from source text.
          </p>
        </div>

        <div className="w-full lg:w-auto lg:min-w-[420px] xl:min-w-[480px] shrink-0">
          <DocumentUpload />
        </div>
      </div>

      {/* Main Graph Canvas Area */}
      <div className="flex-1 min-h-[520px] lg:min-h-0 relative">
        <GraphExplorer />
      </div>
    </div>
  );
}
