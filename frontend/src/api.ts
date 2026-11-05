import type { AskResponse } from "./types";

// Empty in development (Vite proxies /api); set to the backend address when deployed.
const API_URL = import.meta.env.VITE_API_URL ?? "";
// Shared key the backend checks. Only reaches the browser of users who passed the sign-in.
const API_KEY = import.meta.env.VITE_API_KEY ?? "";

export async function askQuestion(question: string): Promise<AskResponse> {
  const response = await fetch(`${API_URL}/api/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": API_KEY },
    body: JSON.stringify({ question }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    throw new Error(typeof detail === "string" ? detail : `Request failed (${response.status})`);
  }
  return response.json();
}
