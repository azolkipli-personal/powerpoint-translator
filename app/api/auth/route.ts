import { NextRequest, NextResponse } from 'next/server';
import { createHash, timingSafeEqual } from 'node:crypto';
import { AUTH_COOKIE, TOKEN_TTL_DAYS, makeToken } from '@/lib/auth';

export const config = { matcher: ['/api/auth'] };

export async function POST(req: NextRequest) {
  const secret = process.env.AUTH_SECRET;
  const passphrase = process.env.SITE_PASSPHRASE;
  if (!secret || !passphrase) {
    return NextResponse.json({ error: 'Auth not configured' }, { status: 503 });
  }

  let supplied = '';
  try {
    const body = await req.json();
    supplied = typeof body?.passphrase === 'string' ? body.passphrase.trim() : '';
  } catch {
    return NextResponse.json({ error: 'Invalid request' }, { status: 400 });
  }

  const a = createHash('sha256').update(supplied ?? '').digest();
  const b = createHash('sha256').update(passphrase ?? '').digest();
  if (!timingSafeEqual(a, b)) {
    // Small delay to blunt brute-force attempts.
    await new Promise((r) => setTimeout(r, 800));
    return NextResponse.json({ error: 'Incorrect passphrase' }, { status: 401 });
  }

  const token = await makeToken(secret);
  const res = NextResponse.json({ ok: true });
  res.cookies.set(AUTH_COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: TOKEN_TTL_DAYS * 24 * 60 * 60,
    path: '/',
  });
  return res;
}
