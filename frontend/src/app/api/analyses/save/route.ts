import { createClient } from '@supabase/supabase-js';
import { NextRequest, NextResponse } from 'next/server';

export async function POST(req: NextRequest) {
  try {
    const accessToken = req.cookies.get('sb-access-token')?.value;
    if (!accessToken) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const supabase = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      { global: { headers: { Authorization: `Bearer ${accessToken}` } } },
    );

    const { data: { user }, error: userError } = await supabase.auth.getUser(accessToken);
    if (userError || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const body = await req.json();
    const { error } = await supabase.from('user_analyses').insert({
      user_id: user.id,
      url: body.url,
      spoken_claim: body.spoken_claim,
      written_claim: body.written_claim,
      core_news_claim: body.core_news_claim,
      evidence_findings: body.evidence_findings,
      reasoning: body.reasoning,
      truth_score: body.truth_score,
      verdict: body.verdict,
      thumbnail: body.thumbnail,
    });

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json({ status: 'saved' });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
