'use client';

import React, { useState, useEffect } from 'react';

// --- Types (mirror translator page) ---
interface TextRun { run_id: string; text: string; style: { font_size: number | null; font_color: string | null; font_name: string | null; bold: boolean; italic: boolean; underline: boolean; }; }
interface TextBox { box_id: string; shape_type: string; runs: TextRun[]; constraints: { left: number; top: number; width: number; height: number; }; }
interface Slide { slide_index: number; slide_id: number; text_boxes: TextBox[]; }
interface SlidesDocument { presentation_id: string; filename: string; total_slides: number; total_runs: number; slides: Slide[]; }
interface TranslatedRun { run_id: string; original_text: string; translated_text: string; model_used: string; }
interface Presentation { id: string; name: string; }

const en = {
  authenticateFirst: 'Connect your Google account to translate Google Slides presentations.',
  connect: 'Connect Google Account',
  connecting: 'Connecting…',
  selectPresentation: 'Select a presentation',
  disconnect: 'Disconnect',
  loadingPresentations: 'Loading presentations…',
  noPresentations: 'No presentations found',
  reload: 'Reload',
  runs: 'text runs',
  slides: 'slides',
  translate: 'Translate',
  translating: 'Translating…',
  download: 'Download PPTX',
  exporting: 'Exporting…',
  startOver: 'Start over',
  done: 'done',
  failed: 'failed',
  original: 'Original',
  translation: 'Translation',
  translateFailed: 'Translation failed',
  exportFailed: 'Export failed',
  noRuns: 'No text runs found to translate',
  slideLabel: 'Slide',
};
const ja: typeof en = {
  authenticateFirst: 'Googleスライドを翻訳するには、Googleアカウントと連携してください。',
  connect: 'Googleアカウントと連携',
  connecting: '接続中…',
  selectPresentation: 'プレゼンテーションを選択',
  disconnect: '連携解除',
  loadingPresentations: 'プレゼンテーションを読み込み中…',
  noPresentations: 'プレゼンテーションが見つかりません',
  reload: '再読み込み',
  runs: 'テキスト',
  slides: 'スライド',
  translate: '翻訳する',
  translating: '翻訳中…',
  download: 'PPTXをダウンロード',
  exporting: 'エクスポート中…',
  startOver: '最初から',
  done: '完了',
  failed: '失敗',
  original: '原文',
  translation: '翻訳文',
  translateFailed: '翻訳失敗',
  exportFailed: 'エクスポート失敗',
  noRuns: '翻訳するテキストが見つかりません',
  slideLabel: 'スライド',
};

type Lang = 'en' | 'ja';
const t = (lang: Lang) => lang === 'en' ? en : ja;

interface Props {
  ui: 'en' | 'ja';
  sourceLang: 'ja' | 'en';
  targetLang: 'ja' | 'en';
  model: string;
  contextPrompt: string;
}

export default function SlidesPanel({ ui, sourceLang, targetLang, model, contextPrompt }: Props) {
  const lang = ui;
  const text = t(lang);

  const [authStatus, setAuthStatus] = useState<'checking' | 'unauthenticated' | 'authenticated'>('checking');
  const [presentations, setPresentations] = useState<Presentation[]>([]);
  const [loadingPres, setLoadingPres] = useState(false);
  const [presError, setPresError] = useState<string | null>(null);
  const [selected, setSelected] = useState<SlidesDocument | null>(null);
  const [selecting, setSelecting] = useState(false);
  const [translatedRuns, setTranslatedRuns] = useState<TranslatedRun[]>([]);
  const [translating, setTranslating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    fetch('/api/slides/auth/status')
      .then(r => r.json())
      .then(data => {
        const authed = data?.authenticated === true;
        setAuthStatus(authed ? 'authenticated' : 'unauthenticated');
        if (authed) loadPresentations();
      })
      .catch(() => setAuthStatus('unauthenticated'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function loadPresentations() {
    setLoadingPres(true);
    setPresError(null);
    fetch('/api/slides/presentations')
      .then(r => {
        if (!r.ok) throw new Error('failed');
        return r.json();
      })
      .then(data => setPresentations(data.presentations || []))
      .catch(() => setPresError('Failed to load presentations'))
      .finally(() => setLoadingPres(false));
  }

  function handleConnect() {
    setAuthStatus('checking');
    fetch('/api/slides/auth/url')
      .then(r => r.json())
      .then(data => {
        if (data?.url) {
          window.location.href = data.url;
        } else {
          setAuthStatus('unauthenticated');
        }
      })
      .catch(() => setAuthStatus('unauthenticated'));
  }

  function handleDisconnect() {
    fetch('/api/slides/auth/logout', { method: 'POST' }).finally(() => {
      setAuthStatus('unauthenticated');
      setPresentations([]);
      setSelected(null);
    });
  }

  function handleSelect(pres: Presentation) {
    setSelecting(true);
    setErrorMsg(null);
    fetch(`/api/slides/read/${encodeURIComponent(pres.id)}`)
      .then(r => {
        if (!r.ok) throw new Error('failed');
        return r.json();
      })
      .then((data: SlidesDocument) => {
        setSelected(data);
        setTranslatedRuns([]);
      })
      .catch(() => setErrorMsg('Failed to open presentation'))
      .finally(() => setSelecting(false));
  }

  async function handleTranslate() {
    if (!selected) return;
    setTranslating(true);
    setErrorMsg(null);
    setProgress(0);
    try {
      const allRuns: TextRun[] = [];
      for (const slide of selected.slides) for (const textBox of slide.text_boxes) allRuns.push(...textBox.runs);
      if (allRuns.length === 0) throw new Error(text.noRuns);
      const body: Record<string, unknown> = {
        presentation_id: selected.presentation_id,
        runs: allRuns,
        source_language: sourceLang,
        target_language: targetLang,
        model,
      };
      if (contextPrompt.trim()) body.context = contextPrompt.trim();
      const res = await fetch('/api/slides/translate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(text.translateFailed);
      const data = await res.json();
      setTranslatedRuns(data.translated_runs || []);
      setProgress(100);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : text.translateFailed);
    } finally {
      setTranslating(false);
    }
  }

  async function handleExport() {
    if (!selected || translatedRuns.length === 0) return;
    setExporting(true);
    setErrorMsg(null);
    try {
      const res = await fetch('/api/export-new', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: selected.presentation_id, filename: `translated_${selected.filename}` }),
      });
      if (!res.ok) throw new Error(text.exportFailed);
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = window.document.createElement('a');
      a.href = url;
      a.download = `translated_${selected.filename}`;
      window.document.body.appendChild(a);
      a.click();
      window.document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : text.exportFailed);
    } finally {
      setExporting(false);
    }
  }

  const completedCount = translatedRuns.filter(r => r.original_text !== r.translated_text || r.model_used === 'cache').length;
  const failedCount = translatedRuns.filter(r => r.original_text === r.translated_text && r.model_used !== 'cache').length;
  const allDone = selected && translatedRuns.length > 0 && !translating;

  if (authStatus === 'checking') {
    return (
      <div className="max-w-xl mx-auto mt-8">
        <div className="bg-white dark:bg-zinc-900 border border-gray-200 dark:border-zinc-800 rounded-xl p-8 text-center">
          <svg className="animate-spin h-6 w-6 text-blue-500 mx-auto mb-3" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <p className="text-sm text-gray-500 dark:text-zinc-400">{text.connecting}</p>
        </div>
      </div>
    );
  }

  if (authStatus === 'unauthenticated') {
    return (
      <div className="max-w-xl mx-auto mt-8">
        <div className="bg-white dark:bg-zinc-900 border border-gray-200 dark:border-zinc-800 rounded-xl p-8 text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-blue-50 dark:bg-blue-950/50 mb-4">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#1a73e8" strokeWidth="1.5">
              <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
            </svg>
          </div>
          <h2 className="text-lg font-medium text-gray-800 dark:text-zinc-100 mb-2">Google Slides</h2>
          <p className="text-sm text-gray-500 dark:text-zinc-400 mb-5">{text.authenticateFirst}</p>
          <button onClick={handleConnect}
            className="px-6 py-2.5 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 transition-colors shadow-sm inline-flex items-center gap-2">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
            {text.connect}
          </button>
          {errorMsg && <p className="mt-4 text-sm text-red-600 dark:text-red-400">{errorMsg}</p>}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto mt-8">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-medium text-gray-700 dark:text-zinc-200">{text.selectPresentation}</h2>
        <button onClick={handleDisconnect} className="text-xs text-gray-400 dark:text-zinc-500 hover:text-red-500 transition-colors">
          {text.disconnect}
        </button>
      </div>

      {loadingPres && (
        <div className="bg-white dark:bg-zinc-900 border border-gray-200 dark:border-zinc-800 rounded-xl p-6 text-center">
          <svg className="animate-spin h-5 w-5 text-blue-500 mx-auto mb-2" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <p className="text-sm text-gray-500 dark:text-zinc-400">{text.loadingPresentations}</p>
        </div>
      )}

      {presError && !loadingPres && (
        <div className="bg-white dark:bg-zinc-900 border border-gray-200 dark:border-zinc-800 rounded-xl p-8 text-center">
          <p className="text-sm text-gray-500 dark:text-zinc-400">{presError}</p>
          <button onClick={loadPresentations} className="mt-3 text-sm text-blue-600 hover:underline">{text.reload}</button>
        </div>
      )}

      {!loadingPres && !presError && presentations.length === 0 && (
        <div className="bg-white dark:bg-zinc-900 border border-gray-200 dark:border-zinc-800 rounded-xl p-8 text-center">
          <p className="text-sm text-gray-500 dark:text-zinc-400">{text.noPresentations}</p>
        </div>
      )}

      {!loadingPres && !presError && presentations.length > 0 && (
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {presentations.map(pres => (
            <button key={pres.id} onClick={() => handleSelect(pres)} disabled={selecting}
              className="w-full text-left bg-white dark:bg-zinc-900 border border-gray-200 dark:border-zinc-800 hover:border-blue-300 dark:hover:border-blue-700 hover:bg-blue-50/30 dark:hover:bg-blue-950/30 rounded-xl p-4 transition-all">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-gray-800 dark:text-zinc-100 truncate">{pres.name}</p>
                </div>
                {selecting && <svg className="animate-spin h-4 w-4 text-blue-500 flex-shrink-0" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>}
              </div>
            </button>
          ))}
        </div>
      )}

      {selected && (
        <div className="mt-6">
          <div className="flex items-center gap-2.5 mb-6 pb-4 border-b border-gray-200 dark:border-zinc-800">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" className="stroke-zinc-500 dark:stroke-zinc-400" strokeWidth="1.5">
              <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/>
            </svg>
            <span className="text-sm text-gray-700 dark:text-zinc-200 truncate">
              {selected.filename} · {selected.total_slides} {text.slides}, {selected.total_runs} {text.runs}
            </span>
          </div>

          {errorMsg && (
            <div className="mb-4 px-4 py-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 rounded-lg text-sm text-red-700 dark:text-red-300">{errorMsg}</div>
          )}

          <div className="flex items-center gap-3">
            <button onClick={handleTranslate} disabled={translating}
              className="px-6 py-2.5 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 dark:disabled:bg-zinc-700 disabled:text-gray-500 dark:disabled:text-zinc-500 transition-colors shadow-sm">
              {translating ? text.translating : text.translate}
            </button>
            {allDone && (
              <button onClick={handleExport} disabled={exporting}
                className="px-6 py-2.5 rounded-lg text-sm font-medium text-white bg-green-600 hover:bg-green-700 disabled:bg-gray-300 dark:disabled:bg-zinc-700 transition-colors shadow-sm">
                {exporting ? text.exporting : text.download}
              </button>
            )}
            {translatedRuns.length > 0 && (
              <div className="flex items-center gap-2 text-xs">
                <span className="text-green-700 dark:text-green-300 bg-green-50 dark:bg-green-950/50 px-2.5 py-1 rounded-full">{completedCount}/{translatedRuns.length} {text.done}</span>
                {failedCount > 0 && <span className="text-yellow-700 dark:text-yellow-300 bg-yellow-50 dark:bg-yellow-950/50 px-2.5 py-1 rounded-full">{failedCount} {text.failed}</span>}
              </div>
            )}
          </div>

          {translating && (
            <div className="mt-4">
              <div className="flex items-center justify-between text-sm mb-2">
                <span className="text-gray-500 dark:text-zinc-400">{text.translating}</span>
                <span className="text-blue-600 font-medium">{progress}%</span>
              </div>
              <div className="h-2 bg-gray-100 dark:bg-zinc-800 rounded-full overflow-hidden">
                <div className="h-full bg-blue-500 rounded-full transition-all duration-500 ease-out" style={{ width: `${progress}%` }} />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
