import React, { useCallback, useMemo, useState } from "react";
import StudyPanel from "./StudyPanel";

function getRawText(processedText) {
  return processedText?.rawText || processedText?.raw_text || processedText?.text || "";
}

function buildSegmentsFromOffsets(rawText, tokens) {
  const ordered = [...tokens]
    .filter((token) => Number.isInteger(token.start) && Number.isInteger(token.end))
    .sort((a, b) => a.start - b.start);

  if (!ordered.length) return null;

  const segments = [];
  let cursor = 0;

  for (let index = 0; index < ordered.length; index += 1) {
    const token = ordered[index];
    if (token.start > cursor) {
      segments.push({ type: "text", value: rawText.slice(cursor, token.start) });
    }

    segments.push({
      type: "token",
      value: rawText.slice(token.start, token.end),
      tokenIndex: index,
    });
    cursor = token.end;
  }

  if (cursor < rawText.length) {
    segments.push({ type: "text", value: rawText.slice(cursor) });
  }

  return { orderedTokens: ordered, segments };
}

function buildSegmentsByWordOrder(rawText, tokens) {
  const orderedTokens = [...tokens];
  const segments = [];
  const wordRegex = /\p{L}[\p{L}\p{M}'’-]*/gu;
  let cursor = 0;
  let tokenCursor = 0;
  let match = wordRegex.exec(rawText);

  while (match) {
    const start = match.index;
    const end = start + match[0].length;

    if (start > cursor) {
      segments.push({ type: "text", value: rawText.slice(cursor, start) });
    }

    const currentToken = orderedTokens[tokenCursor] || null;
    if (currentToken) {
      segments.push({
        type: "token",
        value: match[0],
        tokenIndex: tokenCursor,
      });
      tokenCursor += 1;
    } else {
      segments.push({ type: "text", value: match[0] });
    }

    cursor = end;
    match = wordRegex.exec(rawText);
  }

  if (cursor < rawText.length) {
    segments.push({ type: "text", value: rawText.slice(cursor) });
  }

  return { orderedTokens, segments };
}

function normalizeToken(rawToken) {
  return {
    ...rawToken,
    lemma: rawToken.lemma || "",
    translation: rawToken.translation || rawToken.translation_ptbr || "",
    grammaticalCase: rawToken.grammaticalCase || rawToken.grammatical_case || "",
    isUnknown:
      Boolean(rawToken.isUnknown) ||
      rawToken.retentionLevel === 0 ||
      rawToken.retention_level === 0 ||
      Boolean(rawToken.is_due),
  };
}

export default function InteractiveReader({
  processedText,
  onGenerateFlashcard,
  studyPlanEndpoint = "/api/learning-engine/study-plan/",
  className = "",
}) {
  const [selectedToken, setSelectedToken] = useState(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState("");

  const rawText = getRawText(processedText);
  const documentId = processedText?.documentId || processedText?.document_id;

  const tokens = useMemo(
    () => (processedText?.tokens || []).map((token) => normalizeToken(token)),
    [processedText]
  );

  const structuredText = useMemo(() => {
    const byOffsets = buildSegmentsFromOffsets(rawText, tokens);
    if (byOffsets) return byOffsets;
    return buildSegmentsByWordOrder(rawText, tokens);
  }, [rawText, tokens]);

  const orderedTokens = structuredText.orderedTokens;
  const segments = structuredText.segments;

  const handleTextClick = useCallback(
    (event) => {
      const target = event.target.closest("[data-token-index]");
      if (!target) return;

      const tokenIndex = Number(target.getAttribute("data-token-index"));
      const token = orderedTokens[tokenIndex];
      if (!token) return;

      setSelectedToken(token);
      setPanelOpen(true);
      setError("");
    },
    [orderedTokens]
  );

  const handleClosePanel = useCallback(() => {
    setPanelOpen(false);
  }, []);

  const handleGenerateFlashcard = useCallback(async () => {
    if (!selectedToken || !documentId || isGenerating) return;

    setIsGenerating(true);
    setError("");

    try {
      if (typeof onGenerateFlashcard === "function") {
        await onGenerateFlashcard({ token: selectedToken, documentId });
      } else {
        const response = await fetch(studyPlanEndpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            document_id: documentId,
            focus_word_token_id: selectedToken.wordTokenId || selectedToken.word_token_id || selectedToken.id,
          }),
        });

        if (!response.ok) {
          throw new Error("Falha ao gerar flashcard dinâmico.");
        }
      }
    } catch (apiError) {
      setError(apiError?.message || "Erro inesperado ao gerar flashcard.");
    } finally {
      setIsGenerating(false);
    }
  }, [documentId, isGenerating, onGenerateFlashcard, selectedToken, studyPlanEndpoint]);

  return (
    <section className={`relative ${className}`}>
      <div
        className="rounded-lg border border-slate-200 bg-white p-5 text-lg leading-8 text-slate-800"
        onClick={handleTextClick}
      >
        {segments.map((segment, index) => {
          if (segment.type === "text") {
            return <span key={`txt-${index}`}>{segment.value}</span>;
          }

          const token = orderedTokens[segment.tokenIndex];
          const underlineClass = token?.isUnknown
            ? "underline decoration-1 decoration-dotted decoration-slate-400 underline-offset-4"
            : "";

          return (
            <span
              key={`tok-${index}`}
              role="button"
              tabIndex={0}
              data-token-index={segment.tokenIndex}
              className={`cursor-pointer rounded-sm px-0.5 transition hover:bg-slate-100 focus:bg-slate-100 focus:outline-none ${underlineClass}`}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  event.currentTarget.click();
                }
              }}
            >
              {segment.value}
            </span>
          );
        })}
      </div>

      <StudyPanel
        isOpen={panelOpen}
        token={selectedToken}
        isGenerating={isGenerating}
        error={error}
        onClose={handleClosePanel}
        onGenerateFlashcard={handleGenerateFlashcard}
      />
    </section>
  );
}