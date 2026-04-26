export const ESG_CHAT_API_BASE =
  process.env.NEXT_PUBLIC_ESG_CHAT_API_BASE?.replace(/\/$/, "") || "http://localhost:8000";

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${ESG_CHAT_API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const raw = await response.text();
    throw new Error(raw || `Request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}
