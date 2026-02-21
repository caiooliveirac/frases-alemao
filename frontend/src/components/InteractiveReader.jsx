import React, { useState } from "react";
import { evaluateStudyTranslation, generateStudyFlashcard } from "../api_client";

function normalizeCaseForClass(caso) {
  if (caso === "Nom") return "NOM";
  if (caso === "Akk") return "AKK";
  if (caso === "Dat") return "DAT";
  return caso;
}

function getCaseClass(caso) {
  if (caso === "NOM") return "bg-blue-900/50 text-blue-200 border-b-2 border-blue-500 font-medium px-1.5 py-0.5 mx-0.5 cursor-pointer hover:bg-blue-800 transition-colors";
  if (caso === "AKK") return "bg-red-900/50 text-red-200 border-b-2 border-red-500 font-medium px-1.5 py-0.5 mx-0.5 cursor-pointer hover:bg-red-800 transition-colors";
  if (caso === "DAT") return "bg-purple-900/50 text-purple-200 border-b-2 border-purple-500 font-medium px-1.5 py-0.5 mx-0.5 cursor-pointer hover:bg-purple-800 transition-colors";
  if (caso === "GEN") return "bg-yellow-900/50 text-yellow-200 border-b-2 border-yellow-500 font-medium px-1.5 py-0.5 mx-0.5 cursor-pointer hover:bg-yellow-800 transition-colors";
  return "text-gray-300 hover:text-white hover:bg-gray-800 px-1 mx-0.5 cursor-pointer transition-colors";
}

export default function InteractiveReader({ data }) {
  const [explicacao, setExplicacao] = useState(null);
  const [loading, setLoading] = useState(false);
  const [tentativaDe, setTentativaDe] = useState("");
  const [avaliando, setAvaliando] = useState(false);
  const [resultadoAvaliacao, setResultadoAvaliacao] = useState(null);
  const [tokenSelecionado, setTokenSelecionado] = useState(null);

  const tokens = data?.tokens || [];
  const documentId = data?.document?.id || data?.document_id;

  const handleClickToken = async (token) => {
    const palavraId = token?.palavra?.id || token?.word?.id || token?.word_token_id;
    if (!documentId || !palavraId) return;

    setLoading(true);
    setTokenSelecionado(token);
    setExplicacao(null);
    setResultadoAvaliacao(null);
    setTentativaDe("");

    try {
      const payload = await generateStudyFlashcard(documentId, palavraId);

      const resultado = payload?.llm_result || null;
      setExplicacao(resultado);
    } catch (error) {
      setExplicacao({
        analise_rapida: error?.message || "Erro ao consultar o Oberarzt.",
        nivel_c1: [],
        variacao_nativa: "",
        desafio_traducao: "",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleEnviarTraducao = async () => {
    if (!explicacao?.desafio_traducao || !tentativaDe.trim() || avaliando) return;

    setAvaliando(true);
    setResultadoAvaliacao(null);

    try {
      const contextoOriginal =
        tokenSelecionado?.context_sentence ||
        tokenSelecionado?.sentence ||
        explicacao?.variacao_nativa ||
        "";

      const avaliacao = await evaluateStudyTranslation(
        explicacao.desafio_traducao,
        tentativaDe,
        contextoOriginal,
      );
      setResultadoAvaliacao(avaliacao);
    } catch (error) {
      setResultadoAvaliacao({
        correto: false,
        feedback_curto: error?.message || "Erro ao avaliar tradução.",
        versao_ideal: "",
      });
    } finally {
      setAvaliando(false);
    }
  };

  if (!tokens.length) {
    return <div className="text-sm text-gray-500">Nenhum token disponível.</div>;
  }

  return (
    <div className="mt-4 space-y-6">
      <div className="leading-9 font-mono text-[15px] tracking-wide">
        {tokens.map((token) => {
          const lema = token?.palavra?.lema || token?.word?.lemma || token?.lemma || token?.surface || "";
          const posTag = token?.palavra?.pos_tag || token?.word?.pos_tag || token?.pos || "";
          const casoRaw = token?.caso_gramatical || token?.grammatical_case || token?.case || "";
          const caso = normalizeCaseForClass(casoRaw);

          return (
            <span
              key={token.id || token.token_id}
              title={`lemma: ${lema} | pos_tag: ${posTag}`}
              className={getCaseClass(caso)}
              onClick={() => handleClickToken(token)}
            >
              {lema}
              {" "}
            </span>
          );
        })}
      </div>

      {loading ? <div className="text-sm text-blue-300">Consultando o Oberarzt...</div> : null}
      {!loading && explicacao ? (
        <div className="mt-8 p-6 bg-white/5 border border-white/10 backdrop-blur-xl rounded-sm shadow-[0_8px_32px_0_rgba(0,0,0,0.37)]">
          <h3 className="mb-5 text-lg font-black uppercase tracking-[0.14em] text-blue-300">Card de Estudo Avançado</h3>

          <div className="mb-4 border border-white/10 bg-black/30 p-4 rounded-sm">
            <p className="text-xs font-bold uppercase tracking-[0.12em] text-gray-400">Análise Direta</p>
            <p className="mt-2 text-sm text-gray-100">{explicacao?.analise_rapida || "-"}</p>
          </div>

          <div className="mb-4 border border-blue-500/40 bg-blue-950/30 p-4 rounded-sm">
            <p className="text-sm font-extrabold uppercase tracking-[0.12em] text-blue-300">Vocabulário C1</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {(explicacao?.nivel_c1 || []).map((item, index) => (
                <span
                  key={`${item}-${index}`}
                  className="border border-blue-400 bg-blue-900/40 px-2.5 py-1 text-xs font-bold text-blue-100 rounded-none"
                >
                  {item}
                </span>
              ))}
              {(!explicacao?.nivel_c1 || explicacao.nivel_c1.length === 0) ? (
                <span className="text-sm text-gray-400">-</span>
              ) : null}
            </div>
          </div>

          <div className="mb-4 border border-purple-500/40 bg-purple-950/30 p-4 rounded-sm">
            <p className="text-sm font-extrabold uppercase tracking-[0.12em] text-purple-300">No Plantão (Nativo)</p>
            <p className="mt-2 text-sm text-purple-100">{explicacao?.variacao_nativa || "-"}</p>
          </div>

          <div className="border border-red-500/40 bg-red-950/25 p-4 rounded-sm">
            <p className="text-sm font-extrabold uppercase tracking-[0.12em] text-red-300">Teste seu Reflexo</p>
            <p className="mt-2 text-sm text-red-100">{explicacao?.desafio_traducao || "-"}</p>

            <div className="mt-3 flex flex-col gap-3 sm:flex-row">
              <input
                type="text"
                value={tentativaDe}
                onChange={(event) => setTentativaDe(event.target.value)}
                placeholder="Digite sua tradução em alemão (C1)..."
                className="w-full bg-[#0f0f14] border border-blue-400/70 text-blue-100 placeholder:text-blue-300/50 px-3 py-2 rounded-none outline-none focus:border-purple-400 focus:shadow-[0_0_0_2px_rgba(168,85,247,0.25)]"
              />
              <button
                type="button"
                onClick={handleEnviarTraducao}
                disabled={!tentativaDe.trim() || avaliando}
                className="bg-purple-600 hover:bg-purple-500 text-white font-bold py-2 px-4 border-b-4 border-purple-800 hover:border-purple-700 active:border-b-0 active:translate-y-[4px] transition-all rounded-none uppercase tracking-wider text-xs disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {avaliando ? "Avaliando..." : "Enviar Tradução"}
              </button>
            </div>

            {resultadoAvaliacao ? (
              <div
                className={`mt-4 border p-3 rounded-sm ${
                  resultadoAvaliacao?.correto
                    ? "border-emerald-400/70 bg-emerald-500/10 shadow-[0_0_16px_rgba(16,185,129,0.25)]"
                    : "border-orange-400/70 bg-orange-500/10 shadow-[0_0_16px_rgba(249,115,22,0.25)]"
                }`}
              >
                <p className={`text-sm font-bold ${resultadoAvaliacao?.correto ? "text-emerald-300" : "text-orange-300"}`}>
                  {resultadoAvaliacao?.correto ? "Tradução aprovada" : "Ajuste necessário"}
                </p>
                <p className="mt-1 text-sm text-gray-100">{resultadoAvaliacao?.feedback_curto || "-"}</p>
                {resultadoAvaliacao?.versao_ideal ? (
                  <p className={`mt-2 text-sm ${resultadoAvaliacao?.correto ? "text-emerald-200" : "text-orange-200"}`}>
                    Versão ideal: {resultadoAvaliacao.versao_ideal}
                  </p>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
