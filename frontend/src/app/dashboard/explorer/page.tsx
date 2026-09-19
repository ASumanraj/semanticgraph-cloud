import { GraphExplorer } from "@/components/GraphExplorer";
import { AuthGuard } from "@/components/AuthGuard";
import { DocumentUpload } from "@/components/DocumentUpload";

export default function ExplorerPage() {
  return (
    <AuthGuard allowedRoles={["Super Admin", "Tenant Admin"]}>
      <main className="min-h-screen bg-[#050810] text-gray-100 p-8">
        <div className="max-w-7xl mx-auto space-y-10">
          <div className="bg-gray-900/40 p-8 rounded-2xl border border-gray-800 shadow-xl backdrop-blur-sm">
            <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-teal-400 via-blue-500 to-purple-500">
              Semantic Graph Explorer
            </h1>
            <p className="text-gray-400 mt-3 text-lg">
              Visualize relationships, explore connected data, and manage documents with premium analytics.
            </p>
          </div>
          
          <div className="bg-gray-900/60 border border-gray-800 rounded-2xl p-6 shadow-lg backdrop-blur-sm">
            <DocumentUpload />
          </div>
          
          <div className="pt-2">
            <div className="flex items-center gap-4 mb-8">
              <div className="h-[1px] bg-gradient-to-r from-transparent to-gray-700 flex-1"></div>
              <h2 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-teal-300 to-purple-400 uppercase tracking-widest text-sm">
                Knowledge Graph Visualization
              </h2>
              <div className="h-[1px] bg-gradient-to-l from-transparent to-gray-700 flex-1"></div>
            </div>
            
            <div className="ring-1 ring-white/10 rounded-xl overflow-hidden shadow-2xl">
              <GraphExplorer />
            </div>
          </div>
        </div>
      </main>
    </AuthGuard>
  );
}
