import React from "react";

export default function InteractiveReader({ data }) {
  const tokens = data?.tokens || [];

  if (!tokens.length) {
    return <div>Nenhum token disponível.</div>;
  }

  return (
    <div style={{ lineHeight: 2 }}>
      {tokens.map((token) => {
        const lemma = token?.word?.lemma || "";
        const posTag = token?.word?.pos_tag || "";
        const label = token?.surface_form || token?.word?.lemma || lemma || "[token]";

        return (
          <span
            key={token.id}
            title={`lemma: ${lemma} | pos_tag: ${posTag}`}
            style={{
              display: "inline-block",
              marginRight: 6,
              marginBottom: 6,
              padding: "2px 6px",
              border: "1px solid #d1d5db",
              borderRadius: 6,
            }}
          >
            {label}
          </span>
        );
      })}
    </div>
  );
}
