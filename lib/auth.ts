// Shared auth helpers — Edge-runtime compatible (WebCrypto only).
// Used by middleware.ts (edge) and app/api/auth/route.ts (node).

export const AUTH_COOKIE = 'jpeigo_auth';
export const TOKEN_TTL_DAYS = 30;

const enc = new TextEncoder();

function toHex(buf: ArrayBuffer): string {
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

async function hmac(secret: string, payload: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    'raw',
    enc.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(payload));
  return toHex(sig);
}

/** Token format: `<expiryEpochSeconds>.<hmac(expiry)>` */
export async function makeToken(secret: string, ttlDays = TOKEN_TTL_DAYS): Promise<string> {
  const exp = Math.floor(Date.now() / 1000) + ttlDays * 24 * 60 * 60;
  const sig = await hmac(secret, String(exp));
  return `${exp}.${sig}`;
}

export async function verifyToken(token: string | undefined, secret: string): Promise<boolean> {
  if (!token) return false;
  const dot = token.indexOf('.');
  if (dot <= 0) return false;
  const expStr = token.slice(0, dot);
  const sig = token.slice(dot + 1);
  const exp = parseInt(expStr, 10);
  if (!Number.isFinite(exp) || exp < Math.floor(Date.now() / 1000)) return false;
  const expected = await hmac(secret, expStr);
  if (expected.length !== sig.length) return false;
  // Constant-time compare
  let diff = 0;
  for (let i = 0; i < expected.length; i++) diff |= expected.charCodeAt(i) ^ sig.charCodeAt(i);
  return diff === 0;
}
