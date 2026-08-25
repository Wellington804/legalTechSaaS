/**
 * Cliente API Tipado Unificado para o LegalTech SaaS
 * Oferece suporte a retentativas automáticas (exponential backoff), injeção de Tenant ID e Bearer Token.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export interface RequestOptions extends RequestInit {
  retries?: number;
  backoffMs?: number;
  tenantId?: string;
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
  const { retries = 2, backoffMs = 500, tenantId = "tenant_rossi_01", ...fetchOptions } = options;

  const getAuthToken = () => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("access_token") || "";
    }
    return "";
  };

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Tenant-ID": tenantId,
    ...(getAuthToken() ? { Authorization: `Bearer ${getAuthToken()}` } : {}),
    ...(fetchOptions.headers as Record<string, string>),
  };

  let attempt = 0;
  while (attempt <= retries) {
    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...fetchOptions,
        headers,
      });

      if (!response.ok) {
        const errorBody = await response.json().catch(() => ({ detail: response.statusText }));
        throw new ApiError(
          errorBody.detail || `Erro de servidor (${response.status})`,
          response.status,
          errorBody
        );
      }

      return (await response.json()) as T;
    } catch (err: any) {
      attempt++;
      if (attempt > retries || (err instanceof ApiError && err.status >= 400 && err.status < 500)) {
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
  delete: <T>(endpoint: string, options?: RequestOptions) =>
    apiClient<T>(endpoint, { ...options, method: "DELETE" }),
};
