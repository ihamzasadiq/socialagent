import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, KeyboardEvent, ReactNode, RefObject, SVGProps } from "react";
import type { PlatformId, Post, Source, TemplateId } from "@shared/types";
import { ApiError, approvePost, generatePosts, regeneratePost } from "./api";

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
const WarningGlyph = (p: IconProps) => (
  <svg {...svg} width="18" height="18" {...p}>
    <path d="M12 3.5l9 15.5H3l9-15.5z" />
    <path d="M12 10v3.5M12 16.5h.01" />
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

const PLATFORMS: Record<PlatformId, { name: string; handle: string; mark: string; meta: string }> = {
  twitter: { name: "Twitter", handle: "@acme", mark: "X", meta: "280 chars" },
  linkedin: { name: "LinkedIn", handle: "Acme Inc.", mark: "in", meta: "long form" },
  discord: { name: "Discord", handle: "#announcements", mark: "D", meta: "community" },
};

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

function ThumbPlaceholder({ posted }: { posted: boolean }) {
  return (
    <div
      className={`grid h-20 w-20 shrink-0 place-items-center rounded-lg border text-ink-faint ${
        posted ? "border-line bg-raised opacity-60" : "border-line bg-raised"
      }`}
      style={{
        backgroundImage:
          "repeating-linear-gradient(45deg, rgba(255,255,255,0.018) 0 6px, transparent 6px 12px)",
      }}
      aria-hidden="true"
    >
      <ImageGlyph />
    </div>
  );
}

function PlatformMark({ mark }: { mark: string }) {
  return (
    <span className="grid h-6 w-6 place-items-center rounded-md border border-line bg-raised text-[10px] font-medium tracking-tight text-ink-dim">
      {mark}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Sidebar — Sources                                                   */
/* ------------------------------------------------------------------ */

function SourceCard({ source, onRemove }: { source: Source; onRemove: (id: string) => void }) {
  return (
    <li className="group flex items-start gap-2.5 rounded-[10px] border border-line bg-raised px-2.5 py-2 transition-colors hover:border-line-strong">
      <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-md border border-line bg-canvas text-[10px] font-medium uppercase text-ink-dim">
        {source.host.replace(/^www\./, "").charAt(0)}
      </span>
      <div className="min-w-0 flex-1 leading-snug">
        <p className="truncate text-[13px] text-ink">{source.title}</p>
        <p className="truncate text-[11px] text-ink-faint">{source.path}</p>
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

function Sidebar({
  sources,
  onAdd,
  onRemove,
  onCollapse,
  inputRef,
}: {
  sources: Source[];
  onAdd: (raw: string) => boolean;
  onRemove: (id: string) => void;
  onCollapse: () => void;
  inputRef: RefObject<HTMLInputElement>;
}) {
  const [value, setValue] = useState("");
  const [error, setError] = useState("");

  const submit = () => {
    const ok = onAdd(value);
    if (ok) {
      setValue("");
      setError("");
    } else {
      setError(value.trim() ? "That doesn't look like a URL." : "");
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
          <Plus className="shrink-0 text-ink-faint" />
          <input
            ref={inputRef}
            value={value}
            onChange={(e: ChangeEvent<HTMLInputElement>) => {
              setValue(e.target.value);
              if (error) setError("");
            }}
            onKeyDown={(e: KeyboardEvent<HTMLInputElement>) => {
              if (e.key === "Enter") submit();
            }}
            placeholder="Add source URL"
            className="min-w-0 flex-1 bg-transparent text-[13px] text-ink outline-none placeholder:text-ink-faint"
          />
          {value.trim() && (
            <button
              type="button"
              onClick={submit}
              className="shrink-0 rounded-md px-1.5 text-[11px] text-accent transition-colors hover:bg-accent-soft"
            >
              Add
            </button>
          )}
        </div>
        {error && <p className="mt-1.5 px-1 text-[11px] text-ink-faint">{error}</p>}
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
        <div className="h-20 w-20 shrink-0 animate-pulse rounded-lg bg-line" />
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

/** Post plus frontend-only view-state — variantIndex/loading never cross the wire. */
type UIPost = Post & { variantIndex: number; loading: boolean };

function PostCard({
  post,
  onApprove,
  onRegenerate,
}: {
  post: UIPost;
  onApprove: (id: string) => void;
  onRegenerate: (id: string) => void;
}) {
  const p = PLATFORMS[post.platform];
  const posted = post.status === "posted";

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
        <ThumbPlaceholder posted={posted} />
        <p
          className={`min-w-0 flex-1 whitespace-pre-wrap text-[14px] leading-[1.75] ${
            posted ? "text-ink-dim" : "text-ink"
          }`}
        >
          {post.text}
        </p>
      </div>

      <footer className="mt-4 flex items-center justify-between border-t border-line pt-3">
        <span className="text-[11px] text-ink-faint">
          {posted ? "Published just now" : `Draft ${post.variantIndex + 1} · awaiting approval`}
        </span>
        {!posted && (
          <div className="flex items-center gap-2">
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
      <h3 className="mt-4 text-[15px] text-ink">Add a source to get started</h3>
      <p className="mt-1.5 max-w-[380px] text-[13px] leading-relaxed text-ink-faint">
        Paste one or more URLs in the left panel. Drafts are generated from what those pages say —
        nothing is written from thin air.
      </p>
      <button
        type="button"
        onClick={onAddSource}
        className="mt-5 rounded-lg border border-accent/40 bg-accent-soft px-3 py-1.5 text-[13px] text-accent transition-colors hover:border-accent/60"
      >
        Add your first source
      </button>
    </div>
  );
}

function ReadyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center px-6 text-center">
      <h3 className="text-[15px] text-ink">Ready when you are</h3>
      <p className="mt-1.5 max-w-[380px] text-[13px] leading-relaxed text-ink-faint">
        Pick a template, add any extra direction below, and generate a draft for each platform.
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

/** Pure, offline parse — mirrors backend/ingestion/fetch.py's parse_source()
 * fallback so the sidebar can show a card instantly, with no network call,
 * the moment a URL is added. The backend does its own (possibly better)
 * parse of the same URL when /api/generate actually fetches it. */
function parseSource(raw: string): Source | null {
  const trimmed = raw.trim();
  if (!trimmed || /\s/.test(trimmed)) return null;
  const withScheme = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
  let url: URL;
  try {
    url = new URL(withScheme);
  } catch {
    return null;
  }
  if (!url.hostname.includes(".")) return null;

  const slug = url.pathname.split("/").filter(Boolean).pop();
  const title = slug
    ? slug.replace(/[-_]/g, " ").replace(/\.\w+$/, "").replace(/\b\w/g, (c) => c.toUpperCase())
    : url.hostname.replace(/^www\./, "");

  return {
    id: nextId(),
    url: url.toString(),
    host: url.hostname,
    title: title.length > 46 ? `${title.slice(0, 46)}…` : title,
    path: url.hostname.replace(/^www\./, "") + (url.pathname === "/" ? "" : url.pathname),
  };
}

const stamp = () =>
  new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

type Phase = "idle" | "loading" | "preview" | "error";

export default function App() {
  const [sources, setSources] = useState<Source[]>([]);
  const [template, setTemplate] = useState<TemplateId>("launch");
  const [customTemplate, setCustomTemplate] = useState("");
  const [prompt, setPrompt] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [posts, setPosts] = useState<UIPost[]>([]);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [errorMessage, setErrorMessage] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [logOpen, setLogOpen] = useState(true);

  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const addInputRef = useRef<HTMLInputElement>(null);

  const clearTimers = () => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  };
  useEffect(() => clearTimers, []);

  const pushLog = useCallback((text: string, tone: LogTone = "default") => {
    setLog((prev) => [...prev, { id: nextId(), text, tone, time: stamp() }]);
  }, []);

  const addSource = (raw: string): boolean => {
    const parsed = parseSource(raw);
    if (!parsed) return false;
    setSources((prev) => [...prev, parsed]);
    pushLog(`+ source ${parsed.path}`, "dim");
    return true;
  };

  const removeSource = (id: string) => {
    const gone = sources.find((s) => s.id === id);
    if (gone) pushLog(`- source ${gone.path}`, "dim");
    setSources((prev) => prev.filter((s) => s.id !== id));
  };

  const templateLabel = useMemo(
    () => TEMPLATES.find((t) => t.id === template)?.label ?? "Custom",
    [template]
  );

  const generate = async () => {
    if (sources.length === 0 || phase === "loading") return;
    clearTimers();
    setPosts([]);
    setErrorMessage("");
    setPhase("loading");

    // Lines we already know client-side play immediately while the real
    // request is in flight; anything that depends on the actual response
    // (which platforms came back, how many) plays after it resolves.
    const knownSteps: { text: string; tone: LogTone }[] = [
      ...sources.map(
        (s, i): { text: string; tone: LogTone } => ({
          text: `Fetching source ${i + 1}/${sources.length}… ${s.host}`,
          tone: "dim",
        })
      ),
      { text: `Applying template: ${templateLabel}`, tone: "default" },
      ...(prompt.trim()
        ? [{ text: `Steering: "${prompt.trim().slice(0, 44)}"`, tone: "dim" as LogTone }]
        : []),
      { text: "Talking to generation service…", tone: "default" },
    ];
    knownSteps.forEach((step, i) => {
      timers.current.push(setTimeout(() => pushLog(step.text, step.tone), 200 + i * 260));
    });

    try {
      const { bundle } = await generatePosts({
        sources: sources.map((s) => ({ url: s.url })),
        templateId: template,
        customTemplate: template === "custom" ? customTemplate : undefined,
        prompt: prompt.trim() || undefined,
      });

      clearTimers();
      bundle.posts.forEach((post) => {
        pushLog(`Generating ${PLATFORMS[post.platform].name} variant…`, "default");
      });
      pushLog(`${bundle.posts.length} drafts ready — awaiting approval`, "accent");
      setPosts(bundle.posts.map((post) => ({ ...post, variantIndex: 0, loading: false })));
      setPhase("preview");
    } catch (err) {
      clearTimers();
      const message =
        err instanceof ApiError ? err.message : "Something went wrong generating drafts.";
      pushLog(`Generation failed: ${message}`, "error");
      setErrorMessage(message);
      setPhase("error");
    }
  };

  /* keep log writes outside the state updater — updaters must stay pure */
  const approve = async (id: string) => {
    const target = posts.find((p) => p.id === id);
    if (!target || target.status === "posted") return;
    try {
      const { post } = await approvePost({
        postId: target.id,
        platform: target.platform,
        text: target.text,
      });
      pushLog(`Posted to ${PLATFORMS[target.platform].name} ✓`, "ok");
      setPosts((prev) => prev.map((p) => (p.id === id ? { ...p, status: post.status } : p)));
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Approve failed.";
      pushLog(`Approve failed for ${PLATFORMS[target.platform].name}: ${message}`, "error");
    }
  };

  const regenerate = async (id: string) => {
    const target = posts.find((p) => p.id === id);
    if (!target) return;
    pushLog(`Regenerating ${PLATFORMS[target.platform].name} variant…`, "default");
    setPosts((prev) => prev.map((p) => (p.id === id ? { ...p, loading: true } : p)));

    try {
      const { post, variantIndex } = await regeneratePost({
        postId: target.id,
        platform: target.platform,
        templateId: template,
        customTemplate: template === "custom" ? customTemplate : undefined,
        variantIndex: target.variantIndex,
      });
      setPosts((prev) =>
        prev.map((p) => (p.id === id ? { ...p, text: post.text, variantIndex, loading: false } : p))
      );
      pushLog(`${PLATFORMS[target.platform].name} draft updated`, "dim");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Regenerate failed.";
      setPosts((prev) => prev.map((p) => (p.id === id ? { ...p, loading: false } : p)));
      pushLog(`Regenerate failed for ${PLATFORMS[target.platform].name}: ${message}`, "error");
    }
  };

  const focusAddSource = () => {
    setSidebarOpen(true);
    setTimeout(() => addInputRef.current?.focus(), 0);
  };

  const hasSources = sources.length > 0;

  return (
    <div className="flex h-full bg-canvas text-ink">
      {sidebarOpen ? (
        <Sidebar
          sources={sources}
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
          {!logOpen && (
            <IconButton label="Show activity panel" onClick={() => setLogOpen(true)}>
              <PanelRight />
            </IconButton>
          )}
        </header>

        <div className="shrink-0 border-b border-line px-5 py-3">
          <div className="mx-auto w-full max-w-[680px]">
            <TemplateTabs value={template} onChange={setTemplate} />
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
                <ErrorState message={errorMessage} onRetry={generate} />
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
                  <PostCard key={p.id} post={p} onApprove={approve} onRegenerate={regenerate} />
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
                    : "Add a source first"
                }
                className="min-w-0 flex-1 bg-transparent text-[14px] text-ink outline-none placeholder:text-ink-faint"
              />
              <button
                type="button"
                onClick={() => void generate()}
                disabled={!hasSources || phase === "loading"}
                className={`flex shrink-0 items-center gap-1.5 rounded-lg border px-3 py-1.5 text-[13px] transition-colors ${
                  !hasSources || phase === "loading"
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
              Drafts are previews. Nothing publishes until you approve each card.
            </p>
          </div>
        </div>
      </main>

      {logOpen && (
        <LogPanel entries={log} running={phase === "loading"} onCollapse={() => setLogOpen(false)} />
      )}
    </div>
  );
}
