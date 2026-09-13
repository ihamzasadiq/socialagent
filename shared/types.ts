/**
 * Canonical wire contract between /frontend and /backend.
 *
 * This file is the single source of truth. The Python backend can't import
 * TypeScript, so backend/orchestrator/schemas.py hand-mirrors every shape
 * here field-for-field (see the mapping table in that file's docstring).
 * If you add or rename a field here, update schemas.py in the same change.
 *
 * Wire format is camelCase JSON (matches these field names exactly) — the
 * backend's Pydantic models translate to/from snake_case internally via an
 * alias generator, so Python code stays idiomatic without breaking the wire
 * format.
 *
 * There is no database. The backend keeps ONE in-memory session (sources,
 * posts, generated media, LinkedIn connection). The frontend rehydrates from
 * GET /api/session on load and can wipe everything with POST /api/session/clear.
 */

/**
 * Only LinkedIn is fully wired today; Instagram is generated-when-enabled but
 * has no publish path yet, so the UI only shows LinkedIn.
 */
export type PlatformId = "linkedin" | "instagram";

export type TemplateId = "funding" | "acquisition" | "launch" | "custom";

export type PostStatus = "preview" | "posted";

export type SourceStatus = "loading" | "ready" | "error";

export type ImageStatus = "none" | "generating" | "ready" | "error";

export type ImageRatio = "1:1" | "4:5" | "16:9";

export type ImageStyle = "modern" | "editorial" | "minimal";

/** A source URL plus the context extracted from it. */
export interface Source {
  id: string;
  url: string;
  host: string;
  title: string;
  path: string;
  status: SourceStatus;
  error?: string | null;
  /** True once the optional vision pass has described the page images. */
  deep: boolean;
}

/**
 * A single platform's draft. `variantIndex` is server-owned (the session
 * remembers where in the variant rotation each post is). `imageUrl` points at
 * the backend's /media mount once an image has been generated.
 */
export interface Post {
  id: string;
  platform: PlatformId;
  text: string;
  status: PostStatus;
  headline: string;
  subhead: string;
  hashtags: string[];
  altText: string;
  imagePrompt: string;
  imageUrl?: string | null;
  imageStatus: ImageStatus;
  imageError?: string | null;
  variantIndex: number;
}

/** The result of one generation pass. */
export interface PostBundle {
  id: string;
  templateId: TemplateId;
  posts: Post[];
  createdAt: string; // ISO 8601
}

/* -------------------------------- sources -------------------------------- */

export interface AddSourceRequest {
  url: string;
  /** Run the slower OpenRouter vision pass over the page's images. */
  deep?: boolean;
}

export interface AddSourceResponse {
  source: Source;
}

export interface OkResponse {
  ok: boolean;
}

/* ------------------------------- generation ------------------------------ */

export interface GenerateRequest {
  templateId: TemplateId;
  /** Only meaningful when templateId === "custom". */
  customTemplate?: string;
  /** Freeform steering text from the composer bar. */
  prompt?: string;
}

export interface GenerateResponse {
  bundle: PostBundle;
}

export interface RegenerateRequest {
  postId: string;
}

export interface RegenerateResponse {
  post: Post;
}

/* --------------------------------- images -------------------------------- */

export interface ImageRequest {
  postId: string;
  ratio?: ImageRatio;
  style?: ImageStyle;
  /** Override the LLM's suggested background prompt. */
  imagePrompt?: string;
  /** Search the web (Tavily) for a real scene photo to guide the background. */
  webSearch?: boolean;
}

/** Info about a web image found by the Tavily scene search. */
export interface WebImageInfo {
  query: string;
  url?: string | null;
  description?: string | null;
  /** /media path of the downloaded scene photo. */
  local?: string | null;
}

export interface ImageResponse {
  post: Post;
  webImage?: WebImageInfo | null;
}

/* ------------------------------- reference ------------------------------- */

export interface ReferenceRequest {
  /** A base64 `data:image/...` URL read from the uploaded file. */
  dataUrl: string;
}

export interface ReferenceResponse {
  referenceImage?: string | null;
}

/* ------------------------------- watermark ------------------------------- */

export interface WatermarkRequest {
  /** Empty string = no watermark; null = fall back to brand.json. */
  watermark?: string | null;
}

export interface WatermarkResponse {
  watermark?: string | null;
}

/* -------------------------------- approve -------------------------------- */

export interface ApproveRequest {
  postId: string;
}

export interface ApproveResponse {
  post: Post;
  postedAt: string; // ISO 8601
  providerPostId?: string | null;
}

/* ------------------------------ session/auth ----------------------------- */

export interface LinkedInStatus {
  connected: boolean;
  status: "connected" | "expiring" | "expired" | "needs_reauth" | "disconnected";
  displayName?: string | null;
  expiresAt?: string | null;
}

export interface SessionResponse {
  sources: Source[];
  posts: Post[];
  linkedin: LinkedInStatus;
  /** /media path of the uploaded style reference, if any. */
  referenceImage?: string | null;
  /** Watermark drawn on generated images; "" = none, null = brand default. */
  watermark?: string | null;
}

export interface ClearSessionResponse {
  ok: boolean;
}

export interface ProviderErrorResponse {
  detail: string;
  /** Present on a 409 from /api/approve: send the browser here to connect. */
  connectUrl?: string;
}
