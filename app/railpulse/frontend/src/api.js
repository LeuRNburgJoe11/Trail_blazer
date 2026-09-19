const BASE_URL = import.meta.env.VITE_API_URL || "";

async function jsonResponse(res) {
  if (!res.headers.get("content-type")?.includes("application/json")) {
    throw new Error(
      "The API returned a webpage instead of JSON. Restart the dashboard frontend and backend; check the /api proxy.",
    );
  }
  const value = await res.json();
  if (!res.ok)
    throw new Error(
      typeof value.detail === "string"
        ? value.detail
        : `Request failed (${res.status})`,
    );
  return value;
}

export const assistantContext = () =>
  fetch(`${BASE_URL}/api/assistant/context`).then(jsonResponse);
export const askAssistant = (body, signal) =>
  fetch(`${BASE_URL}/api/assistant/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  }).then(jsonResponse);

async function postFiles(path, files) {
  const form = new FormData();
  for (const f of files) form.append("files", f);

  const res = await fetch(`${BASE_URL}${path}`, { method: "POST", body: form });
  return jsonResponse(res);
}

export async function getStatus() {
  const res = await fetch(`${BASE_URL}/api/status`);
  return jsonResponse(res);
}

export const predictDoor = (files) => postFiles("/api/door/predict", files);
export const predictAcv = (files) => postFiles("/api/acv/predict", files);
export const predictRail = (files) => postFiles("/api/rail/predict", files);
export const predictShm = (files) => postFiles("/api/shm/predict", files);

export function downloadCsv(filename, csvText) {
  const blob = new Blob([csvText], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
