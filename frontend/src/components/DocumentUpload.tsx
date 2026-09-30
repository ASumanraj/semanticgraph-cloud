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
    <div className="w-full flex flex-col">
      <div className="mb-4">
        <h2 className="text-xl md:text-2xl font-semibold text-text tracking-tight">Upload Document</h2>
        <p className="text-xs md:text-sm text-muted mt-1">
          Upload a contract or document to extract entities and relationships linked to exact source text.
        </p>
      </div>
      
      {!file ? (
        <div
          id="document-upload-dropzone"
          role="button"
          tabIndex={0}
          aria-label="Upload document dropzone"
          className={`flex flex-col items-center justify-center border border-dashed rounded-lg p-8 md:p-12 text-center cursor-pointer transition-all duration-200 focus-visible:ring-2 focus-visible:ring-teal focus-visible:outline-none ${
            isDragging 
              ? "border-teal bg-teal/5 shadow-[0_0_20px_rgba(45,212,191,0.15)]" 
              : "border-border bg-page hover:border-teal/50 hover:bg-panel/40"
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
          <div className="p-3.5 rounded-full mb-3 bg-panel text-teal border border-border inline-flex items-center justify-center">
            <UploadCloud className="w-7 h-7" />
          </div>
          <p className="text-text font-medium text-base mb-1">Click or drag document here</p>
          <p className="text-xs text-muted">Supports PDF, DOCX, TXT</p>
          <input
            type="file"
            className="hidden"
            ref={fileInputRef}
            onChange={handleFileChange}
          />
        </div>
      ) : (
        <div className="flex flex-col space-y-4">
          <div className="flex items-center justify-between p-4 bg-page rounded-lg border border-border">
            <div className="flex items-center space-x-3 min-w-0">
              <div className="p-2.5 bg-panel text-cyan rounded-lg border border-border shrink-0">
                <FileIcon className="w-6 h-6" />
              </div>
              <div className="min-w-0">
                <p className="font-medium text-text text-sm truncate">{file.name}</p>
                <p className="text-xs text-muted">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
              </div>
            </div>
            {!isUploading && !uploadComplete && (
              <button
                type="button"
                onClick={() => {
                  setFile(null);
                  setErrorMessage(null);
                }}
                className="p-2 text-muted hover:text-error hover:bg-panel rounded-lg transition-colors focus-visible:ring-2 focus-visible:ring-teal focus-visible:outline-none"
                disabled={isUploading}
                aria-label="Remove selected file"
              >
                <X className="w-5 h-5" />
              </button>
            )}
            {uploadComplete && (
              <CheckCircle2 className="w-5 h-5 text-teal shrink-0" />
            )}
          </div>

          {errorMessage && (
            <div className="flex items-center gap-2 p-3 bg-error/10 border border-error/30 rounded-lg text-error text-xs">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}
          
          <button
            type="button"
            onClick={uploadDocument}
            disabled={isUploading || uploadComplete}
            className={`w-full py-3.5 px-6 rounded-lg font-semibold text-page transition-all focus-visible:ring-2 focus-visible:ring-teal focus-visible:outline-none ${
              uploadComplete 
                ? "bg-teal cursor-default flex items-center justify-center gap-2" 
                : isUploading
                  ? "bg-teal/50 text-page/70 cursor-not-allowed"
                  : "bg-teal hover:opacity-95 active:scale-[0.99] shadow-[0_0_15px_rgba(45,212,191,0.2)]"
            }`}
          >
            {uploadComplete ? "Upload Complete!" : isUploading ? "Processing..." : "Extract Knowledge"}
          </button>
        </div>
      )}
    </div>
  );
}
