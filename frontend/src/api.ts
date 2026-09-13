/**
 * Thin fetch wrapper around the orchestrator's HTTP API. Kept separate from
 * App.tsx on purpose: when the backend contract changes, this file and
 * @shared/types are the only things that should need to change — not the
 * component tree.
 */
import type {
  ApproveRequest,
  ApproveResponse,
  GenerateRequest,
  GenerateResponse,
  RegenerateRequest,
  RegenerateResponse,
} from "@shared/types";

export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function post<TResponse>(path: string, body: unknown): Promise<TResponse> {
  let res: Response;
  try {
    res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError("Could not reach the backend. Is it running on :8000?");
  }

  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new ApiError(detail || `Request to ${path} failed (${res.status})`, res.status);
  }

  return (await res.json()) as TResponse;
}

export function generatePosts(req: GenerateRequest): Promise<GenerateResponse> {
  return post<GenerateResponse>("/api/generate", req);
}

export function regeneratePost(req: RegenerateRequest): Promise<RegenerateResponse> {
  return post<RegenerateResponse>("/api/regenerate", req);
}

export function approvePost(req: ApproveRequest): Promise<ApproveResponse> {
  return post<ApproveResponse>("/api/approve", req);
}
