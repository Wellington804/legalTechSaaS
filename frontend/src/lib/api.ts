import { apiClient } from "./api-client";

export async function fetchApi(endpoint: string, options: RequestInit = {}) {
  return apiClient<any>(endpoint, options);
}
