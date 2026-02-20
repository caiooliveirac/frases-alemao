import React, { useState } from "react";
import { createDocument, getDocumentById } from "./api_client";
import InteractiveReader from "./components/InteractiveReader";

const INITIAL_TEXT =
  "Der Notarzt wurde zu einem schweren Verkehrsunfall gerufen. Der Patient ist bewusstlos und benötigt sofortige Intubation. Wir verabreichen dem Patienten das Narkosemittel.";

export default function App() {
  const [text, setText] = useState(INITIAL_TEXT);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const handleAnalyze = async () => {
    if (!text.trim() || loading) return;

    setLoading(true);
    setError("");

    try {
      const created = await createDocument(text.trim(), "Caso clínico");
      const documentId = created?.document_id;

      if (!documentId) {
        throw new Error("document_id não retornado pela API.");
      }

      const detail = await getDocumentById(documentId);
      setResult(detail);
    } catch (err) {
      setError(err?.message || "Falha ao analisar caso clínico.");
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: 24, fontFamily: "sans-serif" }}>
      <h1>POC - Análise de Caso Clínico (Alemão)</h1>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={9}
        style={{ width: "100%", fontSize: 16, padding: 12, marginTop: 12 }}
      />

      <button
        onClick={handleAnalyze}
        disabled={loading}
        style={{ marginTop: 12, padding: "10px 16px", cursor: loading ? "not-allowed" : "pointer" }}
      >
        {loading ? "Analisando..." : "Analisar Caso Clínico"}
      </button>

      {error ? (
        <div style={{ marginTop: 12, color: "#b91c1c" }}>
          {error}
        </div>
      ) : null}

      {result ? (
        <div style={{ marginTop: 20, padding: 12, border: "1px solid #e5e7eb", borderRadius: 8 }}>
          <h2>Resultado Estruturado</h2>
          <InteractiveReader data={result} />
          <pre style={{ marginTop: 12, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      ) : null}
    </div>
  );
}
