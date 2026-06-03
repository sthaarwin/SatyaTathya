"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

type AuthMode = "login" | "signup";

interface FormState {
  email: string;
  password: string;
  confirmPassword?: string;
  fullName?: string;
}

export default function AuthPage() {
  const router = useRouter();
  const [mode, setMode] = useState<AuthMode>("login");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>({ email: "", password: "", confirmPassword: "", fullName: "" });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);

    if (mode === "signup" && form.password !== form.confirmPassword) {
      setError("Passwords do not match.");
      setLoading(false);
      return;
    }

    const endpoint = mode === "login" ? "/api/auth/login" : "/api/auth/signup";

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: form.email,
          password: form.password,
          ...(mode === "signup" && { full_name: form.fullName }),
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || "Authentication failed.");
      }

      if (mode === "signup") {
        setSuccess("Account created. Check your email to confirm your address.");
      } else {
        router.push("/");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  };

  const switchMode = (newMode: AuthMode) => {
    setMode(newMode);
    setError(null);
    setSuccess(null);
    setForm({ email: "", password: "", confirmPassword: "", fullName: "" });
  };

  return (
    <>
      <header className="fixed top-0 left-0 w-full z-50 flex justify-between items-center px-margin-mobile md:px-margin-desktop h-20 max-w-max-width mx-auto bg-surface border-b border-outline-variant">
        <a href="/" className="font-headline-md text-headline-md font-bold text-on-surface tracking-tight hover:text-primary transition-colors duration-200">
          SATYATATHYA
        </a>
        <nav className="hidden md:flex gap-lg">
          <a className="font-label-md text-label-md text-on-surface-variant hover:text-primary transition-colors duration-200" href="#">About</a>
          <a className="font-label-md text-label-md text-on-surface-variant hover:text-primary transition-colors duration-200" href="#">Archive</a>
        </nav>
        <div className="flex items-center gap-md">
          <span className="material-symbols-outlined text-primary">lock</span>
        </div>
      </header>

      <main className="min-h-screen pt-20 flex flex-col lg:flex-row bg-surface">
        <aside className="hidden lg:flex flex-col justify-between w-[45%] min-h-[calc(100vh-5rem)] bg-on-background p-16 relative overflow-hidden">
          <div className="absolute inset-0 opacity-5 pointer-events-none" aria-hidden="true">
            {Array.from({ length: 20 }).map((_, i) => (
              <div key={i} className="border-b border-on-surface" style={{ height: "5%" }} />
            ))}
          </div>
          <span className="absolute -bottom-8 -right-4 text-[22rem] font-black text-on-surface opacity-[0.04] select-none leading-none tracking-tighter pointer-events-none" aria-hidden="true">S</span>

          <div className="relative z-10">
            <div className="inline-flex items-center gap-xs mb-xl">
              <span className="w-2 h-2 rounded-full bg-tertiary-container animate-pulse" />
              <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest">Press Verified System</span>
            </div>
            <h1 className="font-display-lg text-display-lg text-primary leading-none mb-lg">
              THE TRUTH<br /><span className="text-on-surface-variant">STARTS</span><br />HERE.
            </h1>
            <p className="font-body-lg text-body-lg text-on-surface-variant max-w-sm font-serif italic leading-relaxed">
              Join Nepal&rsquo;s most rigorous TikTok news verification platform. Every claim scrutinised. Every source cited. No exceptions.
            </p>
          </div>

          <div className="relative z-10 space-y-md">
            <div className="border-t border-outline-variant pt-md">
              <div className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest mb-sm">Editorial Standards</div>
              <ul className="space-y-xs">
                {[
                  { icon: "verified", text: "Multimodal AI analysis" },
                  { icon: "policy", text: "Cross-referenced with verified sources" },
                  { icon: "shield", text: "End-to-end encrypted sessions" },
                ].map(({ icon, text }) => (
                  <li key={text} className="flex items-center gap-sm font-body-md text-body-md text-on-surface-variant">
                    <span className="material-symbols-outlined text-primary text-base">{icon}</span>
                    {text}
                  </li>
                ))}
              </ul>
            </div>
            <div className="border-t border-outline-variant pt-md flex items-center gap-sm">
              <span className="material-symbols-outlined text-outline-variant text-sm">newspaper</span>
              <span className="font-label-sm text-label-sm text-on-surface-variant italic">Trusted by journalists across Nepal</span>
            </div>
          </div>
        </aside>

        <section className="flex-1 flex flex-col items-center justify-center px-margin-mobile md:px-16 py-xl">
          <div className="w-full max-w-md">
            <div className="flex border-b border-outline-variant mb-xl">
              {(["login", "signup"] as const).map((m) => (
                <button key={m} onClick={() => switchMode(m)}
                  className={`flex-1 py-sm font-label-md text-label-md uppercase tracking-widest transition-all duration-200 border-b-2 -mb-px ${mode === m ? "border-primary text-primary" : "border-transparent text-on-surface-variant hover:text-on-surface"}`}>
                  {m === "login" ? "Sign In" : "Create Account"}
                </button>
              ))}
            </div>

            <div className="mb-xl">
              <h2 className="font-headline-md text-headline-md text-on-background mb-xs">
                {mode === "login" ? "Welcome back, Editor." : "Join the Editorial Desk."}
              </h2>
              <p className="font-body-md text-body-md text-on-surface-variant">
                {mode === "login" ? "Sign in to access your analysis dashboard." : "Create an account to start verifying content."}
              </p>
            </div>

            {error && (
              <div className="mb-md p-sm bg-error/10 border border-error text-error rounded-lg font-body-md flex items-start gap-sm">
                <span className="material-symbols-outlined text-base mt-0.5">error</span>
                {error}
              </div>
            )}
            {success && (
              <div className="mb-md p-sm bg-green-500/10 border border-green-500 text-green-700 rounded-lg font-body-md flex items-start gap-sm">
                <span className="material-symbols-outlined text-base mt-0.5">check_circle</span>
                {success}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-md">
              {mode === "signup" && (
                <div className="space-y-xs">
                  <label className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest" htmlFor="fullName">Full Name</label>
                  <div className="relative">
                    <span className="material-symbols-outlined absolute left-sm top-1/2 -translate-y-1/2 text-outline-variant text-base">person</span>
                    <input id="fullName" name="fullName" type="text" autoComplete="name" value={form.fullName} onChange={handleChange} required={mode === "signup"} placeholder="Aarav Sharma"
                      className="w-full pl-10 pr-sm py-sm bg-surface-container-low border border-outline-variant rounded-lg font-body-md text-on-surface placeholder:text-on-surface-variant/50 focus:outline-none focus:border-primary transition-colors" />
                  </div>
                </div>
              )}

              <div className="space-y-xs">
                <label className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest" htmlFor="email">Email Address</label>
                <div className="relative">
                  <span className="material-symbols-outlined absolute left-sm top-1/2 -translate-y-1/2 text-outline-variant text-base">mail</span>
                  <input id="email" name="email" type="email" autoComplete="email" value={form.email} onChange={handleChange} required placeholder="editor@example.com"
                    className="w-full pl-10 pr-sm py-sm bg-surface-container-low border border-outline-variant rounded-lg font-body-md text-on-surface placeholder:text-on-surface-variant/50 focus:outline-none focus:border-primary transition-colors" />
                </div>
              </div>

              <div className="space-y-xs">
                <label className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest" htmlFor="password">Password</label>
                <div className="relative">
                  <span className="material-symbols-outlined absolute left-sm top-1/2 -translate-y-1/2 text-outline-variant text-base">lock</span>
                  <input id="password" name="password" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} value={form.password} onChange={handleChange} required placeholder="••••••••"
                    className="w-full pl-10 pr-sm py-sm bg-surface-container-low border border-outline-variant rounded-lg font-body-md text-on-surface placeholder:text-on-surface-variant/50 focus:outline-none focus:border-primary transition-colors" />
                </div>
                {mode === "signup" && <p className="font-label-sm text-label-sm text-on-surface-variant">Minimum 8 characters.</p>}
              </div>

              {mode === "signup" && (
                <div className="space-y-xs">
                  <label className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest" htmlFor="confirmPassword">Confirm Password</label>
                  <div className="relative">
                    <span className="material-symbols-outlined absolute left-sm top-1/2 -translate-y-1/2 text-outline-variant text-base">lock_reset</span>
                    <input id="confirmPassword" name="confirmPassword" type="password" autoComplete="new-password" value={form.confirmPassword} onChange={handleChange} required={mode === "signup"} placeholder="••••••••"
                      className="w-full pl-10 pr-sm py-sm bg-surface-container-low border border-outline-variant rounded-lg font-body-md text-on-surface placeholder:text-on-surface-variant/50 focus:outline-none focus:border-primary transition-colors" />
                  </div>
                </div>
              )}

              {mode === "login" && (
                <div className="flex justify-end">
                  <a href="/forgot-password" className="font-label-sm text-label-sm text-primary hover:underline">Forgot password?</a>
                </div>
              )}

              <button type="submit" disabled={loading}
                className="w-full bg-primary text-on-primary py-sm rounded-lg font-label-md text-label-md uppercase tracking-widest flex items-center justify-center gap-sm disabled:opacity-60 transition-all active:scale-[0.98]">
                {loading ? (
                  <><span className="material-symbols-outlined text-base animate-spin">progress_activity</span>Processing…</>
                ) : mode === "login" ? (
                  <><span className="material-symbols-outlined text-base">login</span>Sign In</>
                ) : (
                  <><span className="material-symbols-outlined text-base">how_to_reg</span>Create Account</>
                )}
              </button>
            </form>

            <div className="flex items-center gap-md my-xl">
              <div className="flex-1 border-t border-outline-variant" />
              <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest">or</span>
              <div className="flex-1 border-t border-outline-variant" />
            </div>

            <button type="button"
              className="w-full flex items-center justify-center gap-sm py-sm bg-surface-container-low border border-outline-variant rounded-lg font-label-md text-label-md text-on-surface hover:bg-surface-container transition-colors"
              onClick={async () => {
                const res = await fetch("/api/auth/google");
                const data = await res.json();
                if (data.url) window.location.href = data.url;
              }}>
              <svg viewBox="0 0 24 24" className="w-5 h-5" aria-hidden="true">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
              </svg>
              Continue with Google
            </button>

            <p className="mt-xl text-center font-body-md text-body-md text-on-surface-variant">
              {mode === "login" ? (
                <>No account yet?{" "}<button onClick={() => switchMode("signup")} className="text-primary hover:underline font-medium">Create one</button></>
              ) : (
                <>Already have an account?{" "}<button onClick={() => switchMode("login")} className="text-primary hover:underline font-medium">Sign in</button></>
              )}
            </p>

            <p className="mt-lg text-center font-label-sm text-label-sm text-on-surface-variant/60 italic">
              By continuing, you agree to SATYATATHYA&apos;s editorial standards and privacy policy.
            </p>
          </div>
        </section>
      </main>
    </>
  );
}
