const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function fetchApi(endpoint: string, options: RequestInit = {}) {
  const defaultHeaders = {
    "Content-Type": "application/json",
    "X-Tenant-ID": "default-tenant",
  };

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: "Erro desconhecido na API." }));
    throw new Error(errorData.detail || "Falha na comunicacao com o servidor.");
  }

  return response.json();
}
