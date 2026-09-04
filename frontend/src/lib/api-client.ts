/**
 * Cliente API Tipado Unificado para o LegalTech SaaS
 * Oferece retentativas para falhas transitórias e usa a sessão HttpOnly da mesma origem.
 */

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL || "/api/v1").replace(/\/$/, "");
export const API_ORIGIN = /^https?:\/\//.test(API_BASE_URL) ? new URL(API_BASE_URL).origin : "";
export const SESSION_EXPIRED_EVENT = "legalflow:session-expired";
export const SESSION_RESTORED_EVENT = "legalflow:session-restored";
function reportExpiredSession(endpoint: string, status: number) {
  if (status === 401 && typeof window !== "undefined" && !endpoint.startsWith("/auth/") && !endpoint.startsWith("/client-portal")) window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
}

export interface RequestOptions extends RequestInit {
  retries?: number;
  backoffMs?: number;
}

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

async function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function apiClient<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { retries = 2, backoffMs = 500, ...fetchOptions } = options;
  // A failed response does not prove that a write was not committed.
  const retryLimit = ["GET", "HEAD"].includes((fetchOptions.method || "GET").toUpperCase()) ? retries : 0;

  const headers = new Headers(fetchOptions.headers);
  if (!headers.has("Content-Type") && !(fetchOptions.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  let attempt = 0;
  while (attempt <= retryLimit) {
    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...fetchOptions,
        headers,
        credentials: "include",
        cache: "no-store",
      });

      if (!response.ok) {
        reportExpiredSession(endpoint, response.status);
        const errorBody = await response.json().catch(() => ({ detail: response.statusText }));
        throw new ApiError(
          typeof errorBody.detail === "string" ? errorBody.detail : Array.isArray(errorBody.detail)
            ? errorBody.detail.map((item: { loc?: string[]; msg?: string }) => `${item.loc?.slice(1).join(".") || "Campo"}: ${item.msg || "inválido"}`).join("; ")
            : `Erro de servidor (${response.status})`,
          response.status,
          errorBody
        );
      }

      if (response.status === 204 || fetchOptions.method?.toUpperCase() === "HEAD") return undefined as T;
      return (await response.json()) as T;
    } catch (err: any) {
      attempt++;
      if (attempt > retryLimit || fetchOptions.signal?.aborted || (err instanceof ApiError && err.status >= 400 && err.status < 500)) {
        throw err;
      }
      await delay(backoffMs * Math.pow(2, attempt - 1));
    }
  }

  throw new Error("Falha na requisição à API após várias tentativas.");
}

export const api = {
  get: <T>(endpoint: string, options?: RequestOptions) =>
    apiClient<T>(endpoint, { ...options, method: "GET" }),
  post: <T>(endpoint: string, body: any, options?: RequestOptions) =>
    apiClient<T>(endpoint, { ...options, method: "POST", body: JSON.stringify(body) }),
  put: <T>(endpoint: string, body: any, options?: RequestOptions) =>
    apiClient<T>(endpoint, { ...options, method: "PUT", body: JSON.stringify(body) }),
  patch: <T>(endpoint: string, body: any, options?: RequestOptions) =>
    apiClient<T>(endpoint, { ...options, method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(endpoint: string, options?: RequestOptions) =>
    apiClient<T>(endpoint, { ...options, method: "DELETE" }),
};

/** Private PDF/DOCX requests use the same session; writes are never retried automatically. */
export async function apiBlob(endpoint: string, options: RequestInit = {}): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, { ...options, credentials: "include", cache: "no-store" });
  if (!response.ok) {
    reportExpiredSession(endpoint, response.status);
    const body = await response.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail
      : Array.isArray(body.detail) ? body.detail.map((item: { msg?: string }) => item.msg || "Campo inválido").join("; ")
      : `Arquivo indisponível (${response.status}).`;
    throw new ApiError(detail, response.status, body);
  }
  return response.blob();
}
