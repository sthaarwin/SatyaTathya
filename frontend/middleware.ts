import { NextRequest, NextResponse } from 'next/server';

const PUBLIC_ROUTES = ['/auth', '/auth/callback'];

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // Allow public routes and API routes through
  if (
    PUBLIC_ROUTES.some((r) => pathname.startsWith(r)) ||
    pathname.startsWith('/api/')
  ) {
    return NextResponse.next();
  }

  const accessToken = req.cookies.get('sb-access-token')?.value;
  const refreshToken = req.cookies.get('sb-refresh-token')?.value;

  // No tokens — redirect to login
  if (!accessToken && !refreshToken) {
    return NextResponse.redirect(new URL('/auth', req.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|.*\\.svg$).*)'],
};
