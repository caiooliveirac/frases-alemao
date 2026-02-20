const API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env && import.meta.env.VITE_API_BASE_URL) ||
  (typeof process !== "undefined" && process.env && process.env.REACT_APP_API_BASE_URL) ||
  "";

function buildUrl(path) {
  if (!API_BASE_URL) return path;
  return `${API_BASE_URL.replace(/\/$/, "")}${path}`;
}

async function request(path, options = {}) {
  let response;

  try {
    response = await fetch(buildUrl(path), {
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      ...options,
    });
  } catch (error) {
    throw new Error("Erro de rede. Verifique sua conexão e tente novamente.");
  }

  let data = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    data = await response.json();
  }

  if (!response.ok) {
    const message = data?.detail || "Falha na comunicação com a API.";
    throw new Error(message);
  }

  return data;
}

export async function createDocument(text, title = "Texto em alemão") {
  return request("/api/documents/", {
    method: "POST",
    body: JSON.stringify({ text, title }),
  });
}

export async function getDocumentById(documentId) {
  return request(`/api/documents/${documentId}/`, {
    method: "GET",
  });
}

export async function generateStudyFlashcard(documentId, wordId) {
  return request("/api/study/generate/", {
    method: "POST",
    body: JSON.stringify({
      document_id: documentId,
      word_id: wordId,
    }),
  });
}
