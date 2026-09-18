const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function postFiles(path, files) {
  const form = new FormData();
  for (const f of files) form.append("files", f);

  const res = await fetch(`${BASE_URL}${path}`, { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export async function getStatus() {
  const res = await fetch(`${BASE_URL}/api/status`);
  if (!res.ok) throw new Error("Could not reach the backend");
  return res.json();
}

export const predictDoor = (files) => postFiles("/api/door/predict", files);
export const predictAcv = (files) => postFiles("/api/acv/predict", files);
export const predictRail = (files) => postFiles("/api/rail/predict", files);

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
