import React, { memo } from "react";

const StudyPanel = memo(function StudyPanel({
  isOpen,
  token,
  isGenerating,
  error,
  onClose,
  onGenerateFlashcard,
}) {
  if (!isOpen) return null;

  return (
    <aside className="fixed inset-y-0 right-0 z-40 w-full max-w-md border-l border-slate-200 bg-white shadow-xl">
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <h2 className="text-base font-semibold text-slate-900">Estudo da Palavra</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-2 py-1 text-sm font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-700"
          >
            Fechar
          </button>
        </div>

        <div className="space-y-4 overflow-y-auto px-5 py-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Lema</p>
            <p className="mt-1 text-lg font-semibold text-slate-900">{token?.lemma || "-"}</p>
          </div>

          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Tradução</p>
            <p className="mt-1 text-sm text-slate-800">{token?.translation || "-"}</p>
          </div>

          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Caso gramatical</p>
            <p className="mt-1 text-sm text-slate-800">{token?.grammaticalCase || token?.grammatical_case || "-"}</p>
          </div>

          {error ? (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
          ) : null}
        </div>

        <div className="mt-auto border-t border-slate-200 px-5 py-4">
          <button
            type="button"
            onClick={onGenerateFlashcard}
            disabled={isGenerating || !token}
            className="w-full rounded-md bg-slate-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isGenerating ? "Gerando..." : "Gerar Flashcard Dinâmico"}
          </button>
        </div>
      </div>
    </aside>
  );
});

export default StudyPanel;