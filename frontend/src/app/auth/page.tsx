'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

type AuthMode = 'login' | 'signup';

interface FormState {
  email: string;
  password: string;
  confirmPassword: string;
  fullName: string;
}

export default function AuthPage() {
  const router = useRouter();
  const [mode, setMode] = useState<AuthMode>('login');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>({
    email: '',
    password: '',
    confirmPassword: '',
    fullName: '',
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);

    if (mode === 'signup' && form.password !== form.confirmPassword) {
      setError('Passwords do not match.');
      setLoading(false);
      return;
    }

    if (mode === 'signup' && form.password.length < 8) {
      setError('Password must be at least 8 characters.');
      setLoading(false);
      return;
    }

    const endpoint = mode === 'login' ? '/api/auth/login' : '/api/auth/signup';

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: form.email,
          password: form.password,
          ...(mode === 'signup' && { full_name: form.fullName }),
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || 'Authentication failed.');
      }

      router.push('/');
      router.refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred.');
    } finally {
      setLoading(false);
    }
  };

  const switchMode = (newMode: AuthMode) => {
    setMode(newMode);
    setError(null);
    setSuccess(null);
    setForm({ email: '', password: '', confirmPassword: '', fullName: '' });
  };

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#fbf9f5', display: 'flex', flexDirection: 'column' }}>

      {/* ── Header ── */}
      <header style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 50,
        height: '72px', backgroundColor: '#fbf9f5',
        borderBottom: '1px solid #d6c3b9',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 48px',
      }}>
        <a href="/" style={{
          fontFamily: '"Playfair Display", serif',
          fontSize: '20px', fontWeight: 700,
          color: '#1b1c1a', textDecoration: 'none', letterSpacing: '-0.01em',
        }}>
          SATYATATHYA
        </a>
        <nav style={{ display: 'flex', gap: '32px' }}>
          {['About', 'Archive'].map((item) => (
            <a key={item} href="#" style={{
              fontFamily: '"Plus Jakarta Sans", sans-serif',
              fontSize: '14px', fontWeight: 600,
              color: '#52443d', textDecoration: 'none',
            }}>{item}</a>
          ))}
        </nav>
        <span className="material-symbols-outlined" style={{ color: '#825032' }}>lock</span>
      </header>

      {/* ── Body ── */}
      <div style={{ display: 'flex', flex: 1, paddingTop: '72px', minHeight: '100vh' }}>

        {/* ── Left editorial panel ── */}
        <aside style={{
          width: '45%', minHeight: 'calc(100vh - 72px)',
          backgroundColor: '#1b1c1a',
          padding: '64px', display: 'flex', flexDirection: 'column',
          justifyContent: 'space-between', position: 'relative', overflow: 'hidden',
        }}
          className="auth-aside"
        >
          {/* Ruled lines */}
          <div style={{ position: 'absolute', inset: 0, opacity: 0.05, pointerEvents: 'none' }}>
            {Array.from({ length: 20 }).map((_, i) => (
              <div key={i} style={{ height: '5%', borderBottom: '1px solid #fbf9f5' }} />
            ))}
          </div>

          {/* Big S */}
          <span style={{
            position: 'absolute', bottom: '-32px', right: '-16px',
            fontSize: '320px', fontWeight: 900, fontFamily: '"Playfair Display", serif',
            color: '#fbf9f5', opacity: 0.04, lineHeight: 1, userSelect: 'none',
            pointerEvents: 'none',
          }}>S</span>

          {/* Top content */}
          <div style={{ position: 'relative', zIndex: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '48px' }}>
              <span style={{
                width: '8px', height: '8px', borderRadius: '50%',
                backgroundColor: '#7e726e', display: 'inline-block',
              }} className="pulse-dot" />
              <span style={{
                fontFamily: '"Plus Jakarta Sans", sans-serif',
                fontSize: '12px', fontWeight: 500, color: '#52443d',
                textTransform: 'uppercase', letterSpacing: '0.1em',
              }}>Press Verified System</span>
            </div>

            <h1 style={{
              fontFamily: '"Playfair Display", serif',
              fontSize: '56px', fontWeight: 700, lineHeight: 1.05,
              color: '#825032', marginBottom: '32px', letterSpacing: '-0.02em',
            }}>
              THE TRUTH<br />
              <span style={{ color: '#52443d' }}>STARTS</span><br />
              HERE.
            </h1>

            <p style={{
              fontFamily: '"Playfair Display", serif',
              fontSize: '18px', lineHeight: 1.7, color: '#52443d',
              fontStyle: 'italic', maxWidth: '360px',
            }}>
              Nepal&rsquo;s most rigorous TikTok news verification platform.
              Every claim scrutinised. Every source cited. No exceptions.
            </p>
          </div>

          {/* Bottom content */}
          <div style={{ position: 'relative', zIndex: 10 }}>
            <div style={{ borderTop: '1px solid #d6c3b9', paddingTop: '24px', marginBottom: '24px' }}>
              <p style={{
                fontFamily: '"Plus Jakarta Sans", sans-serif',
                fontSize: '12px', fontWeight: 500, color: '#52443d',
                textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '16px',
              }}>Editorial Standards</p>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {[
                  { icon: 'verified', text: 'Multimodal AI analysis' },
                  { icon: 'policy', text: 'Cross-referenced with verified sources' },
                  { icon: 'shield', text: 'End-to-end encrypted sessions' },
                ].map(({ icon, text }) => (
                  <li key={text} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span className="material-symbols-outlined" style={{ color: '#825032', fontSize: '18px' }}>{icon}</span>
                    <span style={{ fontFamily: '"Plus Jakarta Sans", sans-serif', fontSize: '14px', color: '#52443d' }}>{text}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div style={{ borderTop: '1px solid #d6c3b9', paddingTop: '24px', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span className="material-symbols-outlined" style={{ color: '#84746c', fontSize: '16px' }}>newspaper</span>
              <span style={{ fontFamily: '"Plus Jakarta Sans", sans-serif', fontSize: '12px', color: '#52443d', fontStyle: 'italic' }}>
                Trusted by journalists across Nepal
              </span>
            </div>
          </div>
        </aside>

        {/* ── Right auth panel ── */}
        <section style={{
          flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: '48px 64px', backgroundColor: '#fbf9f5',
        }}>
          <div style={{ width: '100%', maxWidth: '440px' }}>

            {/* Tab switcher */}
            <div style={{ display: 'flex', borderBottom: '1px solid #d6c3b9', marginBottom: '40px' }}>
              {(['login', 'signup'] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => switchMode(m)}
                  style={{
                    flex: 1, padding: '14px 0', border: 'none', background: 'none', cursor: 'pointer',
                    fontFamily: '"Plus Jakarta Sans", sans-serif',
                    fontSize: '13px', fontWeight: 600, letterSpacing: '0.08em',
                    textTransform: 'uppercase',
                    color: mode === m ? '#825032' : '#52443d',
                    borderBottom: mode === m ? '2px solid #825032' : '2px solid transparent',
                    marginBottom: '-1px',
                    transition: 'all 0.2s',
                  }}
                >
                  {m === 'login' ? 'Sign In' : 'Create Account'}
                </button>
              ))}
            </div>

            {/* Heading */}
            <div style={{ marginBottom: '32px' }}>
              <h2 style={{
                fontFamily: '"Playfair Display", serif',
                fontSize: '28px', fontWeight: 600, color: '#1b1c1a',
                marginBottom: '8px', lineHeight: 1.3,
              }}>
                {mode === 'login' ? 'Welcome back, Editor.' : 'Join the Editorial Desk.'}
              </h2>
              <p style={{ fontFamily: '"Plus Jakarta Sans", sans-serif', fontSize: '15px', color: '#52443d', lineHeight: 1.6 }}>
                {mode === 'login'
                  ? 'Sign in to access your analysis dashboard.'
                  : 'Create an account to start verifying content.'}
              </p>
            </div>

            {/* Error / Success banners */}
            {error && (
              <div style={{
                marginBottom: '20px', padding: '12px 16px',
                backgroundColor: 'rgba(186,26,26,0.08)', border: '1px solid #ba1a1a',
                borderRadius: '8px', display: 'flex', alignItems: 'flex-start', gap: '10px',
              }}>
                <span className="material-symbols-outlined" style={{ color: '#ba1a1a', fontSize: '18px', marginTop: '1px' }}>error</span>
                <span style={{ fontFamily: '"Plus Jakarta Sans", sans-serif', fontSize: '14px', color: '#ba1a1a' }}>{error}</span>
              </div>
            )}
            {success && (
              <div style={{
                marginBottom: '20px', padding: '12px 16px',
                backgroundColor: 'rgba(76,175,80,0.08)', border: '1px solid #4caf50',
                borderRadius: '8px', display: 'flex', alignItems: 'flex-start', gap: '10px',
              }}>
                <span className="material-symbols-outlined" style={{ color: '#4caf50', fontSize: '18px', marginTop: '1px' }}>check_circle</span>
                <span style={{ fontFamily: '"Plus Jakarta Sans", sans-serif', fontSize: '14px', color: '#2e7d32' }}>{success}</span>
              </div>
            )}

            {/* Form */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

              {mode === 'signup' && (
                <div>
                  <label style={labelStyle} htmlFor="fullName">Full Name</label>
                  <div style={inputWrapStyle}>
                    <span className="material-symbols-outlined" style={iconStyle}>person</span>
                    <input
                      id="fullName" name="fullName" type="text"
                      autoComplete="name" value={form.fullName}
                      onChange={handleChange} required={mode === 'signup'}
                      placeholder="Aarav Sharma"
                      style={inputStyle}
                    />
                  </div>
                </div>
              )}

              <div>
                <label style={labelStyle} htmlFor="email">Email Address</label>
                <div style={inputWrapStyle}>
                  <span className="material-symbols-outlined" style={iconStyle}>mail</span>
                  <input
                    id="email" name="email" type="email"
                    autoComplete="email" value={form.email}
                    onChange={handleChange} required
                    placeholder="editor@example.com"
                    style={inputStyle}
                  />
                </div>
              </div>

              <div>
                <label style={labelStyle} htmlFor="password">Password</label>
                <div style={inputWrapStyle}>
                  <span className="material-symbols-outlined" style={iconStyle}>lock</span>
                  <input
                    id="password" name="password" type="password"
                    autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                    value={form.password} onChange={handleChange}
                    required placeholder="••••••••"
                    style={inputStyle}
                  />
                </div>
                {mode === 'signup' && (
                  <p style={{ fontFamily: '"Plus Jakarta Sans", sans-serif', fontSize: '12px', color: '#52443d', marginTop: '6px' }}>
                    Minimum 8 characters.
                  </p>
                )}
              </div>

              {mode === 'signup' && (
                <div>
                  <label style={labelStyle} htmlFor="confirmPassword">Confirm Password</label>
                  <div style={inputWrapStyle}>
                    <span className="material-symbols-outlined" style={iconStyle}>lock_reset</span>
                    <input
                      id="confirmPassword" name="confirmPassword" type="password"
                      autoComplete="new-password" value={form.confirmPassword}
                      onChange={handleChange} required={mode === 'signup'}
                      placeholder="••••••••"
                      style={inputStyle}
                    />
                  </div>
                </div>
              )}

              {mode === 'login' && (
                <div style={{ textAlign: 'right' }}>
                  <a href="/forgot-password" style={{
                    fontFamily: '"Plus Jakarta Sans", sans-serif',
                    fontSize: '13px', color: '#825032', textDecoration: 'none',
                  }}>Forgot password?</a>
                </div>
              )}

              <button
                onClick={handleSubmit}
                disabled={loading}
                style={{
                  width: '100%', padding: '14px',
                  backgroundColor: loading ? '#b08060' : '#825032',
                  color: '#ffffff', border: 'none', borderRadius: '8px',
                  fontFamily: '"Plus Jakarta Sans", sans-serif',
                  fontSize: '13px', fontWeight: 600, letterSpacing: '0.08em',
                  textTransform: 'uppercase', cursor: loading ? 'not-allowed' : 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                  transition: 'background-color 0.2s',
                }}
              >
                {loading ? (
                  <><span className="material-symbols-outlined" style={{ fontSize: '18px' }}>progress_activity</span> Processing…</>
                ) : mode === 'login' ? (
                  <><span className="material-symbols-outlined" style={{ fontSize: '18px' }}>login</span> Sign In</>
                ) : (
                  <><span className="material-symbols-outlined" style={{ fontSize: '18px' }}>how_to_reg</span> Create Account</>
                )}
              </button>
            </div>

            {/* Divider */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', margin: '32px 0' }}>
              <div style={{ flex: 1, borderTop: '1px solid #d6c3b9' }} />
              <span style={{ fontFamily: '"Plus Jakarta Sans", sans-serif', fontSize: '12px', color: '#52443d', textTransform: 'uppercase', letterSpacing: '0.08em' }}>or</span>
              <div style={{ flex: 1, borderTop: '1px solid #d6c3b9' }} />
            </div>

            {/* Google */}
            <button
              type="button"
              onClick={async () => {
                const res = await fetch('/api/auth/google');
                const data = await res.json();
                if (data.url) window.location.href = data.url;
              }}
              style={{
                width: '100%', padding: '13px',
                backgroundColor: '#f5f3ef', border: '1px solid #d6c3b9',
                borderRadius: '8px', cursor: 'pointer',
                fontFamily: '"Plus Jakarta Sans", sans-serif',
                fontSize: '14px', fontWeight: 600, color: '#1b1c1a',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px',
                transition: 'background-color 0.2s',
              }}
            >
              <svg viewBox="0 0 24 24" style={{ width: '20px', height: '20px' }} aria-hidden="true">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
              </svg>
              Continue with Google
            </button>

            {/* Toggle */}
            <p style={{
              marginTop: '32px', textAlign: 'center',
              fontFamily: '"Plus Jakarta Sans", sans-serif', fontSize: '14px', color: '#52443d',
            }}>
              {mode === 'login' ? (
                <>No account yet?{' '}
                  <button onClick={() => switchMode('signup')} style={{ background: 'none', border: 'none', color: '#825032', fontWeight: 600, cursor: 'pointer', fontSize: '14px', fontFamily: '"Plus Jakarta Sans", sans-serif' }}>
                    Create one
                  </button>
                </>
              ) : (
                <>Already have an account?{' '}
                  <button onClick={() => switchMode('login')} style={{ background: 'none', border: 'none', color: '#825032', fontWeight: 600, cursor: 'pointer', fontSize: '14px', fontFamily: '"Plus Jakarta Sans", sans-serif' }}>
                    Sign in
                  </button>
                </>
              )}
            </p>

            <p style={{
              marginTop: '16px', textAlign: 'center',
              fontFamily: '"Plus Jakarta Sans", sans-serif', fontSize: '12px', color: '#84746c', fontStyle: 'italic',
            }}>
              By continuing, you agree to SATYATATHYA&apos;s editorial standards and privacy policy.
            </p>
          </div>
        </section>
      </div>

      <style>{`
        .auth-aside { display: flex; }
        @media (max-width: 1023px) { .auth-aside { display: none !important; } }
        .pulse-dot { animation: pulse 2s cubic-bezier(0.4,0,0.6,1) infinite; }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
        input:focus { outline: none; border-color: #825032 !important; box-shadow: 0 0 0 3px rgba(130,80,50,0.12); }
        input::placeholder { color: #84746c; opacity: 0.6; }
      `}</style>
    </div>
  );
}

// ── Shared input styles ──────────────────────────────────────────
const labelStyle: React.CSSProperties = {
  display: 'block',
  fontFamily: '"Plus Jakarta Sans", sans-serif',
  fontSize: '12px', fontWeight: 600,
  color: '#52443d', textTransform: 'uppercase',
  letterSpacing: '0.08em', marginBottom: '8px',
};

const inputWrapStyle: React.CSSProperties = {
  position: 'relative',
  display: 'flex',
  alignItems: 'center',
};

const iconStyle: React.CSSProperties = {
  position: 'absolute', left: '14px',
  color: '#84746c', fontSize: '18px',
  pointerEvents: 'none',
};

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '13px 16px 13px 44px',
  backgroundColor: '#f5f3ef',
  border: '1px solid #d6c3b9',
  borderRadius: '8px',
  fontFamily: '"Plus Jakarta Sans", sans-serif',
  fontSize: '15px', color: '#1b1c1a',
  transition: 'border-color 0.2s, box-shadow 0.2s',
  boxSizing: 'border-box',
};

