const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const TOKEN = import.meta.env.VITE_API_TOKEN || "";

const headers = () => ({
  Authorization: `Bearer ${TOKEN}`,
  "Content-Type": "application/json",
});

async function apiFetch(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: { ...headers(), ...(options.headers || {}) },
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

export const fetchSummary = () => apiFetch("/summary");
export const fetchSleep = (days = 30) => apiFetch(`/sleep?days=${days}`);
export const fetchRecovery = (days = 30) => apiFetch(`/recovery?days=${days}`);
export const fetchWorkouts = (days = 30) => apiFetch(`/workouts?days=${days}`);
export const fetchCycles = (days = 30) => apiFetch(`/cycles?days=${days}`);
export const fetchJournal = (days = 30) => apiFetch(`/journal?days=${days}`);

export const postJournal = (date, entry) =>
  apiFetch(`/journal/${date}`, {
    method: "POST",
    body: JSON.stringify(entry),
  });
