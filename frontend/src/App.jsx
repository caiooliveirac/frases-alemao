import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  analyzePhraseDeep,
  analyzePhraseLite,
  createDocument,
  getClinicalScenarios,
  getCurrentUser,
  getDocumentById,
  getDueFlashcards,
  loginUser,
  logoutUser,
} from "./api_client";
import DailyReview from "./components/DailyReview";
import InteractiveReader from "./components/InteractiveReader";

const FALLBACK_SCENARIOS = [
  "Aufgrund des progredienten Lungenversagens müssen wir den Patienten umgehend stabilisieren.",
  "Trotz maximaler konservativer Therapie bleibt der mittlere arterielle Druck kritisch niedrig.",
  "Angesichts der massiven intrakraniellen Blutung ist eine sofortige neurochirurgische Entlastung unabdingbar.",
];

const ANALYSIS_STATE = {
  IDLE: "idle",
  ANALYZING_LITE: "analyzing_lite",
  LITE_READY: "lite_ready",
  ANALYZING_DEEP: "analyzing_deep",
  DEEP_READY: "deep_ready",
  ERROR: "error",
};

function hashPhrase(phrase) {
  let hash = 0;
  for (let index = 0; index < phrase.length; index += 1) {
    hash = ((hash << 5) - hash) + phrase.charCodeAt(index);
    hash |= 0;
  }
  return `${phrase.length}:${Math.abs(hash)}`;
}

function mapLiteTokens(tokens = []) {
  return tokens.map((token) => ({
    id: token.token_id,
    token_id: token.token_id,
    lemma: token.lemma,
    pos: token.pos,
    gender: token.gender || null,
    word: {
      id: null,
      lemma: token.lemma,
      pos_tag: token.pos,
      gender: token.gender || "X",
    },
  }));
}

function mergeDeepTokens(baseTokens = [], deepTokens = []) {
  const byId = new Map(deepTokens.map((token) => [token.token_id, token]));
  return baseTokens.map((token) => {
    const deep = byId.get(token.token_id || token.id);
    if (!deep) return token;

    return {
      ...token,
      surface: deep.surface,
      lemma: deep.lemma,
      pos: deep.pos,
      gender: deep.gender,
      case: deep.case,
      syntactic_role: deep.syntactic_role,
      confidence: deep.confidence,
      grammatical_case: deep.case,
      word: {
        ...(token.word || {}),
        lemma: deep.lemma,
        pos_tag: deep.pos,
        gender: deep.gender || token?.word?.gender || "X",
      },
    };
  });
}

function mergeWordIds(baseTokens = [], detailTokens = []) {
  const byRelationId = new Map(detailTokens.map((token) => [token.id, token]));
  return baseTokens.map((token) => {
    const relation = byRelationId.get(token.token_id || token.id);
    if (!relation) return token;

    return {
      ...token,
      word_token_id: relation?.word?.id || null,
      word: {
        ...(token.word || {}),
        id: relation?.word?.id || null,
        lemma: relation?.word?.lemma || token?.word?.lemma || token.lemma,
        pos_tag: relation?.word?.pos_tag || token?.word?.pos_tag || token.pos,
        gender: relation?.word?.gender || token?.word?.gender || token.gender || "X",
      },
    };
  });
}

function getRandomScenario(items = [], excludeText = "") {
  if (!items.length) return "";
  if (items.length === 1) return items[0];

  let next = items[Math.floor(Math.random() * items.length)];
  while (next === excludeText) {
    next = items[Math.floor(Math.random() * items.length)];
  }
  return next;
}

export default function App() {
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [authError, setAuthError] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [scenarioItems, setScenarioItems] = useState([]);
  const [selectedLevel, setSelectedLevel] = useState("C1");
  const [text, setText] = useState(() => getRandomScenario(FALLBACK_SCENARIOS));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [analysisState, setAnalysisState] = useState(ANALYSIS_STATE.IDLE);
  const [reviewMode, setReviewMode] = useState(false);
  const [dueCards, setDueCards] = useState([]);
  const [dueLoading, setDueLoading] = useState(false);
  const [dueError, setDueError] = useState("");
  const activeAnalysisRef = useRef(0);
  const activePhraseHashRef = useRef("");

  const scenarioTexts = useMemo(() => scenarioItems.map((item) => item.text), [scenarioItems]);

  const loadScenarios = async (level = "") => {
    const payload = await getClinicalScenarios(level);
    const items = payload?.items || [];
    const effectiveLevel = payload?.selected_level || payload?.proficiency_level || level || "C1";
    setScenarioItems(items);
    setSelectedLevel(effectiveLevel);
    const random = getRandomScenario(items.map((item) => item.text));
    setText(random || "");
  };

  const loadDueCards = async () => {
    setDueLoading(true);
    setDueError("");
    try {
      const cards = await getDueFlashcards();
      setDueCards(cards || []);
    } catch (err) {
      setDueError(err?.message || "Falha ao carregar cards pendentes.");
      setDueCards([]);
    } finally {
      setDueLoading(false);
    }
  };

  useEffect(() => {
    const bootstrap = async () => {
      try {
        const current = await getCurrentUser();
        setUser(current);
        setAuthLoading(false);
        Promise.all([loadScenarios(current?.proficiency_level || ""), loadDueCards()]).catch(() => {
          // mantém UI responsiva mesmo se algum carregamento inicial falhar
        });
      } catch {
        setUser(null);
        setAuthLoading(false);
      }
    };

    bootstrap();
  }, []);

  const handleLogin = async (event) => {
    event.preventDefault();
    if (!username.trim() || !password) return;
    setAuthError("");
    setAuthLoading(true);

    try {
      const logged = await loginUser(username.trim(), password);
      setUser(logged);
      setAuthLoading(false);
      Promise.all([loadScenarios(logged?.proficiency_level || ""), loadDueCards()]).catch(() => {
        // mantém login rápido; erros de carregamento aparecem nos fluxos específicos
      });
      setPassword("");
    } catch (err) {
      setAuthError(err?.message || "Falha no login.");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await logoutUser();
    } catch {
      // noop
    }
    setUser(null);
    setResult(null);
    setDueCards([]);
    setScenarioItems([]);
    setText("");
  };

  if (authLoading) {
    return (
      <main className="px-4 pb-12 pt-10">
        <div className="border-2 border-gray-700 bg-[#1a1a1a] p-8 shadow-[8px_8px_0_#333] max-w-xl mx-auto mt-10">
          <p className="text-gray-200">Carregando sessão...</p>
        </div>
      </main>
    );
  }

  if (!user) {
    return (
      <main className="px-4 pb-12 pt-10">
        <div className="border-2 border-gray-700 bg-[#1a1a1a] p-8 shadow-[8px_8px_0_#333] max-w-xl mx-auto mt-10">
          <h1 className="text-2xl font-black uppercase tracking-[0.16em] text-blue-300">Login Obrigatório</h1>
          <p className="mt-2 text-sm text-gray-400">A aplicação exige sessão autenticada para proteger o consumo da API.</p>

          <form className="mt-6 space-y-3" onSubmit={handleLogin}>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Usuário"
              className="w-full bg-[#111111] border-2 border-gray-300 text-gray-100 p-3 rounded-none outline-none focus:border-blue-400"
            />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Senha"
              className="w-full bg-[#111111] border-2 border-gray-300 text-gray-100 p-3 rounded-none outline-none focus:border-blue-400"
            />

            {authError ? (
              <div className="border-2 border-red-500 bg-red-950/40 px-4 py-3 text-red-200 rounded-sm">{authError}</div>
            ) : null}

            <button
              type="submit"
              className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 px-6 border-b-4 border-blue-800 hover:border-blue-700 active:border-b-0 active:translate-y-[4px] transition-all rounded-none uppercase tracking-widest"
            >
              Entrar
            </button>
          </form>
        </div>
      </main>
    );
  }

  const handleRollScenario = () => {
    const next = getRandomScenario(scenarioTexts, text);
    setText(next);
    setResult(null);
    setAnalysisState(ANALYSIS_STATE.IDLE);
    setError("");
  };

  const handleLevelChange = async (event) => {
    const level = event.target.value;
    setError("");
    setResult(null);
    setAnalysisState(ANALYSIS_STATE.IDLE);
    try {
      await loadScenarios(level);
    } catch (err) {
      setError(err?.message || "Falha ao carregar frases para o nível selecionado.");
    }
  };

  const handleAnalyze = async () => {
    if (!text.trim() || loading) return;

    const phrase = text.trim();
    const phraseHash = hashPhrase(phrase);
    const analysisId = activeAnalysisRef.current + 1;
    activeAnalysisRef.current = analysisId;
    activePhraseHashRef.current = phraseHash;

    setLoading(true);
    setError("");
    setAnalysisState(ANALYSIS_STATE.ANALYZING_LITE);
    setResult(null);

    try {
      const created = await createDocument(phrase, "Caso clínico");
      const documentId = created?.document_id;

      if (!documentId) {
        throw new Error("document_id não retornado pela API.");
      }

      if (analysisId !== activeAnalysisRef.current || phraseHash !== activePhraseHashRef.current) {
        return;
      }

      const lite = await analyzePhraseLite(documentId, 20);

      if (analysisId !== activeAnalysisRef.current || phraseHash !== activePhraseHashRef.current) {
        return;
      }

      setResult({
        document_id: documentId,
        phrase_hash: phraseHash,
        tokens: mapLiteTokens(lite?.tokens || []),
      });
      setAnalysisState(ANALYSIS_STATE.LITE_READY);
      setLoading(false);

      setAnalysisState(ANALYSIS_STATE.ANALYZING_DEEP);
      const [deepResult, detailResult] = await Promise.allSettled([
        analyzePhraseDeep(documentId, 20),
        getDocumentById(documentId),
      ]);

      if (analysisId !== activeAnalysisRef.current || phraseHash !== activePhraseHashRef.current) {
        return;
      }

      setResult((previous) => {
        if (!previous || previous?.phrase_hash !== phraseHash) return previous;

        let mergedTokens = previous.tokens || [];
        if (detailResult.status === "fulfilled") {
          mergedTokens = mergeWordIds(mergedTokens, detailResult.value?.tokens || []);
        }
        if (deepResult.status === "fulfilled") {
          mergedTokens = mergeDeepTokens(mergedTokens, deepResult.value?.tokens || []);
        }

        return {
          ...previous,
          document: detailResult.status === "fulfilled" ? detailResult.value?.document : previous.document,
          tokens: mergedTokens,
        };
      });

      if (deepResult.status === "fulfilled") {
        setAnalysisState(ANALYSIS_STATE.DEEP_READY);
      } else {
        setAnalysisState(ANALYSIS_STATE.ERROR);
        const deepError = deepResult.reason?.message || "Falha ao carregar análise detalhada.";
        setError(deepError);
      }
    } catch (err) {
      setError(err?.message || "Falha ao analisar caso clínico.");
      setAnalysisState(ANALYSIS_STATE.ERROR);
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const handleTextChange = (event) => {
    const nextText = event.target.value;
    const nextHash = hashPhrase(nextText.trim());
    setText(nextText);

    activePhraseHashRef.current = nextHash;
    activeAnalysisRef.current += 1;

    setResult((previous) => {
      if (!previous) return previous;
      if (previous.phrase_hash === nextHash) return previous;
      return null;
    });

    setError("");
    setAnalysisState(ANALYSIS_STATE.IDLE);
  };

  const handleStartDailyReview = async () => {
    await loadDueCards();
    setReviewMode(true);
  };

  const handleExitReview = async () => {
    setReviewMode(false);
    await loadDueCards();
  };

  const handleReviewProgress = (nextIndex) => {
    const pending = Math.max((dueCards?.length || 0) - nextIndex, 0);
    if (pending >= 0) {
      setDueCards((prev) => prev.slice(nextIndex));
    }
  };

  return (
    <main className="px-4 pb-12 pt-10">
      <div className="border-2 border-gray-700 bg-[#1a1a1a] p-8 shadow-[8px_8px_0_#333] max-w-4xl mx-auto mt-10">
        <button
          type="button"
          onClick={handleStartDailyReview}
          disabled={dueLoading}
          className="mb-4 w-full bg-emerald-700 hover:bg-emerald-600 text-white font-bold py-3 px-6 border-b-4 border-emerald-900 hover:border-emerald-800 active:border-b-0 active:translate-y-[4px] transition-all rounded-none uppercase tracking-widest disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {dueLoading
            ? "Carregando treino diário..."
            : `🧠 Iniciar Treino Diário (${dueCards.length} cards pendentes)`}
        </button>

        <h1 className="text-3xl font-black uppercase tracking-[0.18em] text-blue-300">
          POC // Klinik Deutsch Engine
        </h1>
        <p className="mt-2 text-sm text-gray-400 tracking-wide">
          Sessão ativa: {user.username} • Nível {user.proficiency_level}
        </p>
        <div className="mt-3 flex items-center gap-3">
          <label htmlFor="level-select" className="text-xs font-bold uppercase tracking-wider text-gray-400">
            Roleta
          </label>
          <select
            id="level-select"
            value={selectedLevel}
            onChange={handleLevelChange}
            className="bg-[#111111] border-2 border-gray-300 text-gray-100 px-3 py-2 rounded-none outline-none focus:border-blue-400 text-xs font-bold tracking-wider"
          >
            <option value="A1">Modo A1</option>
            <option value="B1">Modo B1</option>
            <option value="C1">Modo C1</option>
          </select>
          <span className="text-xs text-gray-500">(flashcards continuam no seu usuário)</span>
        </div>
        <button
          type="button"
          onClick={handleLogout}
          className="mt-3 bg-gray-700 hover:bg-gray-600 text-white font-bold py-2 px-4 border-b-4 border-gray-900 hover:border-gray-800 active:border-b-0 active:translate-y-[4px] transition-all rounded-none uppercase tracking-wider text-xs"
        >
          Sair
        </button>

        {dueError ? (
          <div className="mt-3 border-2 border-red-500 bg-red-950/40 px-4 py-3 text-red-200 shadow-[4px_4px_0_#7f1d1d] rounded-sm">
            {dueError}
          </div>
        ) : null}

        {reviewMode ? (
          <>
            <div className="mt-4">
              <button
                type="button"
                onClick={handleExitReview}
                className="bg-gray-700 hover:bg-gray-600 text-white font-bold py-2 px-4 border-b-4 border-gray-900 hover:border-gray-800 active:border-b-0 active:translate-y-[4px] transition-all rounded-none uppercase tracking-wider text-xs"
              >
                ← Voltar para Roleta de Casos
              </button>
            </div>

            <DailyReview
              cards={dueCards}
              onProgress={handleReviewProgress}
              onFinish={handleExitReview}
            />
          </>
        ) : (
          <>

            <textarea
              value={text}
              onChange={handleTextChange}
              rows={9}
              placeholder="Nenhum cenário disponível para este usuário."
              className="mt-6 w-full bg-[#111111] border-2 border-gray-300 text-gray-100 p-4 font-mono text-[15px] leading-7 rounded-none outline-none focus:border-blue-400 shadow-[6px_6px_0_#2a2a2a]"
            />

            <div className="mt-5 flex flex-wrap gap-3">
              <button
                onClick={handleAnalyze}
                disabled={loading}
                className="bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 px-6 border-b-4 border-blue-800 hover:border-blue-700 active:border-b-0 active:translate-y-[4px] transition-all rounded-none uppercase tracking-widest disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {loading ? "Analisando..." : "Analisar Caso Clínico"}
              </button>

              <button
                type="button"
                onClick={handleRollScenario}
                disabled={loading || !scenarioTexts.length}
                className="bg-purple-700 hover:bg-purple-600 text-white font-bold py-3 px-4 border-b-4 border-purple-900 hover:border-purple-800 active:border-b-0 active:translate-y-[4px] transition-all rounded-none uppercase tracking-wide text-xs disabled:opacity-60 disabled:cursor-not-allowed"
              >
                🎲 Sortear Novo Caso
              </button>
            </div>

            {error ? (
              <div className="mt-4 border-2 border-red-500 bg-red-950/40 px-4 py-3 text-red-200 shadow-[4px_4px_0_#7f1d1d] rounded-sm">
                {error}
              </div>
            ) : null}

            {result ? (
              <section className="mt-8 border border-gray-700 bg-[#151515] p-5 shadow-[6px_6px_0_#2b2b2b] rounded-sm">
                <h2 className="text-xl font-extrabold uppercase tracking-[0.14em] text-purple-300">
                  Leitura Interativa
                </h2>
                <InteractiveReader data={result} analysisState={analysisState} />
              </section>
            ) : null}
          </>
        )}
      </div>
    </main>
  );
}
