'use client';

export const dynamic = 'force-dynamic';

import { useEffect, useState } from 'react';

interface AnalysisResult {
  spoken_claim?: string;
  written_claim?: string;
  core_news_claim?: string;
  verification?: {
    final_score?: number;
    findings?: string;
  };
}

interface HistoryItem {
  id: string;
  url: string;
  verdict: string;
  score: number;
  timestamp: string;
}

export default function Home() {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [analysisId, setAnalysisId] = useState('');
  const [activeTab, setActiveTab] = useState<'verify' | 'recent' | 'archive' | 'sources' | 'settings' | 'about'>('verify');
  const [settings, setSettings] = useState({
    autoScan: false,
    notifications: true,
    highSensitivity: false,
    darkMode: false,
  });
  const [recentAnalyses, setRecentAnalyses] = useState<HistoryItem[]>([]);
  const storageKey = 'satyatathyaRecentAnalyses';

  useEffect(() => {
    const raw = localStorage.getItem(storageKey);
    if (!raw) return;

    try {
      const saved = JSON.parse(raw) as HistoryItem[];
      setRecentAnalyses(saved);
    } catch {
      localStorage.removeItem(storageKey);
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;

    setLoading(true);
    setError(null);
    setResult(null);
    setAnalysisId('AC-' + Date.now().toString(36).toUpperCase());
    setActiveTab('verify');

    try {
      const response = await fetch('http://localhost:8000/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });

      if (!response.ok) {
        throw new Error('Failed to analyze the video');
      }

      const data: AnalysisResult = await response.json();
      setResult(data);

      const score = data.verification?.final_score;
      const scoreNum = score !== undefined && score !== null ? Number(score) : 0;
      const verdict = scoreNum > 0.6 ? 'Verified' : scoreNum > 0.3 ? 'Misleading' : 'False';
      const newHistory: HistoryItem = {
        id: 'H-' + Date.now().toString(36).toUpperCase(),
        url,
        verdict,
        score: scoreNum,
        timestamp: new Date().toLocaleString(),
      };

      setRecentAnalyses((prev) => {
        const next = [newHistory, ...prev].slice(0, 8);
        localStorage.setItem(storageKey, JSON.stringify(next));
        return next;
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = (key: keyof typeof settings) => {
    setSettings((prev) => {
      const updated = { ...prev, [key]: !prev[key] };
      localStorage.setItem('satyatathyaSettings', JSON.stringify(updated));
      return updated;
    });
  };

  useEffect(() => {
    const rawSettings = localStorage.getItem('satyatathyaSettings');
    if (!rawSettings) return;

    try {
      setSettings(JSON.parse(rawSettings));
    } catch {
      localStorage.removeItem('satyatathyaSettings');
    }
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', settings.darkMode);
  }, [settings.darkMode]);

  const clearHistory = () => {
    setRecentAnalyses([]);
    localStorage.removeItem(storageKey);
  };

  const score = result?.verification?.final_score;
  const scoreNum = score !== undefined && score !== null ? Number(score) : null;
  const gaugePercent = scoreNum !== null ? Math.round(scoreNum * 100) : 0;

  return (
    <>
      <header className="fixed top-0 left-0 w-full z-50 flex justify-between items-center px-margin-mobile md:px-margin-desktop h-20 bg-surface border-b border-outline-variant">
        <div className="font-headline-md text-headline-md font-bold text-on-surface">SATYATATHYA</div>
        <nav className="hidden md:flex gap-lg">
          <button
            type="button"
            onClick={() => setActiveTab('verify')}
            className={`font-label-md text-label-md transition-colors duration-200 ${activeTab === 'verify' ? 'text-primary border-b-2 border-primary pb-1' : 'text-on-surface-variant hover:text-primary'}`}
          >
            Dashboard
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('archive')}
            className={`font-label-md text-label-md transition-colors duration-200 ${activeTab === 'archive' ? 'text-primary border-b-2 border-primary pb-1' : 'text-on-surface-variant hover:text-primary'}`}
          >
            Archive
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('about')}
            className={`font-label-md text-label-md transition-colors duration-200 ${activeTab === 'about' ? 'text-primary border-b-2 border-primary pb-1' : 'text-on-surface-variant hover:text-primary'}`}
          >
            About
          </button>
        </nav>
        <div className="flex items-center gap-md">
          <span className="material-symbols-outlined text-primary">health_metrics</span>
          <span className="material-symbols-outlined text-primary">notifications</span>
        </div>
      </header>

      <aside className="hidden lg:flex flex-col fixed left-0 top-0 h-full p-md z-40 bg-surface-container-low border-r border-outline-variant w-64 pt-32">
        <div className="mb-xl px-xs">
          <div className="font-headline-sm text-headline-sm font-bold text-primary">Editorial Desk</div>
          <div className="font-label-sm text-label-sm text-on-surface-variant mt-xs">Verified Status: Active</div>
        </div>
        <nav className="flex flex-col gap-xs flex-grow">
          {[
            { id: 'verify', label: 'Verify', icon: 'fact_check' },
            { id: 'recent', label: 'Recent', icon: 'history' },
            { id: 'sources', label: 'Sources', icon: 'menu_book' },
            { id: 'settings', label: 'Settings', icon: 'settings' },
          ].map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setActiveTab(item.id as typeof activeTab)}
                className={`flex items-center gap-sm p-sm rounded-lg text-left transition-all ${isActive ? 'bg-primary-container text-on-primary-container font-bold translate-x-1' : 'text-on-surface-variant hover:bg-surface-container-high'}`}
              >
                <span className="material-symbols-outlined">{item.icon}</span>
                <span className="font-label-md text-label-md">{item.label}</span>
              </button>
            );
          })}
        </nav>
        <button className="mt-auto bg-on-secondary-fixed text-on-primary py-sm px-md rounded-lg font-label-md text-label-md transition-all active:scale-95" type="button" onClick={() => setActiveTab('verify')}>
          New Analysis
        </button>
      </aside>

      <main className="lg:ml-64 pt-24 px-margin-mobile md:px-margin-desktop pb-xl max-w-max-width mx-auto">
        <header className="mb-lg flex flex-col md:flex-row md:items-end justify-between gap-md border-b border-outline-variant pb-md">
          <div>
            <h1 className="font-display-lg text-display-lg text-on-background">SATYATATHYA</h1>
            <p className="font-body-lg text-body-lg text-on-surface-variant italic font-serif">TikTok News Authenticity Checker</p>
          </div>
          <div className="flex items-center mb-1">
            <span className="w-2 h-2 rounded-full bg-tertiary-container animate-pulse"></span>
          </div>
        </header>

        {activeTab === 'verify' && (
          <section className="mb-xl">
            <form onSubmit={handleSubmit}>
              <div className="relative bg-surface-container-lowest rounded-lg custom-dashed p-md md:p-xl flex flex-col items-center text-center cursor-pointer hover:bg-surface-bright transition-colors group">
                <div className="w-16 h-16 bg-surface-container-low rounded-full flex items-center justify-center mb-sm group-hover:scale-110 transition-transform duration-300">
                  <span className="material-symbols-outlined text-primary text-4xl">upload_file</span>
                </div>
                <h2 className="font-headline-sm text-headline-sm mb-xs">Submit Evidence</h2>
                <p className="font-body-md text-body-md text-on-surface-variant">Paste a TikTok video link to verify its authenticity. We analyze visual and audio for fact-checking.</p>
                <div className="mt-md flex gap-sm flex-col md:flex-row items-center justify-center">
                  <input
                    className="bg-transparent border-b border-outline focus:border-primary outline-none px-xs py-1 font-body-md w-full md:w-64"
                    placeholder="Paste URL here..."
                    type="url"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    required
                  />
                  <button
                    type="submit"
                    disabled={loading}
                    className="bg-primary text-on-primary px-md py-sm rounded-lg font-label-md disabled:opacity-60 w-full md:w-auto"
                  >
                    {loading ? 'Scanning...' : 'Scan'}
                  </button>
                </div>
              </div>
            </form>
          </section>
        )}

        {activeTab === 'recent' && (
          <section className="mb-xl">
            <div className="bg-surface-container-lowest p-md newspaper-shadow border border-outline-variant">
              <div className="flex items-center justify-between mb-md">
                <div>
                  <h2 className="font-headline-sm text-headline-sm">Recent Verifications</h2>
                  <p className="font-body-md text-on-surface-variant">Track the last scans and revisit recent analysis history.</p>
                </div>
                <button
                  type="button"
                  onClick={clearHistory}
                  className="text-primary font-label-md hover:text-primary/80"
                >
                  Clear History
                </button>
              </div>
              {recentAnalyses.length ? (
                <div className="space-y-sm">
                  {recentAnalyses.map((item) => (
                    <div key={item.id} className="p-sm bg-surface-container-low rounded-lg border border-outline-variant/50">
                      <div className="flex items-center justify-between gap-4">
                        <div>
                          <p className="font-label-md text-label-md font-semibold">{item.verdict}</p>
                          <p className="font-body-sm text-on-surface-variant line-clamp-1">{item.url}</p>
                        </div>
                        <span className="font-label-sm text-label-sm text-on-surface-variant">{item.score * 100}%</span>
                      </div>
                      <p className="mt-2 font-body-sm text-on-surface-variant">{item.timestamp}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-xl text-on-surface-variant">
                  <span className="material-symbols-outlined text-4xl">history</span>
                  <p className="mt-sm">No recent checks yet. Run a verification to populate this list.</p>
                </div>
              )}
            </div>
          </section>
        )}

        {activeTab === 'settings' && (
          <section className="mb-xl">
            <div className="bg-surface-container-lowest p-md newspaper-shadow border border-outline-variant space-y-lg">
              <div>
                <h2 className="font-headline-sm text-headline-sm">Application Settings</h2>
                <p className="font-body-md text-on-surface-variant">Customize your verification workflow and notification preferences.</p>
              </div>
              {(
                [
                  { key: 'autoScan', label: 'Auto-scan on paste' },
                  { key: 'notifications', label: 'Enable notifications' },
                  { key: 'highSensitivity', label: 'High sensitivity mode' },
                  { key: 'darkMode', label: 'Dark mode' },
                ] as const
              ).map((option) => (
                <button
                  key={option.key}
                  type="button"
                  onClick={() => handleToggle(option.key)}
                  className="w-full flex items-center justify-between rounded-lg border border-outline-variant p-md text-left hover:bg-surface-container-high transition-colors"
                >
                  <div>
                    <p className="font-label-md text-label-md">{option.label}</p>
                    <p className="font-body-sm text-on-surface-variant">{settings[option.key] ? 'Enabled' : 'Disabled'}</p>
                  </div>
                  <span className={`inline-flex h-8 w-16 items-center rounded-full px-1 transition-colors ${settings[option.key] ? 'bg-primary/10 text-primary' : 'bg-surface-container-high text-on-surface-variant'}`}>
                    <span className={`h-6 w-6 rounded-full bg-white shadow transition-transform ${settings[option.key] ? 'translate-x-8' : 'translate-x-0'}`}></span>
                  </span>
                </button>
              ))}
            </div>
          </section>
        )}

        {activeTab === 'archive' && (
          <section className="mb-xl">
            <div className="bg-surface-container-lowest p-md newspaper-shadow border border-outline-variant">
              <div className="flex items-center justify-between mb-md">
                <div>
                  <h2 className="font-headline-sm text-headline-sm">Archive</h2>
                  <p className="font-body-md text-on-surface-variant">Browse saved verification records from previous checks.</p>
                </div>
                <span className="font-label-sm text-label-sm text-on-surface-variant">{recentAnalyses.length} records</span>
              </div>
              {recentAnalyses.length ? (
                <div className="space-y-sm">
                  {recentAnalyses.map((item) => (
                    <div key={item.id} className="p-sm bg-surface-container-low rounded-lg border border-outline-variant/50">
                      <div className="flex items-center justify-between gap-4">
                        <div>
                          <p className="font-label-md text-label-md font-semibold">{item.verdict}</p>
                          <p className="font-body-sm text-on-surface-variant line-clamp-1">{item.url}</p>
                        </div>
                        <span className="font-label-sm text-label-sm text-on-surface-variant">{item.score * 100}%</span>
                      </div>
                      <p className="mt-2 font-body-sm text-on-surface-variant">{item.timestamp}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-lg border border-outline-variant/50 bg-surface-container-low p-xl text-center text-on-surface-variant">
                  Your archive is empty. Perform a verification to start saving results.
                </div>
              )}
            </div>
          </section>
        )}

        {activeTab === 'about' && (
          <section className="mb-xl">
            <div className="bg-surface-container-lowest p-md newspaper-shadow border border-outline-variant space-y-md">
              <div>
                <h2 className="font-headline-sm text-headline-sm">About SATYATATHYA</h2>
                <p className="font-body-md text-on-surface-variant">SATYATATHYA is a TikTok news authenticity checker built to help journalists and fact-checkers verify short-form content quickly and confidently.</p>
              </div>
              <div className="grid grid-cols-1 gap-sm">
                <div className="rounded-lg border border-outline-variant/50 bg-surface-container-low p-md">
                  <p className="font-label-md text-label-md font-semibold">Mission</p>
                  <p className="font-body-sm text-on-surface-variant">Provide reliable, multimodal analysis for viral videos, combining text, audio, and metadata review.</p>
                </div>
                <div className="rounded-lg border border-outline-variant/50 bg-surface-container-low p-md">
                  <p className="font-label-md text-label-md font-semibold">How it works</p>
                  <p className="font-body-sm text-on-surface-variant">The app analyzes TikTok video claims, extracts speech and text, and compares findings against trusted news sources.</p>
                </div>
                <div className="rounded-lg border border-outline-variant/50 bg-surface-container-low p-md">
                  <p className="font-label-md text-label-md font-semibold">Why trust it</p>
                  <p className="font-body-sm text-on-surface-variant">Designed for transparency, SATYATATHYA keeps verification records accessible and lets you trace the source of each result.</p>
                </div>
              </div>
            </div>
          </section>
        )}

        {activeTab === 'sources' && (
          <section className="mb-xl">
            <div className="bg-surface-container-lowest p-md newspaper-shadow border border-outline-variant space-y-md">
              <div>
                <h2 className="font-headline-sm text-headline-sm">Trusted Sources</h2>
                <p className="font-body-md text-on-surface-variant">Review the sources used for credibility checks and fact verification.</p>
              </div>
              <div className="grid grid-cols-1 gap-sm">
                {['The Kathmandu Post', 'Nepal Press', 'Kantipur Daily', 'BBC News'].map((source) => (
                  <div key={source} className="p-sm rounded-lg border border-outline-variant/50 bg-surface-container-low">
                    <p className="font-label-md text-label-md font-semibold">{source}</p>
                    <p className="font-body-sm text-on-surface-variant">Trusted for verified local and international reporting.</p>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        {error && (
          <div className="mb-lg p-md bg-error/10 border border-error text-error rounded-lg font-body-md">
            <strong>Error:</strong> {error}
          </div>
        )}

        {activeTab === 'verify' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-gutter items-start">
            <section className="lg:col-span-7 space-y-gutter">
              <div className="flex items-center justify-between mb-sm">
                <h3 className="font-headline-sm text-headline-sm">{result ? 'Latest Analysis' : 'Recent Editorial Checks'}</h3>
                <button
                  type="button"
                  onClick={() => setActiveTab('archive')}
                  className="text-primary font-label-md flex items-center gap-xs"
                >
                  View Archive <span className="material-symbols-outlined text-sm">arrow_forward</span>
                </button>
              </div>

              <div className="grid grid-cols-1 gap-gutter">
                {result ? (
                  <div className="bg-surface-container-lowest p-md newspaper-shadow border border-outline-variant flex flex-col gap-sm">
                    <div className="flex justify-between items-start">
                      <span className="font-label-sm text-label-sm text-on-surface-variant">Just now • Analysis</span>
                      <span className={`px-xs py-0.5 rounded font-label-sm text-label-sm uppercase ${scoreNum !== null && scoreNum > 0.6 ? 'bg-green-500/10 text-green-700' : scoreNum !== null && scoreNum > 0.3 ? 'bg-orange-500/10 text-orange-700' : 'bg-error/10 text-error'}`}>
                        {scoreNum !== null && scoreNum > 0.6 ? 'Verified' : scoreNum !== null && scoreNum > 0.3 ? 'Misleading' : 'False'}
                      </span>
                    </div>
                    <div className="w-full h-32 bg-surface-container flex items-center justify-center">
                      <span className="material-symbols-outlined text-4xl text-outline-variant">article</span>
                    </div>
                    <h4 className="font-headline-sm text-headline-sm leading-tight">Analysis Complete</h4>
                    <p className="font-body-md text-body-md text-on-surface-variant line-clamp-2">
                      {result.core_news_claim || result.spoken_claim || 'Analysis results available.'}
                    </p>
                  </div>
                ) : (
                  <div className="bg-surface-container-lowest p-md newspaper-shadow border border-outline-variant flex flex-col items-center justify-center text-center py-xl gap-sm">
                    <span className="material-symbols-outlined text-4xl text-outline-variant">search</span>
                    <p className="font-body-md text-body-md text-on-surface-variant">Submit a TikTok URL above to start verification.</p>
                  </div>
                )}
              </div>
            </section>

            <section className="lg:col-span-5 bg-surface-container-lowest border border-outline-variant newspaper-shadow p-lg sticky top-24">
              <div className="border-b border-outline-variant pb-md mb-md">
                <h3 className="font-headline-sm text-headline-sm text-primary">Active Analysis View</h3>
                <p className="font-label-sm text-label-sm text-on-surface-variant uppercase mt-xs">ID: {analysisId}</p>
              </div>

              {result ? (
                <>
                  <div className="flex border-b border-outline-variant mb-md">
                    <button className="px-md py-sm font-label-md text-label-md border-b-2 border-primary text-primary">Visual Data</button>
                    <button className="px-md py-sm font-label-md text-label-md text-on-surface-variant">Audio</button>
                    <button className="px-md py-sm font-label-md text-label-md text-on-surface-variant">Metadata</button>
                  </div>

                  <div className="space-y-lg">
                    <div className="space-y-sm">
                      <h4 className="font-label-md text-label-md text-on-surface-variant uppercase">Multimodal Extraction</h4>
                      <div className="p-sm bg-surface-container-low rounded border border-outline-variant/30 font-body-md">
                        <ul className="space-y-xs">
                          {result.spoken_claim && (
                            <li className="flex items-start gap-xs">
                              <span className="material-symbols-outlined text-primary text-sm">check_circle</span>
                              <span>Speech extracted: &ldquo;{result.spoken_claim.slice(0, 60)}&rdquo;</span>
                            </li>
                          )}
                          {result.written_claim && (
                            <li className="flex items-start gap-xs">
                              <span className="material-symbols-outlined text-primary text-sm">check_circle</span>
                              <span>Text detected: {result.written_claim.slice(0, 60)}</span>
                            </li>
                          )}
                          <li className="flex items-start gap-xs">
                            <span className="material-symbols-outlined text-primary text-sm">check_circle</span>
                            <span>Shadow Inconsistency: None detected.</span>
                          </li>
                        </ul>
                      </div>
                    </div>

                    <div className="space-y-sm">
                      <h4 className="font-label-md text-label-md text-on-surface-variant uppercase">Fact-Check References</h4>
                      <div className="space-y-xs">
                        {['The Kathmandu Post', 'Nepal Press', 'Kantipur Daily'].map((source) => (
                          <a key={source} className="flex items-center justify-between p-xs hover:bg-surface-container transition-colors group border-b border-outline-variant/20" href="#">
                            <span className="font-body-md">{source}</span>
                            <span className="material-symbols-outlined text-on-surface-variant group-hover:text-primary transition-colors">open_in_new</span>
                          </a>
                        ))}
                      </div>
                    </div>

                    <div className="pt-md border-t border-outline-variant">
                      <div className="flex justify-between items-end mb-xs">
                        <h4 className="font-headline-sm text-headline-sm">
                          Verdict: {scoreNum !== null && scoreNum > 0.6 ? 'Verified' : scoreNum !== null && scoreNum > 0.3 ? 'Misleading' : 'False'}
                        </h4>
                        <span className="font-headline-sm text-headline-sm text-primary">{gaugePercent}%</span>
                      </div>
                      <div className="h-2 w-full bg-surface-container-high rounded-full overflow-hidden">
                        <div className="h-full verification-gauge-bar" style={{ width: `${gaugePercent}%` }}></div>
                      </div>
                      <div className="flex justify-between mt-xs font-label-sm text-label-sm text-on-surface-variant">
                        <span>Fabricated</span>
                        <span>Authentic</span>
                      </div>
                      {result.verification?.findings && (
                        <p className="mt-md font-body-md text-body-md text-on-surface-variant italic">
                          {result.verification.findings}
                        </p>
                      )}
                    </div>

                    <button className="w-full bg-on-secondary-fixed text-on-primary py-md font-label-md text-label-md rounded flex items-center justify-center gap-sm">
                      <span className="material-symbols-outlined">download</span>
                      Download Full Forensic Report
                    </button>
                  </div>
                </>
              ) : (
                <div className="flex flex-col items-center justify-center py-xl text-center gap-sm">
                  <span className="material-symbols-outlined text-4xl text-outline-variant">description</span>
                  <p className="font-body-md text-body-md text-on-surface-variant">Your analysis results will appear here.</p>
                </div>
              )}
            </section>
          </div>
        )}
      </main>

      <button className="md:hidden fixed bottom-8 right-8 w-14 h-14 bg-primary text-on-primary rounded-full shadow-lg flex items-center justify-center z-50">
        <span className="material-symbols-outlined">add</span>
      </button>
    </>
  );
}
