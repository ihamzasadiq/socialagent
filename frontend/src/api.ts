/**
 * Thin fetch wrapper around the orchestrator's HTTP API. Kept separate from
 * App.tsx on purpose: when the backend contract changes, this file and
 * @shared/types are the only things that should need to change — not the
 * component tree.
 */
import type {
  AddSourceRequest,
  AddSourceResponse,
  ApproveRequest,
  ApproveResponse,
  ClearSessionResponse,
  GenerateRequest,
  GenerateResponse,
  ImageRequest,
  ImageResponse,
  LinkedInStatus,
  OkResponse,
  ReferenceRequest,
  ReferenceResponse,
  RegenerateRequest,
  RegenerateResponse,
  SessionResponse,
  WatermarkRequest,
  WatermarkResponse,
} from "@shared/types";

export class ApiError extends Error {
  status?: number;
  /** Present on the 409 from /api/approve: where to send the browser to connect. */
  connectUrl?: string;

  constructor(message: string, status?: number, connectUrl?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.connectUrl = connectUrl;
  }
}

async function request<TResponse>(path: string, init?: RequestInit): Promise<TResponse> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: init?.body ? { "Content-Type": "application/json" } : undefined,
    });
  } catch {
    throw new ApiError("Could not reach the backend. Is it running on :8000?");
  }

  if (!res.ok) {
    const raw = await res.text().catch(() => "");
    let detail = raw;
    let connectUrl: string | undefined;
    try {
      const parsed = JSON.parse(raw) as { detail?: unknown; connectUrl?: string };
      if (typeof parsed.detail === "string") detail = parsed.detail;
      if (typeof parsed.connectUrl === "string") connectUrl = parsed.connectUrl;
    } catch {
      // non-JSON error body — keep the raw text
    }
    throw new ApiError(detail || `Request to ${path} failed (${res.status})`, res.status, connectUrl);
  }

  if (res.status === 204) return undefined as TResponse;
  return (await res.json()) as TResponse;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export function getSession(): Promise<SessionResponse> {
  return request<SessionResponse>("/api/session");
}

export function clearSession(): Promise<ClearSessionResponse> {
  return post<ClearSessionResponse>("/api/session/clear");
}

export function addSource(req: AddSourceRequest): Promise<AddSourceResponse> {
  return post<AddSourceResponse>("/api/sources", req);
}

export function removeSource(id: string): Promise<OkResponse> {
  return request<OkResponse>(`/api/sources/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export function generatePosts(req: GenerateRequest): Promise<GenerateResponse> {
  return post<GenerateResponse>("/api/generate", req);
}

export function regeneratePost(req: RegenerateRequest): Promise<RegenerateResponse> {
  return post<RegenerateResponse>("/api/regenerate", req);
}

export function generateImage(req: ImageRequest): Promise<ImageResponse> {
  return post<ImageResponse>("/api/image", req);
}

export function setReference(req: ReferenceRequest): Promise<ReferenceResponse> {
  return post<ReferenceResponse>("/api/reference", req);
}

export function clearReference(): Promise<ReferenceResponse> {
  return request<ReferenceResponse>("/api/reference", { method: "DELETE" });
}

export function setWatermark(req: WatermarkRequest): Promise<WatermarkResponse> {
  return post<WatermarkResponse>("/api/watermark", req);
}

export function approvePost(req: ApproveRequest): Promise<ApproveResponse> {
  return post<ApproveResponse>("/api/approve", req);
}

export function getLinkedInStatus(): Promise<LinkedInStatus> {
  return request<LinkedInStatus>("/api/oauth/linkedin/status");
}

export function disconnectLinkedIn(): Promise<OkResponse> {
  return post<OkResponse>("/api/oauth/linkedin/disconnect");
}
