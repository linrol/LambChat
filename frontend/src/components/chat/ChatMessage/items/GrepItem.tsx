import { memo, useMemo } from "react";
import { clsx } from "clsx";
import { Search, FileText } from "lucide-react";
import { useTranslation } from "react-i18next";
import { CollapsiblePill } from "../../../common";
import { extractText } from "./toolUtils";

const GrepItem = memo(function GrepItem({
  args,
  result,
  success,
  isPending,
}: {
  args: Record<string, unknown>;
  result?: string | Record<string, unknown>;
  success?: boolean;
  isPending?: boolean;
}) {
  const { t } = useTranslation();
  const pattern = (args.pattern as string) || "";
  const searchPath = (args.path as string) || "";
  const glob = (args.glob as string) || "";
  const outputMode = (args.output_mode as string) || "files_with_matches";

  const parsedResult = useMemo(() => {
    if (!result) return { files: [] as string[], lines: [] as string[] };
    const raw = extractText(result);
    try {
      const obj = JSON.parse(raw);
      if (Array.isArray(obj)) {
        const files: string[] = [];
        const lines: string[] = [];
        for (const item of obj) {
          if (typeof item === "string") {
            files.push(item);
          } else if (item && typeof item === "object") {
            const file = (item as Record<string, unknown>).file as string;
            if (file) files.push(file);
            const matches = (item as Record<string, unknown>).matches;
            if (Array.isArray(matches)) {
              for (const m of matches) {
                const match = m as Record<string, unknown>;
                lines.push(`${file}:${match.line ?? ""}:${match.text ?? ""}`);
              }
            }
          }
        }
        return { files, lines };
      }
    } catch {
      // 非 JSON，按行解析 ripgrep 风格输出
    }

    const lines: string[] = raw.split("\n").filter(Boolean);
    const files = [
      ...new Set(lines.map((l) => l.split(":")[0]).filter(Boolean)),
    ];
    return { files, lines };
  }, [result]);

  const canExpand =
    !!pattern || parsedResult.files.length > 0 || parsedResult.lines.length > 0;

  const highlightRe = useMemo(() => {
    if (!pattern) return null;
    try {
      return new RegExp(
        `(${pattern.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`,
        "gi",
      );
    } catch {
      return null;
    }
  }, [pattern]);

  const highlightPattern = (text: string) => {
    if (!highlightRe) return text;
    try {
      const parts = text.split(highlightRe);
      return parts.map((part, i) =>
        i % 2 === 1 ? (
          <mark
            key={i}
            className="bg-yellow-200 dark:bg-yellow-700/60 text-inherit rounded-sm px-0.5"
          >
            {part}
          </mark>
        ) : (
          part
        ),
      );
    } catch {
      return text;
    }
  };

  return (
    <CollapsiblePill
      status={isPending ? "loading" : success ? "success" : "error"}
      icon={<Search size={12} className="shrink-0 opacity-50" />}
      label={`${t("chat.message.toolSearch")} ${pattern || ""}`}
      variant="tool"
      expandable={canExpand}
    >
      {canExpand && (
        <div className="mt-2 ml-4 pl-3 border-l-2 border-stone-200/60 dark:border-stone-700/50">
          <div className="flex items-center gap-2 mb-2 px-2 py-1.5 rounded-md bg-stone-100 dark:bg-stone-800 text-xs text-stone-500 dark:text-stone-400 font-mono flex-wrap">
            <span className="text-violet-600 dark:text-violet-400 font-semibold">
              {pattern}
            </span>
            {searchPath && (
              <span className="text-stone-400 dark:text-stone-500">
                {t("chat.message.toolInPath", { path: searchPath })}
              </span>
            )}
            {glob && (
              <span className="shrink-0 px-1.5 py-0.5 rounded bg-stone-200 dark:bg-stone-700 text-stone-600 dark:text-stone-300">
                {glob}
              </span>
            )}
          </div>
          {parsedResult.files.length > 0 && (
            <div className="mb-2">
              <div className="text-xs text-stone-400 dark:text-stone-500 mb-1">
                {t("chat.message.toolFileCount", {
                  count: parsedResult.files.length,
                })}
              </div>
              <div className="flex flex-wrap gap-1">
                {parsedResult.files.slice(0, 10).map((f, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-stone-100 dark:bg-stone-800 text-xs text-stone-600 dark:text-stone-300 font-mono"
                  >
                    <FileText size={10} className="shrink-0 opacity-40" />
                    {f.split("/").pop() || f}
                  </span>
                ))}
                {parsedResult.files.length > 10 && (
                  <span className="text-xs text-stone-400 dark:text-stone-500 px-1">
                    {t("chat.message.toolMoreFiles", {
                      count: parsedResult.files.length - 10,
                    })}
                  </span>
                )}
              </div>
            </div>
          )}
          {outputMode === "content" && parsedResult.lines.length > 0 && (
            <pre
              className={clsx(
                "text-xs max-h-48 overflow-y-auto rounded-md p-2.5",
                "bg-stone-50 dark:bg-stone-900 border border-stone-200/60 dark:border-stone-700/50",
                "text-stone-700 dark:text-stone-300 whitespace-pre-wrap break-words font-mono",
              )}
            >
              {parsedResult.lines.slice(0, 50).map((line, i) => (
                <div
                  key={i}
                  className="hover:bg-stone-100 dark:hover:bg-stone-800/50 rounded px-1 -mx-1"
                >
                  {highlightPattern(line)}
                </div>
              ))}
              {parsedResult.lines.length > 50 && (
                <div className="text-stone-400 dark:text-stone-500 mt-1">
                  {t("chat.message.toolMoreLines", {
                    count: parsedResult.lines.length - 50,
                  })}
                </div>
              )}
            </pre>
          )}
          {result &&
            (() => {
              const text = extractText(result);
              return text &&
                parsedResult.lines.length === 0 &&
                parsedResult.files.length === 0 ? (
                <pre className="text-xs text-stone-500 dark:text-stone-400 whitespace-pre-wrap break-words">
                  {text}
                </pre>
              ) : null;
            })()}
        </div>
      )}
    </CollapsiblePill>
  );
});

export { GrepItem };
