/**
 * Proxy API route for job status polling.
 * Forwards to Python FastAPI backend GET /api/jobs/{job_id}.
 */
import { NextRequest, NextResponse } from 'next/server';

const PYTHON_BACKEND_URL = process.env.PYTHON_BACKEND_URL || 'http://localhost:8002';

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ job_id: string }> }
) {
  const { job_id } = await params;
  try {
    const res = await fetch(`${PYTHON_BACKEND_URL}/api/jobs/${encodeURIComponent(job_id)}`, {
      cache: 'no-store',
    });
    if (!res.ok) {
      return NextResponse.json({ error: 'Job not found' }, { status: res.status });
    }
    const data = await res.json();
    // Only expose lightweight status fields
    return NextResponse.json({
      status: data.status,
      progress: data.progress,
      total_runs: data.total_runs,
    });
  } catch {
    return NextResponse.json({ error: 'Backend unavailable' }, { status: 502 });
  }
}
