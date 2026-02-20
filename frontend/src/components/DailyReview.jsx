import React, { useMemo, useState } from "react";
import { submitFlashcardReview } from "../api_client";

const SCORE_BUTTONS = [
  { score: 1, label: "1 - Errei (Amanhã)", className: "bg-red-700 hover:bg-red-600 border-red-900" },
  { score: 2, label: "2 - Difícil", className: "bg-orange-700 hover:bg-orange-600 border-orange-900" },
  { score: 3, label: "3 - Bom", className: "bg-blue-700 hover:bg-blue-600 border-blue-900" },
  { score: 4, label: "4 - Fácil", className: "bg-emerald-700 hover:bg-emerald-600 border-emerald-900" },
];

export default function DailyReview({ cards = [], onFinish, onProgress }) {
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const current = useMemo(() => cards[index] || null, [cards, index]);

  const handleReveal = () => setRevealed(true);

  const handleRate = async (score) => {
    if (!current || submitting) return;

    setSubmitting(true);
    setError("");

    try {
      await submitFlashcardReview(current.id, score);
      const nextIndex = index + 1;
      if (typeof onProgress === "function") onProgress(nextIndex);

      if (nextIndex >= cards.length) {
        if (typeof onFinish === "function") onFinish();
      } else {
        setIndex(nextIndex);
        setRevealed(false);
      }
    } catch (err) {
      setError(err?.message || "Falha ao salvar revisão.");
    } finally {
      setSubmitting(false);
    }
  };

  if (!cards.length) {
    return (
      <section className="mt-8 border border-gray-700 bg-[#151515] p-6 shadow-[6px_6px_0_#2b2b2b] rounded-sm">
        <h2 className="text-xl font-extrabold uppercase tracking-[0.14em] text-emerald-300">Treino Diário</h2>
        <p className="mt-3 text-gray-300">Nenhum card pendente para hoje.</p>
      </section>
    );
  }

  if (!current) {
    return (
      <section className="mt-8 border border-gray-700 bg-[#151515] p-6 shadow-[6px_6px_0_#2b2b2b] rounded-sm">
        <h2 className="text-xl font-extrabold uppercase tracking-[0.14em] text-emerald-300">Treino Diário</h2>
        <p className="mt-3 text-gray-300">Treino concluído.</p>
      </section>
    );
  }

  return (
    <section className="mt-8 border border-gray-700 bg-[#151515] p-6 shadow-[6px_6px_0_#2b2b2b] rounded-sm">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-xl font-extrabold uppercase tracking-[0.14em] text-emerald-300">Treino Diário</h2>
        <span className="text-xs font-bold uppercase tracking-wider text-gray-400">
          Card {index + 1} / {cards.length}
        </span>
      </div>

      <div className="mt-5 border border-white/10 bg-black/30 p-4 rounded-sm">
        <p className="text-xs font-bold uppercase tracking-[0.12em] text-gray-400">Desafio em Português</p>
        <p className="mt-2 text-sm text-gray-100">{current.challenge_pt || "-"}</p>
      </div>

      {!revealed ? (
        <button
          type="button"
          onClick={handleReveal}
          className="mt-4 bg-purple-700 hover:bg-purple-600 text-white font-bold py-2.5 px-5 border-b-4 border-purple-900 hover:border-purple-800 active:border-b-0 active:translate-y-[4px] transition-all rounded-none uppercase tracking-wider text-xs"
        >
          Revelar
        </button>
      ) : (
        <div className="mt-4 space-y-3">
          <div className="border border-blue-500/40 bg-blue-950/30 p-4 rounded-sm">
            <p className="text-xs font-bold uppercase tracking-[0.12em] text-blue-300">Palavra em Alemão</p>
            <p className="mt-1 text-sm text-blue-100">{current.word || "-"}</p>
          </div>

          <div className="border border-purple-500/40 bg-purple-950/30 p-4 rounded-sm">
            <p className="text-xs font-bold uppercase tracking-[0.12em] text-purple-300">Jargão C1</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {(current.nivel_c1 || []).map((item, idx) => (
                <span key={`${item}-${idx}`} className="border border-purple-400 bg-purple-900/40 px-2.5 py-1 text-xs font-bold text-purple-100 rounded-none">
                  {item}
                </span>
              ))}
              {(!current.nivel_c1 || current.nivel_c1.length === 0) ? <span className="text-sm text-purple-100">-</span> : null}
            </div>
          </div>

          <div className="border border-emerald-500/40 bg-emerald-950/30 p-4 rounded-sm">
            <p className="text-xs font-bold uppercase tracking-[0.12em] text-emerald-300">Contexto Original</p>
            <p className="mt-1 text-sm text-emerald-100">{current.context_original || current.variacao_nativa || "-"}</p>
          </div>

          {error ? <div className="border border-red-500 bg-red-950/40 p-3 text-sm text-red-200 rounded-sm">{error}</div> : null}

          <div className="grid grid-cols-1 gap-2 pt-1 sm:grid-cols-2">
            {SCORE_BUTTONS.map((option) => (
              <button
                key={option.score}
                type="button"
                onClick={() => handleRate(option.score)}
                disabled={submitting}
                className={`${option.className} text-white font-bold py-2.5 px-4 border-b-4 active:border-b-0 active:translate-y-[4px] transition-all rounded-none uppercase tracking-wider text-xs disabled:opacity-60 disabled:cursor-not-allowed`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
