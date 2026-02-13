'use client';

import { useState } from 'react';
import Link from 'next/link';

type UploadResult = {
  chunks_processed: number;
  embeddings_created: number;
  images_processed: number;
  message: string;
};

type SourceType = 'textbook' | 'exam_paper';

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [sourceType, setSourceType] = useState<SourceType>('textbook');
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      if (selectedFile.type !== 'application/pdf') {
        setError('Please select a PDF file');
        setFile(null);
        return;
      }
      setFile(selectedFile);
      setError(null);
      setResult(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setError(null);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('source_type', sourceType);

      const response = await fetch('http://localhost:8000/ingest', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
      }

      const data: UploadResult = await response.json();
      setResult(data);
      setFile(null);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to upload PDF. Make sure the backend is running.';
      setError(message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-purple-50 p-8">
      <div className="max-w-3xl mx-auto">
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-center mb-2 bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
            Upload Document
          </h1>
          <p className="text-center text-gray-600">
            Upload PDF files to build your knowledge base for question generation
          </p>
        </div>

        <div className="bg-white rounded-2xl shadow-xl p-8 border border-gray-100">
          <div className="space-y-6">
            {/* Source Type Selector */}
            <div className="flex gap-4">
              <button
                type="button"
                onClick={() => setSourceType('textbook')}
                className={`flex-1 py-3 px-4 rounded-lg border-2 transition-all ${
                  sourceType === 'textbook'
                    ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                    : 'border-gray-200 text-gray-600 hover:border-gray-300'
                }`}
              >
                <div className="font-semibold">Textbook</div>
                <div className="text-xs mt-1">Knowledge base content</div>
              </button>
              <button
                type="button"
                onClick={() => setSourceType('exam_paper')}
                className={`flex-1 py-3 px-4 rounded-lg border-2 transition-all ${
                  sourceType === 'exam_paper'
                    ? 'border-purple-500 bg-purple-50 text-purple-700'
                    : 'border-gray-200 text-gray-600 hover:border-gray-300'
                }`}
              >
                <div className="font-semibold">Exam Paper</div>
                <div className="text-xs mt-1">Style profile extraction</div>
              </button>
            </div>

            {/* Upload Area */}
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-indigo-400 transition-colors">
              <input
                type="file"
                accept=".pdf"
                onChange={handleFileChange}
                className="hidden"
                id="file-upload"
              />
              <label
                htmlFor="file-upload"
                className="cursor-pointer flex flex-col items-center"
              >
                <svg
                  className="w-16 h-16 text-gray-400 mb-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  />
                </svg>
                <span className="text-lg font-medium text-gray-700 mb-2">
                  Click to upload PDF
                </span>
                <span className="text-sm text-gray-500">
                  or drag and drop
                </span>
              </label>
            </div>

            {/* Selected File */}
            {file && (
              <div className="flex items-center justify-between bg-gray-50 rounded-lg p-4">
                <div className="flex items-center gap-3">
                  <svg
                    className="w-8 h-8 text-red-600"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" />
                  </svg>
                  <div>
                    <p className="font-medium text-gray-800">{file.name}</p>
                    <p className="text-sm text-gray-500">
                      {(file.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setFile(null)}
                  className="text-gray-400 hover:text-red-600 transition-colors"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            )}

            {/* Upload Button */}
            <button
              onClick={handleUpload}
              disabled={!file || uploading}
              className={`w-full text-white font-semibold py-3 px-6 rounded-lg transition-all shadow-lg hover:shadow-xl ${
                sourceType === 'textbook'
                  ? 'bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700'
                  : 'bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              {uploading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Processing PDF...
                </span>
              ) : (
                `Upload as ${sourceType === 'textbook' ? 'Textbook' : 'Exam Paper'}`
              )}
            </button>

            {/* Error Message */}
            {error && (
              <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded">
                <div className="flex">
                  <svg className="w-5 h-5 text-red-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                  <p className="text-red-800">{error}</p>
                </div>
              </div>
            )}

            {/* Success Message */}
            {result && (
              <div className="bg-green-50 border-l-4 border-green-500 p-4 rounded">
                <div className="flex items-start">
                  <svg className="w-5 h-5 text-green-500 mr-2 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <div>
                    <p className="font-semibold text-green-800 mb-2">Upload Successful!</p>
                    <div className="text-sm text-green-700 space-y-1">
                      <p>✓ Chunks processed: <span className="font-semibold">{result.chunks_processed}</span></p>
                      <p>✓ Embeddings created: <span className="font-semibold">{result.embeddings_created}</span></p>
                      <p>✓ Images processed: <span className="font-semibold">{result.images_processed}</span></p>
                    </div>
                    <p className="text-sm text-green-600 mt-3">
                      {sourceType === 'exam_paper' 
                        ? 'Style profile extracted! Questions will now match this exam\'s pattern.'
                        : 'You can now generate questions based on this content!'}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Navigation */}
        <div className="mt-6 text-center">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-indigo-600 hover:text-indigo-700 font-medium"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Back to Question Generator
          </Link>
        </div>
      </div>
    </div>
  );
}