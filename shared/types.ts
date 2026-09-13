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
 */

export type PlatformId = "twitter" | "linkedin" | "discord";

export type TemplateId = "funding" | "acquisition" | "launch" | "custom";

export type PostStatus = "preview" | "posted";

/** A source URL, parsed into something a template can reference. */
export interface Source {
  id: string;
  url: string;
  host: string;
  title: string;
  path: string;
}

/**
 * A single platform's draft. Deliberately minimal — `variantIndex` and
 * `loading` are frontend view-state, not part of this resource; the
 * frontend layers those on top locally (see UIPost in frontend/src/App.tsx).
 */
export interface Post {
  id: string;
  platform: PlatformId;
  text: string;
  status: PostStatus;
}

/** The result of one generation pass: one Post per platform. */
export interface PostBundle {
  id: string;
  templateId: TemplateId;
  posts: Post[];
  createdAt: string; // ISO 8601
}

export interface GenerateRequest {
  sources: { url: string }[];
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
  platform: PlatformId;
  templateId: TemplateId;
  customTemplate?: string;
  /** The client's CURRENT variant index — input only, not stored server-side. */
  variantIndex: number;
}

export interface RegenerateResponse {
  post: Post;
  /** The new index; the client persists it locally. */
  variantIndex: number;
}

export interface ApproveRequest {
  postId: string;
  platform: PlatformId;
  /**
   * The backend is stateless (see PostBundle discussion in shared/README.md)
   * and never stored this post's text, so the client sends it along with
   * the approval so the response's `post.text` can echo the real thing
   * instead of coming back blank.
   */
  text: string;
}

export interface ApproveResponse {
  post: Post;
  postedAt: string; // ISO 8601
}
