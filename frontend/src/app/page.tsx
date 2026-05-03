'use client';

import { useState } from 'react';

export default function Home() {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;
    
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch('http://localhost:8000/api/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url }),
      });

      if (!response.ok) {
        throw new Error('Failed to analyze the video');
      }

      const data = await response.json();
      setResult(data);
    } catch (err: any) {
      setError(err.message || 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-gray-50 flex flex-col items-center p-8">
      <div className="text-center max-w-4xl w-full mt-10">
        <h1 className="text-5xl font-extrabold text-gray-900 mb-4 tracking-tight">
          Satya<span className="text-blue-600">Tathya</span>
        </h1>
        <p className="text-xl text-gray-600 mb-8">
          The Multimodal Fact-Checking Engine for Nepali Social Media
        </p>
        
        <div className="bg-white p-6 rounded-xl shadow-lg w-full mb-8">
          <form className="flex flex-col md:flex-row gap-4" onSubmit={handleSubmit}>
            <input 
              type="url" 
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="Paste a Video URL here..." 
              className="flex-1 p-4 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-lg text-gray-800"
              required
            />
            <button 
              type="submit" 
              disabled={loading}
              className="md:w-auto w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-bold py-4 px-8 rounded-lg transition-colors text-lg whitespace-nowrap"
            >
              {loading ? 'Analyzing...' : 'Analyze Truth'}
            </button>
          </form>
        </div>

        {error && (
          <div className="bg-red-50 text-red-700 p-4 rounded-lg mb-8 shadow-sm border border-red-200 text-left">
            <strong>Error:</strong> {error}
          </div>
        )}

        {result && (
          <div className="bg-white p-8 rounded-xl shadow-lg w-full text-left space-y-6">
            <h2 className="text-2xl font-bold border-b pb-2">Analysis Results</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-gray-50 p-4 rounded-lg border">
                <h3 className="font-semibold text-gray-700 mb-2">Spoken Claim</h3>
                <p className="text-gray-900">{result.spoken_claim || "None"}</p>
              </div>
              <div className="bg-gray-50 p-4 rounded-lg border">
                <h3 className="font-semibold text-gray-700 mb-2">Written Claim</h3>
                <p className="text-gray-900">{result.written_claim || "None"}</p>
              </div>
            </div>

            <div className="bg-blue-50 p-5 rounded-lg border border-blue-100">
              <h3 className="font-bold text-blue-900 mb-2">Core Unified Claim</h3>
              <p className="text-blue-900 text-lg">{result.core_news_claim || "None"}</p>
            </div>

            {result.verification && (
              <div className="mt-8">
                <h2 className="text-2xl font-bold border-b pb-2 mb-4">Verification Check</h2>
                <div className="bg-green-50 text-green-900 p-5 rounded-lg border border-green-200 shadow-sm">
                   <div className="mb-4">
                     <span className="font-bold text-xl block mb-2">
                       Truth Score: <span className="text-3xl">{result.verification.final_score ?? "N/A"}</span>
                     </span>
                   </div>
                   <div className="space-y-2 text-sm">
                      <p className="font-semibold">Context:</p>
                      <p className="whitespace-pre-line leading-relaxed text-gray-800">
                        {result.verification.findings || "No findings retrieved."}
                      </p>
                   </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
