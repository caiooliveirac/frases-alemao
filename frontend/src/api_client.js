const API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env && import.meta.env.VITE_API_BASE_URL) ||
  (typeof import.meta !== "undefined" && import.meta.env && import.meta.env.PROD ? "/frases" : "") ||
  "";

const REQUEST_TIMEOUT_MS = 20000;
const MAX_RETRIES_SAFE = 2;
const RETRYABLE_STATUS = new Set([408, 429, 500, 502, 503, 504]);

let csrfInitialized = false;
let csrfInitPromise = null;

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
  if (!csrfInitPromise) {
    csrfInitPromise = fetch(buildUrl("/api/auth/csrf/"), {
      credentials: "include",
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    })
      .then(() => {
        csrfInitialized = true;
      })
      .finally(() => {
        csrfInitPromise = null;
      });
  }

  await csrfInitPromise;
}

function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function isTimeoutError(error) {
  return error?.name === "TimeoutError" || error?.name === "AbortError";
}

function buildNetworkErrorMessage(error) {
  if (isTimeoutError(error)) {
    return "A API demorou demais para responder. Tente novamente em instantes.";
  }
  return "Erro de rede. Verifique sua conexão e tente novamente.";
}

function shouldRetry(method, attempt, error, response) {
  const safeMethod = ["GET", "HEAD", "OPTIONS"].includes(method);
  if (!safeMethod || attempt >= MAX_RETRIES_SAFE) return false;

  if (error) return true;
  if (response && RETRYABLE_STATUS.has(response.status)) return true;
  return false;
}

async function request(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const requiresCsrf = ["POST", "PUT", "PATCH", "DELETE"].includes(method);

  if (requiresCsrf) {
    await initCsrf();
  }

  const csrfToken = getCookie("csrftoken");
  const defaultHeaders = {
    "Content-Type": "application/json",
    ...(requiresCsrf && csrfToken ? { "X-CSRFToken": csrfToken } : {}),
    ...(options.headers || {}),
  };

  for (let attempt = 0; ; attempt += 1) {
    let response;

    try {
      response = await fetch(buildUrl(path), {
        credentials: "include",
        headers: defaultHeaders,
        ...options,
        signal: options.signal || AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });
    } catch (error) {
      if (shouldRetry(method, attempt, error, null)) {
        await sleep(300 * (attempt + 1));
        continue;
      }
      throw new Error(buildNetworkErrorMessage(error));
    }

    if (shouldRetry(method, attempt, null, response)) {
      await sleep(300 * (attempt + 1));
      continue;
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
      if (response.status === 429) {
        throw new Error("Muitas requisições em sequência. Aguarde alguns segundos e tente novamente.");
      }
      if (response.status === 503 || response.status === 504) {
        throw new Error("Servidor temporariamente indisponível. Tente novamente em instantes.");
      }

      const message = data?.detail || "Falha na comunicação com a API.";
      throw new Error(message);
    }

    return data;
  }
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

export async function analyzePhraseLite(documentId, limit = 20) {
  return request("/api/analyze_lite", {
    method: "POST",
    body: JSON.stringify({
      document_id: documentId,
      limit,
    }),
  });
}

export async function analyzePhraseDeep(documentId, limit = 20) {
  return request("/api/analyze_deep", {
    method: "POST",
    body: JSON.stringify({
      document_id: documentId,
      limit,
    }),
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
