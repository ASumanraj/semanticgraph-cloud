"use client";

import React, { useState, useRef } from "react";
import { UploadCloud, File as FileIcon, X, CheckCircle2, AlertCircle } from "lucide-react";

export function DocumentUpload() {
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadComplete, setUploadComplete] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const getBase64 = (fileToEncode: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const result = reader.result as string;
        const base64 = result.includes(",") ? result.split(",")[1] : result;
        resolve(base64);
      };
      reader.onerror = (err) => reject(err);
      reader.readAsDataURL(fileToEncode);
    });
  };

  const uploadDocument = async () => {
    if (!file) return;
    setIsUploading(true);
    setUploadComplete(false);
    setErrorMessage(null);

    try {
      const base64Content = await getBase64(file);
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "";
      const url = apiBase ? `${apiBase}/api/v1/documents/ingest` : "/api/v1/documents/ingest";
      const tenantId = process.env.NEXT_PUBLIC_TENANT_ID || "00000000-0000-0000-0000-000000000001";

      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Tenant-ID": tenantId,
        },
        body: JSON.stringify({
          filename: file.name,
          content: base64Content,
          ontology_name: "default",
          allowed_entity_types: ["Organization", "Person", "Product"],
          allowed_edge_types: ["RELATED_TO", "WORKS_AT", "ACQUIRED"],
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const message = errorData?.detail?.error?.message || errorData?.error?.message || "Document ingestion failed";
        throw new Error(message);
      }
      
      setUploadComplete(true);
      setTimeout(() => {
        setFile(null);
        setUploadComplete(false);
      }, 3000);
    } catch (error) {
      console.error("Document ingestion error:", error);
      setErrorMessage(error instanceof Error ? error.message : "Document ingestion failed");
    } finally {
      setIsUploading(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setFile(e.dataTransfer.files[0]);
      setErrorMessage(null);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setErrorMessage(null);
    }
  };

  return (
    <div className="w-full h-full flex flex-col relative z-10">
      <h2 className="text-2xl font-bold mb-6 text-white tracking-tight">Upload Document</h2>
      
      {!file ? (
        <div
          className={`flex-1 flex flex-col items-center justify-center border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all duration-300 backdrop-blur-md ${
            isDragging 
              ? "border-blue-400 bg-blue-500/10 shadow-[0_0_30px_rgba(59,130,246,0.3)]" 
              : "border-white/20 bg-white/5 hover:border-white/40 hover:bg-white/10"
          }`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <div className={`p-4 rounded-full mb-4 transition-colors duration-300 ${isDragging ? 'bg-blue-500/20 text-blue-400' : 'bg-white/5 text-zinc-400'}`}>
            <UploadCloud className="w-10 h-10" />
          </div>
          <p className="text-zinc-200 font-medium text-lg mb-2">Click or drag document here</p>
          <p className="text-sm text-zinc-500">Supports PDF, DOCX, TXT</p>
          <input
            type="file"
            className="hidden"
            ref={fileInputRef}
            onChange={handleFileChange}
          />
        </div>
      ) : (
        <div className="flex flex-col space-y-6 flex-1 justify-center">
          <div className="flex items-center justify-between p-5 bg-white/5 backdrop-blur-md rounded-2xl border border-white/10">
            <div className="flex items-center space-x-4">
              <div className="p-3 bg-blue-500/20 rounded-xl">
                <FileIcon className="w-8 h-8 text-blue-400" />
              </div>
              <div>
                <p className="font-medium text-white line-clamp-1">{file.name}</p>
                <p className="text-sm text-zinc-400">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
              </div>
            </div>
            {!isUploading && !uploadComplete && (
              <button
                onClick={() => {
                  setFile(null);
                  setErrorMessage(null);
                }}
                className="p-2 text-zinc-400 hover:text-red-400 transition-colors rounded-full hover:bg-white/10"
                disabled={isUploading}
                aria-label="Remove selected file"
              >
                <X className="w-5 h-5" />
              </button>
            )}
            {uploadComplete && (
              <CheckCircle2 className="w-6 h-6 text-emerald-400" />
            )}
          </div>

          {errorMessage && (
            <div className="flex items-center gap-2 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm">
              <AlertCircle className="w-5 h-5 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}
          
          <button
            onClick={uploadDocument}
            disabled={isUploading || uploadComplete}
            className={`w-full py-4 px-6 rounded-xl font-medium text-white shadow-lg transition-all duration-300 ${
              uploadComplete 
                ? "bg-emerald-500/80 hover:bg-emerald-500/80 cursor-default" 
                : isUploading
                  ? "bg-blue-600/50 cursor-not-allowed"
                  : "bg-blue-600 hover:bg-blue-500 hover:shadow-[0_0_20px_rgba(37,99,235,0.4)] hover:-translate-y-0.5"
            }`}
          >
            {uploadComplete ? "Upload Complete!" : isUploading ? "Processing..." : "Extract Knowledge"}
          </button>
        </div>
      )}
    </div>
  );
}
