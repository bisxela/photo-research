export function getApiBaseUrl() {
  if (process.env.NEXT_PUBLIC_API_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_BASE_URL;
  }

  if (typeof window !== "undefined") {
    const protocol = window.location.protocol === "https:" ? "https:" : "http:";
    const hostname = window.location.hostname || "localhost";
    return `${protocol}//${hostname}:8000`;
  }

  return "http://localhost:8000";
}

export function resolveBackendAssetUrl(path) {
  if (!path) {
    return "";
  }

  return `${getApiBaseUrl()}${path}`;
}

function buildAuthHeaders(token, extraHeaders = {}) {
  return {
    ...extraHeaders,
    Authorization: `Bearer ${token}`,
  };
}

export async function checkHealth() {
  return requestJson(`${getApiBaseUrl()}/health`);
}

export async function register(username, password) {
  return requestJson(`${getApiBaseUrl()}/api/v1/auth/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ username, password }),
  });
}

export async function login(username, password) {
  return requestJson(`${getApiBaseUrl()}/api/v1/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ username, password }),
  });
}

export async function getCurrentUser(token) {
  return requestJson(`${getApiBaseUrl()}/api/v1/auth/me`, {
    headers: buildAuthHeaders(token),
  });
}

export async function searchImages(token, query, topK = 12, searchType = "semantic") {
  return requestJson(`${getApiBaseUrl()}/api/v1/search/text`, {
    method: "POST",
    headers: buildAuthHeaders(token, {
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({ query, top_k: topK, search_type: searchType }),
  });
}

export async function searchSimilarImages(token, imageId, topK = 12) {
  return requestJson(`${getApiBaseUrl()}/api/v1/search/similar`, {
    method: "POST",
    headers: buildAuthHeaders(token, {
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({ image_id: imageId, top_k: topK }),
  });
}

export async function uploadImage(token, file) {
  const formData = new FormData();
  formData.append("file", file);

  return requestJson(`${getApiBaseUrl()}/api/v1/images/upload`, {
    method: "POST",
    headers: buildAuthHeaders(token),
    body: formData,
  });
}

export async function uploadImages(token, files) {
  const formData = new FormData();

  for (const file of files) {
    formData.append("files", file);
  }

  return requestJson(`${getApiBaseUrl()}/api/v1/images/batch-upload`, {
    method: "POST",
    headers: buildAuthHeaders(token),
    body: formData,
  });
}

export async function getImage(token, imageId) {
  return requestJson(`${getApiBaseUrl()}/api/v1/images/${imageId}`, {
    headers: buildAuthHeaders(token),
  });
}

export async function listImages(token) {
  return requestJson(`${getApiBaseUrl()}/api/v1/images`, {
    headers: buildAuthHeaders(token),
  });
}

export async function getImageOcr(token, imageId) {
  return requestJson(`${getApiBaseUrl()}/api/v1/images/${imageId}/ocr`, {
    headers: buildAuthHeaders(token),
  });
}

export async function saveImageOcr(token, imageId, text, language = "chi_sim+eng", source = "client_tesseract") {
  return requestJson(`${getApiBaseUrl()}/api/v1/images/${imageId}/ocr`, {
    method: "PUT",
    headers: buildAuthHeaders(token, {
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({ text, language, source }),
  });
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);

  if (!response.ok) {
    let message = `HTTP ${response.status}`;

    try {
      const errorData = await response.json();
      message = errorData.detail || errorData.message || message;
    } catch {
      message = response.statusText || message;
    }

    throw new Error(message);
  }

  return response.json();
}
