const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function checkHealth() {
  return requestJson(`${API_BASE_URL}/health`);
}

export async function searchImages(query, topK = 12) {
  return requestJson(`${API_BASE_URL}/api/v1/search/text`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ query, top_k: topK }),
  });
}

export async function searchSimilarImages(imageId, topK = 12) {
  return requestJson(`${API_BASE_URL}/api/v1/search/similar`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ image_id: imageId, top_k: topK }),
  });
}

export async function uploadImage(file) {
  const formData = new FormData();
  formData.append("file", file);

  return requestJson(`${API_BASE_URL}/api/v1/images/upload`, {
    method: "POST",
    body: formData,
  });
}

export async function uploadImages(files) {
  const formData = new FormData();

  for (const file of files) {
    formData.append("files", file);
  }

  return requestJson(`${API_BASE_URL}/api/v1/images/batch-upload`, {
    method: "POST",
    body: formData,
  });
}

export async function getImage(imageId) {
  return requestJson(`${API_BASE_URL}/api/v1/images/${imageId}`);
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
