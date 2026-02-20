const API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env && import.meta.env.VITE_API_BASE_URL) ||
  "";

let csrfInitialized = false;

function buildUrl(path) {
  if (!API_BASE_URL) return path;
  return `${API_BASE_URL.replace(/\/$/, "")}${path}`;
}

function getCookie(name) {
  if (typeof document === "undefined") return "";
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift() || "";
  return "";
}

export async function initCsrf() {
  if (csrfInitialized) return;
  await fetch(buildUrl("/api/auth/csrf/"), { credentials: "include" });
  csrfInitialized = true;
}

async function request(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const requiresCsrf = ["POST", "PUT", "PATCH", "DELETE"].includes(method);

  if (requiresCsrf) {
    await initCsrf();
  }

  const csrfToken = getCookie("csrftoken");

  let response;

  try {
    response = await fetch(buildUrl(path), {
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(requiresCsrf && csrfToken ? { "X-CSRFToken": csrfToken } : {}),
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
    if (response.status === 401) {
      throw new Error("Sessão expirada ou não autenticada. Faça login para continuar.");
    }
    const message = data?.detail || "Falha na comunicação com a API.";
    throw new Error(message);
  }

  return data;
}

export async function loginUser(username, password) {
  await initCsrf();
  return request("/api/auth/login/", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function logoutUser() {
  return request("/api/auth/logout/", {
    method: "POST",
  });
}

export async function getCurrentUser() {
  return request("/api/auth/me/", {
    method: "GET",
  });
}

export async function getClinicalScenarios(level = "") {
  const query = level ? `?level=${encodeURIComponent(level)}` : "";
  return request(`/api/scenarios/${query}`, {
    method: "GET",
  });
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

export async function evaluateStudyTranslation(desafioPt, tentativaDe, contextoOriginal = "") {
  return request("/api/study/evaluate/", {
    method: "POST",
    body: JSON.stringify({
      desafio_pt: desafioPt,
      tentativa_de: tentativaDe,
      contexto_original: contextoOriginal,
    }),
  });
}

export async function getDueFlashcards() {
  return request("/api/study/review/", {
    method: "GET",
  });
}

export async function submitFlashcardReview(id, score) {
  return request(`/api/study/review/${id}/`, {
    method: "POST",
    body: JSON.stringify({ score }),
  });
}
