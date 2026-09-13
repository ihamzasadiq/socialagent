import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, KeyboardEvent, MouseEvent, ReactNode, RefObject, SVGProps } from "react";
import type {
  ImageRatio,
  LinkedInStatus,
  PlatformId,
  Post,
  Source,
  TemplateId,
} from "@shared/types";
import {
  ApiError,
  addSource as addSourceApi,
  approvePost,
  clearReference as clearReferenceApi,
  clearSession as clearSessionApi,
  disconnectLinkedIn,
  generateImage,
  generatePosts,
  getSession,
  regeneratePost,
  removeSource as removeSourceApi,
  setReference as setReferenceApi,
  setWatermark as setWatermarkApi,
} from "./api";

/* ------------------------------------------------------------------ */
/* Icons — functional only (add, remove, send, check, refresh, panels) */
/* ------------------------------------------------------------------ */

type IconProps = SVGProps<SVGSVGElement>;

const svg: IconProps = {
  strokeWidth: 1.5,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  fill: "none",
  stroke: "currentColor",
  viewBox: "0 0 24 24",
  xmlns: "http://www.w3.org/2000/svg",
};

const Plus = (p: IconProps) => (
  <svg {...svg} width="14" height="14" {...p}>
    <path d="M12 5v14M5 12h14" />
  </svg>
);
const Close = (p: IconProps) => (
  <svg {...svg} width="14" height="14" {...p}>
    <path d="M6 6l12 12M18 6L6 18" />
  </svg>
);
const Send = (p: IconProps) => (
  <svg {...svg} width="14" height="14" {...p}>
    <path d="M4 12h15M13 6l6 6-6 6" />
  </svg>
);
const Check = (p: IconProps) => (
  <svg {...svg} width="14" height="14" {...p}>
    <path d="M4 12.5l5 5L20 6.5" />
  </svg>
);
const Refresh = (p: IconProps) => (
  <svg {...svg} width="14" height="14" {...p}>
    <path d="M20 11a8 8 0 10-1.8 6M20 5v6h-6" />
  </svg>
);
const PanelLeft = (p: IconProps) => (
  <svg {...svg} width="15" height="15" {...p}>
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <path d="M10 4v16" />
  </svg>
);
const PanelRight = (p: IconProps) => (
  <svg {...svg} width="15" height="15" {...p}>
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <path d="M14 4v16" />
  </svg>
);
const ImageGlyph = (p: IconProps) => (
  <svg {...svg} width="16" height="16" {...p}>
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <circle cx="9" cy="10" r="1.6" />
    <path d="M21 16l-5-5-8 9" />
  </svg>
);
const SourceGlyph = (p: IconProps) => (
  <svg {...svg} width="18" height="18" {...p}>
    <path d="M10 13a4 4 0 006 .5l2-2a4 4 0 10-5.7-5.7l-1.1 1.1" />
    <path d="M14 11a4 4 0 00-6-.5l-2 2a4 4 0 105.7 5.7l1.1-1.1" />
  </svg>
);
const LinkGlyph = (p: IconProps) => (
  <svg {...svg} width="13" height="13" {...p}>
    <path d="M10 13a4 4 0 006 .5l2-2a4 4 0 10-5.7-5.7" />
    <path d="M14 11a4 4 0 00-6-.5l-2 2a4 4 0 105.7 5.7" />
  </svg>
);
const WarningGlyph = (p: IconProps) => (
  <svg {...svg} width="18" height="18" {...p}>
    <path d="M12 3.5l9 15.5H3l9-15.5z" />
    <path d="M12 10v3.5M12 16.5h.01" />
  </svg>
);
const TrashGlyph = (p: IconProps) => (
  <svg {...svg} width="13" height="13" {...p}>
    <path d="M4 7h16M10 7V5h4v2M6 7l1 13h10l1-13" />
  </svg>
);

const Spinner = ({ size = 14 }: { size?: number }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className="animate-spin"
  >
    <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" opacity="0.18" />
    <path d="M21 12a9 9 0 00-9-9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

/* ------------------------------------------------------------------ */
/* Frontend-only display config — NOT part of the wire contract.       */
/* The actual draft copy comes from the backend; this is just labels.  */
/* ------------------------------------------------------------------ */

const TEMPLATES: { id: TemplateId; label: string }[] = [
  { id: "funding", label: "Funding" },
  { id: "acquisition", label: "Acquisition" },
  { id: "launch", label: "Launch" },
  { id: "custom", label: "Custom" },
];

/** Only LinkedIn is shown; Instagram is kept for when publishing lands. */
const ACTIVE_PLATFORMS: PlatformId[] = ["linkedin"];

const PLATFORMS: Record<PlatformId, { name: string; handle: string; mark: string; meta: string }> = {
  linkedin: { name: "LinkedIn", handle: "Personal profile", mark: "in", meta: "long form" },
  instagram: { name: "Instagram", handle: "Business account", mark: "IG", meta: "caption" },
};

const RATIOS: ImageRatio[] = ["4:5", "1:1", "16:9"];

/* ------------------------------------------------------------------ */
/* Small primitives                                                    */
/* ------------------------------------------------------------------ */

function IconButton({
  label,
  onClick,
  children,
  active = false,
  className = "",
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
  active?: boolean;
  className?: string;
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      aria-pressed={active}
      onClick={onClick}
      className={`grid h-7 w-7 place-items-center rounded-lg border border-transparent text-ink-faint transition-colors hover:border-line hover:bg-raised hover:text-ink-dim ${
        active ? "border-line bg-raised text-ink-dim" : ""
      } ${className}`}
    >
      {children}
    </button>
  );
}

function PlatformMark({ mark }: { mark: string }) {
  return (
    <span className="grid h-6 w-6 place-items-center rounded-md border border-line bg-raised text-[10px] font-medium tracking-tight text-ink-dim">
      {mark}
    </span>
  );
}

function ConfirmDialog({
  title,
  body,
  confirmLabel,
  busy = false,
  onConfirm,
  onCancel,
}: {
  title: string;
  body: ReactNode;
  confirmLabel: string;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4"
      onClick={onCancel}
      role="presentation"
    >
      <div
        className="w-full max-w-[440px] rounded-xl border border-line bg-raised p-5 shadow-2xl"
        onClick={(e: MouseEvent) => e.stopPropagation()}
      >
        <h3 className="text-[15px] text-ink">{title}</h3>
        <div className="mt-1.5 text-[13px] leading-relaxed text-ink-dim">{body}</div>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-line px-3 py-1.5 text-[13px] text-ink-dim transition-colors hover:border-line-strong hover:text-ink"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="flex items-center gap-1.5 rounded-lg border border-accent/40 bg-accent-soft px-3 py-1.5 text-[13px] text-accent transition-colors hover:border-accent/60 disabled:opacity-60"
          >
            {busy && <Spinner size={12} />}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

function ReferenceControl({
  referenceImage,
  busy,
  onPick,
  onClear,
}: {
  referenceImage: string | null;
  busy: boolean;
  onPick: (file: File) => void;
  onClear: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <div className="flex shrink-0 items-center gap-2">
      {referenceImage ? (
        <>
          <img
            src={referenceImage}
            alt="Style reference"
            title="Style reference — the agent copies this image's design"
            className="h-8 w-8 rounded-md border border-line object-cover"
          />
          <span className="text-[11px] text-ink-faint">Style ref</span>
          <button
            type="button"
            onClick={onClear}
            aria-label="Remove style reference"
            className="grid h-5 w-5 place-items-center rounded-md text-ink-faint transition hover:bg-canvas hover:text-ink-dim"
          >
            <Close width={11} height={11} />
          </button>
        </>
      ) : (
        <button
          type="button"
          disabled={busy}
          onClick={() => inputRef.current?.click()}
          title="Upload a style reference — the agent copies its layout, palette and typography"
          className="flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1 text-[11px] text-ink-dim transition-colors hover:border-line-strong hover:text-ink disabled:opacity-60"
        >
          {busy ? <Spinner size={12} /> : <ImageGlyph width={13} height={13} />}
          Style ref
        </button>
      )}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e: ChangeEvent<HTMLInputElement>) => {
          const file = e.target.files?.[0];
          if (file) onPick(file);
          e.target.value = "";
        }}
      />
    </div>
  );
}

function WatermarkControl({
  value,
  onSave,
}: {
  value: string;
  onSave: (value: string) => void;
}) {
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);

  const commit = () => {
    const next = draft.trim();
    if (next !== value) onSave(next);
  };

  return (
    <input
      value={draft}
      onChange={(e: ChangeEvent<HTMLInputElement>) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e: KeyboardEvent<HTMLInputElement>) => {
        if (e.key === "Enter") e.currentTarget.blur();
      }}
      placeholder="@watermark"
      title="Watermark drawn on generated images (leave empty for none)"
      className="w-[110px] rounded-lg border border-line bg-raised px-2 py-1 text-[11px] text-ink outline-none transition-colors placeholder:text-ink-faint focus:border-line-strong"
    />
  );
}

/* ------------------------------------------------------------------ */
/* Sidebar — Sources                                                   */
/* ------------------------------------------------------------------ */

function SourceCard({ source, onRemove }: { source: Source; onRemove: (id: string) => void }) {
  const failed = source.status === "error";
  return (
    <li className="group flex items-start gap-2.5 rounded-[10px] border border-line bg-raised px-2.5 py-2 transition-colors hover:border-line-strong">
      <span
        className={`mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-md border text-[10px] font-medium uppercase ${
          failed ? "border-error/40 bg-canvas text-error" : "border-line bg-canvas text-ink-dim"
        }`}
      >
        {source.host.replace(/^www\./, "").charAt(0)}
      </span>
      <div className="min-w-0 flex-1 leading-snug">
        <p className="truncate text-[13px] text-ink">{source.title}</p>
        <p className={`truncate text-[11px] ${failed ? "text-error/80" : "text-ink-faint"}`}>
          {failed ? source.error ?? "Could not fetch this source" : source.path}
        </p>
        {source.deep && !failed && (
          <p className="mt-0.5 text-[10px] uppercase tracking-wide text-accent/80">deep context</p>
        )}
      </div>
      <button
        type="button"
        aria-label={`Remove ${source.title}`}
        onClick={() => onRemove(source.id)}
        className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-md text-ink-faint opacity-0 transition hover:bg-canvas hover:text-ink-dim focus-visible:opacity-100 group-hover:opacity-100"
      >
        <Close />
      </button>
    </li>
  );
}

export type AddSourceResult = { ok: boolean; error?: string };

function Sidebar({
  sources,
  adding,
  onAdd,
  onRemove,
  onCollapse,
  inputRef,
}: {
  sources: Source[];
  adding: boolean;
  onAdd: (raw: string, deep: boolean) => Promise<AddSourceResult>;
  onRemove: (id: string) => void;
  onCollapse: () => void;
  inputRef: RefObject<HTMLInputElement>;
}) {
  const [value, setValue] = useState("");
  const [deep, setDeep] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    const raw = value.trim();
    if (!raw || adding) return;
    const result = await onAdd(raw, deep);
    if (result.ok) {
      setValue("");
      setError("");
    } else {
      setError(result.error || "Couldn't add that source.");
    }
  };

  return (
    <aside className="flex w-[272px] shrink-0 flex-col border-r border-line">
      <div className="flex h-12 items-center justify-between px-4">
        <h2 className="text-[13px] font-medium text-ink-dim">Sources</h2>
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] tabular-nums text-ink-faint">{sources.length}</span>
          <IconButton label="Collapse sources panel" onClick={onCollapse}>
            <PanelLeft />
          </IconButton>
        </div>
      </div>

      <div className="px-3 pb-3">
        <div className="flex items-center gap-1.5 rounded-[10px] border border-line bg-raised px-2.5 py-1.5 focus-within:border-line-strong">
          {adding ? <Spinner size={13} /> : <Plus className="shrink-0 text-ink-faint" />}
          <input
            ref={inputRef}
            value={value}
            onChange={(e: ChangeEvent<HTMLInputElement>) => {
              setValue(e.target.value);
              if (error) setError("");
            }}
            onKeyDown={(e: KeyboardEvent<HTMLInputElement>) => {
              if (e.key === "Enter") void submit();
            }}
            placeholder={adding ? "Reading source…" : "Add source URL"}
            disabled={adding}
            className="min-w-0 flex-1 bg-transparent text-[13px] text-ink outline-none placeholder:text-ink-faint disabled:opacity-70"
          />
          {value.trim() && !adding && (
            <button
              type="button"
              onClick={() => void submit()}
              className="shrink-0 rounded-md px-1.5 text-[11px] text-accent transition-colors hover:bg-accent-soft"
            >
              Add
            </button>
          )}
        </div>
        <label className="mt-2 flex cursor-pointer items-center gap-1.5 px-1 text-[11px] text-ink-faint">
          <input
            type="checkbox"
            checked={deep}
            disabled={adding}
            onChange={(e: ChangeEvent<HTMLInputElement>) => setDeep(e.target.checked)}
            className="h-3 w-3 accent-[#d9a95c]"
          />
          Analyze page images too (slower)
        </label>
        {error && <p className="mt-1.5 px-1 text-[11px] text-error/90">{error}</p>}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
        {sources.length === 0 ? (
          <p className="px-1 pt-2 text-[12px] leading-relaxed text-ink-faint">
            Paste a link to a blog post, changelog, or press release. Sources ground every draft.
          </p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {sources.map((s) => (
              <SourceCard key={s.id} source={s} onRemove={onRemove} />
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}

/* ------------------------------------------------------------------ */
/* Center — templates, feed, composer                                  */
/* ------------------------------------------------------------------ */

function TemplateTabs({
  value,
  onChange,
}: {
  value: TemplateId;
  onChange: (id: TemplateId) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {TEMPLATES.map((t) => {
        const active = t.id === value;
        return (
          <button
            key={t.id}
            type="button"
            onClick={() => onChange(t.id)}
            aria-pressed={active}
            className={`rounded-full border px-3 py-1 text-[13px] transition-colors ${
              active
                ? "border-accent/40 bg-accent-soft text-accent"
                : "border-line bg-transparent text-ink-dim hover:border-line-strong hover:text-ink"
            }`}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

function SkeletonCard({ lines }: { lines: number }) {
  return (
    <article className="rounded-xl border border-line bg-raised/40 p-4">
      <div className="flex items-center gap-2.5">
        <div className="h-6 w-6 animate-pulse rounded-md bg-line" />
        <div className="h-3 w-24 animate-pulse rounded bg-line" />
      </div>
      <div className="mt-4 flex gap-4">
        <div className="h-24 w-20 shrink-0 animate-pulse rounded-lg bg-line" />
        <div className="flex-1 space-y-2.5 pt-1">
          {Array.from({ length: lines }).map((_, i) => (
            <div
              key={i}
              className="h-2.5 animate-pulse rounded bg-line"
              style={{ width: `${[96, 88, 72, 60][i % 4]}%` }}
            />
          ))}
        </div>
      </div>
    </article>
  );
}

/** Post plus frontend-only view-state — `loading` never crosses the wire. */
type UIPost = Post & { loading: boolean };

function PostThumb({ post }: { post: UIPost }) {
  if (post.imageUrl && post.imageStatus !== "generating") {
    return (
      <img
        src={post.imageUrl}
        alt={post.altText || post.headline || "Post image"}
        className="h-24 w-20 shrink-0 rounded-lg border border-line object-cover"
      />
    );
  }
  return (
    <div
      className={`grid h-24 w-20 shrink-0 place-items-center rounded-lg border text-ink-faint ${
        post.status === "posted" ? "border-line bg-raised opacity-60" : "border-line bg-raised"
      }`}
      style={{
        backgroundImage:
          "repeating-linear-gradient(45deg, rgba(255,255,255,0.018) 0 6px, transparent 6px 12px)",
      }}
      aria-hidden="true"
    >
      {post.imageStatus === "generating" ? <Spinner size={16} /> : <ImageGlyph />}
    </div>
  );
}

function PostCard({
  post,
  onApprove,
  onRegenerate,
  onImage,
}: {
  post: UIPost;
  onApprove: (id: string) => void;
  onRegenerate: (id: string) => void;
  onImage: (id: string, ratio: ImageRatio, webSearch: boolean) => void;
}) {
  const p = PLATFORMS[post.platform];
  const posted = post.status === "posted";
  const [ratio, setRatio] = useState<ImageRatio>("4:5");
  const [webBg, setWebBg] = useState(false);
  const imaging = post.imageStatus === "generating";

  if (post.loading) return <SkeletonCard lines={3} />;

  return (
    <article
      className={`rounded-xl border bg-raised/40 p-4 transition-colors ${
        posted ? "border-line" : "border-line hover:border-line-strong"
      }`}
    >
      <header className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <PlatformMark mark={p.mark} />
          <div className="min-w-0 leading-tight">
            <p className="truncate text-[13px] text-ink">{p.name}</p>
            <p className="truncate text-[11px] text-ink-faint">{p.handle}</p>
          </div>
        </div>
        {posted ? (
          <span className="flex shrink-0 items-center gap-1.5 rounded-full border border-ok/25 px-2.5 py-0.5 text-[11px] text-ok">
            <Check /> Posted
          </span>
        ) : (
          <span className="shrink-0 text-[11px] text-ink-faint">{p.meta}</span>
        )}
      </header>

      <div className="mt-4 flex gap-4">
        <PostThumb post={post} />
        <div className="min-w-0 flex-1">
          {post.headline && (
            <p className="mb-1 truncate text-[12px] font-medium uppercase tracking-wide text-accent/90">
              {post.headline}
            </p>
          )}
          <p
            className={`min-w-0 whitespace-pre-wrap text-[14px] leading-[1.75] ${
              posted ? "text-ink-dim" : "text-ink"
            }`}
          >
            {post.text}
          </p>
          {post.hashtags.length > 0 && (
            <p className="mt-2 text-[12px] text-ink-faint">
              {post.hashtags.map((tag) => `#${tag}`).join(" ")}
            </p>
          )}
          {post.imageError && (
            <p className="mt-2 text-[11px] text-error/90">Image failed: {post.imageError}</p>
          )}
        </div>
      </div>

      <footer className="mt-4 flex items-center justify-between gap-3 border-t border-line pt-3">
        <span className="text-[11px] text-ink-faint">
          {posted ? "Published just now" : `Draft ${post.variantIndex + 1} · awaiting approval`}
        </span>
        {!posted && (
          <div className="flex items-center gap-2">
            {imaging ? (
              <span className="flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1 text-[12px] text-ink-faint">
                <Spinner size={12} /> Imaging…
              </span>
            ) : (
              <>
                <select
                  value={ratio}
                  onChange={(e: ChangeEvent<HTMLSelectElement>) =>
                    setRatio(e.target.value as ImageRatio)
                  }
                  title="Image ratio"
                  className="rounded-lg border border-line bg-raised px-1.5 py-1 text-[11px] text-ink-dim outline-none transition-colors hover:border-line-strong"
                >
                  {RATIOS.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
                <label
                  className="flex cursor-pointer items-center gap-1 text-[11px] text-ink-faint"
                  title="Search the web for a real scene photo to guide the background"
                >
                  <input
                    type="checkbox"
                    checked={webBg}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => setWebBg(e.target.checked)}
                    className="h-3 w-3 accent-[#d9a95c]"
                  />
                  Web bg
                </label>
                <button
                  type="button"
                  onClick={() => onImage(post.id, ratio, webBg)}
                  className="flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1 text-[12px] text-ink-dim transition-colors hover:border-line-strong hover:text-ink"
                >
                  <ImageGlyph width={13} height={13} />
                  {post.imageUrl ? "New image" : "Add image"}
                </button>
              </>
            )}
            <button
              type="button"
              onClick={() => onRegenerate(post.id)}
              className="flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1 text-[12px] text-ink-dim transition-colors hover:border-line-strong hover:text-ink"
            >
              <Refresh /> Regenerate
            </button>
            <button
              type="button"
              onClick={() => onApprove(post.id)}
              className="flex items-center gap-1.5 rounded-lg border border-accent/40 bg-accent-soft px-2.5 py-1 text-[12px] text-accent transition-colors hover:border-accent/60"
            >
              <Check /> Approve
            </button>
          </div>
        )}
      </footer>
    </article>
  );
}

function EmptyState({ onAddSource }: { onAddSource: () => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center px-6 text-center">
      <span className="grid h-10 w-10 place-items-center rounded-xl border border-line bg-raised text-ink-faint">
        <SourceGlyph />
      </span>
      <h3 className="mt-4 text-[15px] text-ink">Ground it with a source — or skip it</h3>
      <p className="mt-1.5 max-w-[380px] text-[13px] leading-relaxed text-ink-faint">
        Sources make drafts factual: paste one or more URLs in the left panel. Or just describe
        what you want in the composer below and generate without any source.
      </p>
      <button
        type="button"
        onClick={onAddSource}
        className="mt-5 rounded-lg border border-accent/40 bg-accent-soft px-3 py-1.5 text-[13px] text-accent transition-colors hover:border-accent/60"
      >
        Add a source
      </button>
    </div>
  );
}

function ReadyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center px-6 text-center">
      <h3 className="text-[15px] text-ink">Ready when you are</h3>
      <p className="mt-1.5 max-w-[380px] text-[13px] leading-relaxed text-ink-faint">
        Pick a template, add any extra direction below, and generate a LinkedIn draft. You can add
        an image afterwards.
      </p>
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center px-6 text-center">
      <span className="grid h-10 w-10 place-items-center rounded-xl border border-error/30 bg-raised text-error">
        <WarningGlyph />
      </span>
      <h3 className="mt-4 text-[15px] text-ink">Couldn't generate drafts</h3>
      <p className="mt-1.5 max-w-[380px] text-[13px] leading-relaxed text-ink-faint">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-5 flex items-center gap-1.5 rounded-lg border border-accent/40 bg-accent-soft px-3 py-1.5 text-[13px] text-accent transition-colors hover:border-accent/60"
      >
        <Refresh /> Retry
      </button>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Right — activity log                                                */
/* ------------------------------------------------------------------ */

type LogTone = "dim" | "default" | "accent" | "ok" | "error";
interface LogEntry {
  id: string;
  text: string;
  tone: LogTone;
  time: string;
}

function LogPanel({
  entries,
  running,
  onCollapse,
}: {
  entries: LogEntry[];
  running: boolean;
  onCollapse: () => void;
}) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [entries.length]);

  const toneClass: Record<LogTone, string> = {
    dim: "text-ink-faint",
    default: "text-ink-dim",
    accent: "text-accent",
    ok: "text-ok",
    error: "text-error",
  };

  return (
    <aside className="flex w-[300px] shrink-0 flex-col border-l border-line">
      <div className="flex h-12 items-center justify-between px-4">
        <h2 className="flex items-center gap-2 text-[13px] font-medium text-ink-dim">
          Activity
          {running && <Spinner size={12} />}
        </h2>
        <IconButton label="Collapse activity panel" onClick={onCollapse}>
          <PanelRight />
        </IconButton>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-4 font-mono text-[11px] leading-[1.9]">
        {entries.length === 0 ? (
          <p className="text-ink-faint">— idle —</p>
        ) : (
          <ul>
            {entries.map((entry) => (
              <li key={entry.id} className="flex gap-2">
                <span className="shrink-0 text-ink-faint/60 tabular-nums">{entry.time}</span>
                <span className={`min-w-0 break-words ${toneClass[entry.tone]}`}>{entry.text}</span>
              </li>
            ))}
          </ul>
        )}
        <div ref={endRef} />
      </div>
    </aside>
  );
}

/* ------------------------------------------------------------------ */
/* App                                                                 */
/* ------------------------------------------------------------------ */

let uid = 0;
const nextId = () => `id-${++uid}`;

const stamp = () =>
  new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

type Phase = "idle" | "loading" | "preview" | "error";

export default function App() {
  const [booting, setBooting] = useState(true);
  const [sources, setSources] = useState<Source[]>([]);
  const [addingSource, setAddingSource] = useState(false);
  const [template, setTemplate] = useState<TemplateId>("launch");
  const [customTemplate, setCustomTemplate] = useState("");
  const [prompt, setPrompt] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [posts, setPosts] = useState<UIPost[]>([]);
  const [linkedin, setLinkedin] = useState<LinkedInStatus>({
    connected: false,
    status: "disconnected",
  });
  const [referenceImage, setReferenceImage] = useState<string | null>(null);
  const [referenceBusy, setReferenceBusy] = useState(false);
  const [watermark, setWatermark] = useState("");
  const [log, setLog] = useState<LogEntry[]>([]);
  const [errorMessage, setErrorMessage] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [logOpen, setLogOpen] = useState(true);
  const [confirmPost, setConfirmPost] = useState<UIPost | null>(null);
  const [publishing, setPublishing] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);

  const addInputRef = useRef<HTMLInputElement>(null);

  const pushLog = useCallback((text: string, tone: LogTone = "default") => {
    setLog((prev) => [...prev, { id: nextId(), text, tone, time: stamp() }]);
  }, []);

  /* Rehydrate from the backend's single session and consume any OAuth
     callback query params (?connected=linkedin / ?error=...). */
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const connected = params.get("connected");
    const oauthError = params.get("error");
    if (connected || oauthError) {
      window.history.replaceState({}, "", window.location.pathname);
    }
    if (connected === "linkedin") pushLog("LinkedIn connected", "ok");
    else if (connected) pushLog(`Connected ${connected}`, "ok");
    if (oauthError) pushLog(`OAuth failed: ${oauthError}`, "error");

    void (async () => {
      try {
        const data = await getSession();
        setSources(data.sources);
        setPosts(data.posts.map((post) => ({ ...post, loading: false })));
        setLinkedin(data.linkedin);
        setReferenceImage(data.referenceImage ?? null);
        setWatermark(data.watermark ?? "");
        if (data.posts.length > 0) setPhase("preview");
      } catch (err) {
        const message = err instanceof ApiError ? err.message : "Could not load the session.";
        pushLog(`Session load failed: ${message}`, "error");
      } finally {
        setBooting(false);
      }
    })();
  }, [pushLog]);

  const addSource = async (raw: string, deep: boolean): Promise<AddSourceResult> => {
    setAddingSource(true);
    pushLog(`Fetching ${raw.slice(0, 60)}${deep ? " (deep analysis)" : ""}…`, "dim");
    try {
      const { source } = await addSourceApi({ url: raw, deep });
      setSources((prev) => [...prev, source]);
      if (source.status === "error") {
        pushLog(`Source failed: ${source.error ?? "unknown error"}`, "error");
        return { ok: true, error: source.error ?? undefined };
      }
      pushLog(`+ ${source.host} · ${source.title}`, "dim");
      return { ok: true };
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Could not add that source.";
      pushLog(`Source rejected: ${message}`, "error");
      return { ok: false, error: message };
    } finally {
      setAddingSource(false);
    }
  };

  const removeSource = async (id: string) => {
    const gone = sources.find((s) => s.id === id);
    setSources((prev) => prev.filter((s) => s.id !== id));
    try {
      await removeSourceApi(id);
      if (gone) pushLog(`- ${gone.path}`, "dim");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Could not remove that source.";
      pushLog(`Remove failed: ${message}`, "error");
    }
  };

  const uploadReference = (file: File) => {
    if (file.size > 12 * 1024 * 1024) {
      pushLog("Reference image is larger than 12 MB", "error");
      return;
    }
    setReferenceBusy(true);
    const reader = new FileReader();
    reader.onerror = () => {
      pushLog("Could not read the reference image", "error");
      setReferenceBusy(false);
    };
    reader.onload = async () => {
      try {
        const { referenceImage: url } = await setReferenceApi({
          dataUrl: String(reader.result),
        });
        setReferenceImage(url ?? null);
        pushLog("Style reference set — generate or regenerate to apply its style", "accent");
      } catch (err) {
        const message = err instanceof ApiError ? err.message : "Could not set the reference.";
        pushLog(`Reference failed: ${message}`, "error");
      } finally {
        setReferenceBusy(false);
      }
    };
    reader.readAsDataURL(file);
  };

  const removeReference = async () => {
    try {
      await clearReferenceApi();
      setReferenceImage(null);
      pushLog("Style reference removed", "dim");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Could not clear the reference.";
      pushLog(message, "error");
    }
  };

  const saveWatermark = async (value: string) => {
    try {
      const result = await setWatermarkApi({ watermark: value });
      setWatermark(result.watermark ?? "");
      pushLog(value ? `Watermark: ${value}` : "Watermark disabled", "dim");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Could not save the watermark.";
      pushLog(message, "error");
    }
  };

  const templateLabel = useMemo(
    () => TEMPLATES.find((t) => t.id === template)?.label ?? "Custom",
    [template]
  );

  const generate = async () => {
    if (phase === "loading") return;
    setErrorMessage("");
    setPhase("loading");
    pushLog(`Applying template: ${templateLabel}`, "default");
    if (prompt.trim()) pushLog(`Steering: "${prompt.trim().slice(0, 44)}"`, "dim");
    pushLog("Talking to the generation service…", "default");

    try {
      const { bundle } = await generatePosts({
        templateId: template,
        customTemplate: template === "custom" ? customTemplate : undefined,
        prompt: prompt.trim() || undefined,
      });
      bundle.posts.forEach((post) => {
        if (ACTIVE_PLATFORMS.includes(post.platform)) {
          pushLog(`${PLATFORMS[post.platform].name} draft ready`, "default");
        }
      });
      pushLog(`${bundle.posts.length} draft(s) — review, then approve to publish`, "accent");
      setPosts(bundle.posts.map((post) => ({ ...post, loading: false })));
      setPhase("preview");
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Something went wrong generating drafts.";
      pushLog(`Generation failed: ${message}`, "error");
      setErrorMessage(message);
      setPhase("error");
    }
  };

  const regenerate = async (id: string) => {
    const target = posts.find((p) => p.id === id);
    if (!target) return;
    pushLog(`Regenerating ${PLATFORMS[target.platform].name} draft…`, "default");
    setPosts((prev) => prev.map((p) => (p.id === id ? { ...p, loading: true } : p)));

    try {
      const { post } = await regeneratePost({ postId: id });
      setPosts((prev) =>
        prev.map((p) => (p.id === id ? { ...post, loading: false } : p))
      );
      pushLog(`${PLATFORMS[post.platform].name} draft updated`, "dim");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Regenerate failed.";
      setPosts((prev) => prev.map((p) => (p.id === id ? { ...p, loading: false } : p)));
      pushLog(`Regenerate failed: ${message}`, "error");
    }
  };

  const makeImage = async (id: string, ratio: ImageRatio, webSearch: boolean) => {
    const target = posts.find((p) => p.id === id);
    if (!target) return;
    const mode = referenceImage ? "reference-styled " : "";
    pushLog(
      `Generating ${mode}${ratio} image for ${PLATFORMS[target.platform].name}…`,
      "default"
    );
    setPosts((prev) =>
      prev.map((p) => (p.id === id ? { ...p, imageStatus: "generating", imageError: null } : p))
    );
    try {
      const { post, webImage } = await generateImage({ postId: id, ratio, webSearch });
      setPosts((prev) => prev.map((p) => (p.id === id ? { ...post, loading: false } : p)));
      if (webImage) {
        pushLog(`Web background: ${webImage.description || webImage.query}`, "dim");
      }
      pushLog("Image ready — attached when you approve", "accent");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Image generation failed.";
      setPosts((prev) =>
        prev.map((p) =>
          p.id === id ? { ...p, imageStatus: "error", imageError: message } : p
        )
      );
      pushLog(`Image failed: ${message}`, "error");
    }
  };

  const requestApprove = (id: string) => {
    const target = posts.find((p) => p.id === id);
    if (target && target.status !== "posted") setConfirmPost(target);
  };

  const doApprove = async () => {
    const target = confirmPost;
    if (!target) return;
    setPublishing(true);
    try {
      const { post, providerPostId } = await approvePost({ postId: target.id });
      setPosts((prev) => prev.map((p) => (p.id === target.id ? { ...post, loading: false } : p)));
      pushLog(
        `Posted to LinkedIn ✓${providerPostId ? ` (${providerPostId})` : ""}`,
        "ok"
      );
      setConfirmPost(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409 && err.connectUrl) {
        pushLog("LinkedIn isn't connected — opening the authorization flow…", "error");
        window.location.href = err.connectUrl;
        return;
      }
      const message = err instanceof ApiError ? err.message : "Approve failed.";
      pushLog(`Publish failed: ${message}`, "error");
    } finally {
      setPublishing(false);
    }
  };

  const connectLinkedIn = () => {
    pushLog("Redirecting to LinkedIn…", "dim");
    window.location.href = "/api/oauth/linkedin/connect";
  };

  const disconnect = async () => {
    try {
      await disconnectLinkedIn();
      setLinkedin({ connected: false, status: "disconnected" });
      pushLog("LinkedIn disconnected", "dim");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Disconnect failed.";
      pushLog(message, "error");
    }
  };

  const clearSession = async () => {
    try {
      await clearSessionApi();
      setSources([]);
      setPosts([]);
      setPhase("idle");
      setErrorMessage("");
      setLinkedin({ connected: false, status: "disconnected" });
      setReferenceImage(null);
      setWatermark("");
      pushLog("Session cleared", "accent");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Clear failed.";
      pushLog(message, "error");
    } finally {
      setConfirmClear(false);
    }
  };

  const focusAddSource = () => {
    setSidebarOpen(true);
    setTimeout(() => addInputRef.current?.focus(), 0);
  };

  const hasSources = sources.length > 0;

  if (booting) {
    return (
      <div className="grid h-full place-items-center bg-canvas text-ink-faint">
        <span className="flex items-center gap-2 text-[13px]">
          <Spinner size={15} /> Loading session…
        </span>
      </div>
    );
  }

  return (
    <div className="flex h-full bg-canvas text-ink">
      {sidebarOpen ? (
        <Sidebar
          sources={sources}
          adding={addingSource}
          onAdd={addSource}
          onRemove={removeSource}
          onCollapse={() => setSidebarOpen(false)}
          inputRef={addInputRef}
        />
      ) : (
        <div className="flex w-12 shrink-0 flex-col items-center gap-3 border-r border-line pt-2.5">
          <IconButton label="Expand sources panel" onClick={() => setSidebarOpen(true)}>
            <PanelLeft />
          </IconButton>
          {hasSources && (
            <span className="text-[11px] tabular-nums text-ink-faint">{sources.length}</span>
          )}
        </div>
      )}

      {/* center */}
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 shrink-0 items-center justify-between border-b border-line px-5">
          <div className="flex items-baseline gap-2.5">
            <h1 className="text-[13px] font-medium text-ink">Workspace</h1>
            <span className="text-[11px] text-ink-faint">
              {hasSources
                ? `${sources.length} source${sources.length === 1 ? "" : "s"} · ${templateLabel}`
                : "no sources"}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {linkedin.connected ? (
              <span className="flex items-center gap-2 rounded-full border border-ok/25 px-2.5 py-0.5 text-[11px] text-ok">
                <span className="h-1.5 w-1.5 rounded-full bg-ok" />
                {linkedin.displayName || "LinkedIn connected"}
                <button
                  type="button"
                  onClick={() => void disconnect()}
                  className="text-ink-faint transition-colors hover:text-ink"
                  title="Disconnect LinkedIn"
                >
                  <Close width={11} height={11} />
                </button>
              </span>
            ) : (
              <button
                type="button"
                onClick={connectLinkedIn}
                className="flex items-center gap-1.5 rounded-lg border border-accent/40 bg-accent-soft px-2.5 py-1 text-[12px] text-accent transition-colors hover:border-accent/60"
              >
                <LinkGlyph /> Connect LinkedIn
              </button>
            )}
            <button
              type="button"
              onClick={() => setConfirmClear(true)}
              className="flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1 text-[12px] text-ink-dim transition-colors hover:border-line-strong hover:text-ink"
              title="Clear the session (sources, drafts, images, LinkedIn)"
            >
              <TrashGlyph /> Clear session
            </button>
            {!logOpen && (
              <IconButton label="Show activity panel" onClick={() => setLogOpen(true)}>
                <PanelRight />
              </IconButton>
            )}
          </div>
        </header>

        <div className="shrink-0 border-b border-line px-5 py-3">
          <div className="mx-auto w-full max-w-[680px]">
            <div className="flex items-center justify-between gap-3">
              <TemplateTabs value={template} onChange={setTemplate} />
              <div className="flex shrink-0 items-center gap-3">
                <WatermarkControl value={watermark} onSave={(v) => void saveWatermark(v)} />
                <ReferenceControl
                  referenceImage={referenceImage}
                  busy={referenceBusy}
                  onPick={uploadReference}
                  onClear={() => void removeReference()}
                />
              </div>
            </div>
            {template === "custom" && (
              <textarea
                value={customTemplate}
                onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setCustomTemplate(e.target.value)}
                rows={4}
                placeholder={
                  "Paste a custom template…\n\ne.g. Hook (1 line) → what changed → one number → single CTA. No emoji, no hashtags."
                }
                className="mt-3 w-full resize-y rounded-[10px] border border-line bg-raised px-3 py-2.5 text-[13px] leading-relaxed text-ink outline-none transition-colors placeholder:text-ink-faint focus:border-line-strong"
              />
            )}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[680px] px-5 py-6">
            {phase === "error" ? (
              <div className="h-[60vh]">
                <ErrorState message={errorMessage} onRetry={() => void generate()} />
              </div>
            ) : !hasSources && phase !== "loading" && posts.length === 0 ? (
              <div className="h-[60vh]">
                <EmptyState onAddSource={focusAddSource} />
              </div>
            ) : phase === "loading" ? (
              <div className="flex flex-col gap-4">
                <div className="flex items-center gap-2 px-1 text-[12px] text-ink-faint">
                  <Spinner size={13} />
                  Generating drafts from {sources.length} source
                  {sources.length === 1 ? "" : "s"}…
                </div>
                {[4, 6, 3].map((lines, i) => (
                  <SkeletonCard key={i} lines={lines} />
                ))}
              </div>
            ) : posts.length === 0 ? (
              <div className="h-[60vh]">
                <ReadyState />
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                {posts.map((p) => (
                  <PostCard
                    key={p.id}
                    post={p}
                    onApprove={requestApprove}
                    onRegenerate={(id) => void regenerate(id)}
                    onImage={(id, ratio, webSearch) => void makeImage(id, ratio, webSearch)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="shrink-0 border-t border-line px-5 py-4">
          <div className="mx-auto w-full max-w-[680px]">
            <div className="flex items-center gap-2 rounded-xl border border-line bg-raised px-3 py-2 transition-colors focus-within:border-line-strong">
              <input
                value={prompt}
                onChange={(e: ChangeEvent<HTMLInputElement>) => setPrompt(e.target.value)}
                onKeyDown={(e: KeyboardEvent<HTMLInputElement>) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void generate();
                  }
                }}
                placeholder={
                  hasSources
                    ? "Add direction — tone, audience, what to emphasize…"
                    : "Describe what to post about — sources are optional…"
                }
                className="min-w-0 flex-1 bg-transparent text-[14px] text-ink outline-none placeholder:text-ink-faint"
              />
              <button
                type="button"
                onClick={() => void generate()}
                disabled={phase === "loading"}
                className={`flex shrink-0 items-center gap-1.5 rounded-lg border px-3 py-1.5 text-[13px] transition-colors ${
                  phase === "loading"
                    ? "cursor-not-allowed border-line text-ink-faint"
                    : "border-accent/40 bg-accent-soft text-accent hover:border-accent/60"
                }`}
              >
                {phase === "loading" ? <Spinner size={13} /> : <Send />}
                {phase === "loading"
                  ? "Generating"
                  : posts.length > 0
                    ? "Regenerate all"
                    : "Generate posts"}
              </button>
            </div>
            <p className="mt-2 px-1 text-[11px] text-ink-faint">
              Drafts are previews. You approve each card before anything publishes — images are
              optional. Add a style reference (top right) to copy a design, or tick “Web bg” on a
              card to ground the background in a real photo.
            </p>
          </div>
        </div>
      </main>

      {logOpen && (
        <LogPanel entries={log} running={phase === "loading"} onCollapse={() => setLogOpen(false)} />
      )}

      {confirmPost && (
        <ConfirmDialog
          title="Publish this draft to LinkedIn?"
          body={
            <>
              It will be posted as{" "}
              <span className="text-ink">{linkedin.displayName || "your profile"}</span>
              {confirmPost.imageUrl ? " with the generated image attached" : " as text only"}. This
              cannot be undone from here.
            </>
          }
          confirmLabel="Publish now"
          busy={publishing}
          onConfirm={() => void doApprove()}
          onCancel={() => setConfirmPost(null)}
        />
      )}

      {confirmClear && (
        <ConfirmDialog
          title="Clear the session?"
          body="Sources, drafts, generated images and the LinkedIn connection are all forgotten. There is no database, so this cannot be undone."
          confirmLabel="Clear everything"
          onConfirm={() => void clearSession()}
          onCancel={() => setConfirmClear(false)}
        />
      )}
    </div>
  );
}
