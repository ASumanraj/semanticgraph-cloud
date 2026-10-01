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
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("document-uploaded"));
      }
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
    <div className="w-full">
      {!file ? (
        <div
          id="document-upload-dropzone"
          role="button"
          tabIndex={0}
          aria-label="Upload document dropzone"
          className={`flex items-center justify-between gap-3 border rounded-lg px-3.5 py-2 cursor-pointer transition-all duration-200 focus-visible:ring-2 focus-visible:ring-teal focus-visible:outline-none ${
            isDragging 
              ? "border-teal bg-teal/10 shadow-[0_0_20px_var(--color-teal)]/15" 
              : "border-border bg-page hover:border-teal/50 hover:bg-panel/60"
          }`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              fileInputRef.current?.click();
            }
          }}
        >
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="p-1.5 rounded bg-panel text-teal border border-border shrink-0">
              <UploadCloud className="w-4 h-4" />
            </div>
            <span className="text-text font-medium text-xs truncate">
              Click or drag document here
            </span>
            <span className="text-[11px] text-muted hidden md:inline">
              (Supports PDF, DOCX, TXT)
            </span>
          </div>
          <span className="px-2.5 py-1 bg-panel border border-border text-teal text-[11px] font-semibold rounded shrink-0 pointer-events-none">
            Choose File
          </span>
          <input
            type="file"
            className="hidden"
            ref={fileInputRef}
            onChange={handleFileChange}
          />
        </div>
      ) : (
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5 p-2 bg-page rounded-lg border border-border">
          <div className="flex items-center space-x-2.5 min-w-0 flex-1">
            <div className="p-1.5 bg-panel text-cyan rounded border border-border shrink-0">
              <FileIcon className="w-4 h-4" />
            </div>
            <div className="min-w-0 flex-1 flex items-baseline gap-2">
              <p className="font-medium text-text text-xs truncate">{file.name}</p>
              <p className="text-[10px] text-muted shrink-0">({(file.size / 1024 / 1024).toFixed(2)} MB)</p>
            </div>
            {!isUploading && !uploadComplete && (
              <button
                type="button"
                onClick={() => {
                  setFile(null);
                  setErrorMessage(null);
                }}
                className="p-1 text-muted hover:text-error hover:bg-panel rounded transition-colors"
                aria-label="Remove selected file"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {errorMessage && (
            <div className="flex items-center gap-1.5 text-error text-[11px] px-2 py-0.5 bg-error/10 border border-error/30 rounded">
              <AlertCircle className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">{errorMessage}</span>
            </div>
          )}

          <button
            type="button"
            onClick={uploadDocument}
            disabled={isUploading || uploadComplete}
            className={`py-1.5 px-4 rounded font-semibold text-xs text-page shrink-0 transition-all focus-visible:ring-2 focus-visible:ring-teal focus-visible:outline-none ${
              uploadComplete 
                ? "bg-teal cursor-default flex items-center gap-1.5" 
                : isUploading
                  ? "bg-teal/50 cursor-not-allowed"
                  : "bg-teal hover:opacity-95 active:scale-[0.99] shadow-[0_0_15px_var(--color-teal)]/20"
            }`}
          >
            {uploadComplete ? (
              <>
                <CheckCircle2 className="w-3.5 h-3.5 text-page" />
                <span>Upload Complete!</span>
              </>
            ) : isUploading ? (
              "Processing..."
            ) : (
              "Extract Knowledge"
            )}
          </button>
        </div>
      )}
    </div>
  );
}
