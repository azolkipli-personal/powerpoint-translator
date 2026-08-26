import { NextRequest, NextResponse } from 'next/server';
import { AUTH_COOKIE, verifyToken } from '@/lib/auth';

// Skip static assets, the login page itself, and the auth endpoint.
export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|login$|api/auth).*)'],
};

export async function middleware(req: NextRequest) {
  const host = req.headers.get('host') || '';
  // Local development bypass is opt-in via AUTH_TRUST_LOCAL=1 — Host is
  // client-controlled, so trusting it by default lets a LAN attacker send
  // "Host: localhost" and skip auth on a server bound to 0.0.0.0.
  const TRUST_LOCAL = process.env.AUTH_TRUST_LOCAL === '1';
  if (TRUST_LOCAL && /^(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$/.test(host)) {
    return NextResponse.next();
  }

  const secret = process.env.AUTH_SECRET;
  if (!secret) {
    // Fail closed: never expose the app publicly without auth configured.
    return new NextResponse('Authentication not configured', { status: 503 });
  }

  const token = req.cookies.get(AUTH_COOKIE)?.value;
  if (await verifyToken(token, secret)) {
    return NextResponse.next();
  }

  if (req.nextUrl.pathname.startsWith('/api/')) {
    return new NextResponse(JSON.stringify({ error: 'Unauthorized' }), {
      status: 401,
      headers: { 'content-type': 'application/json' },
    });
  }

  const url = req.nextUrl.clone();
  url.pathname = '/login';
  url.search =
    req.nextUrl.pathname === '/'
      ? ''
      : `?next=${encodeURIComponent(req.nextUrl.pathname)}`;
  return NextResponse.redirect(url);
}
