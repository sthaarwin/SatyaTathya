import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function GET() {
  for (const base of ['http://127.0.0.1:8000', process.env.NEXT_PUBLIC_API_URL].filter(Boolean)) {
    try {
      const res = await fetch(`${base}/api/sources`);
      if (res.ok) {
        return NextResponse.json(await res.json());
      }
    } catch {}
  }
  return NextResponse.json({ sources: [] });
}
