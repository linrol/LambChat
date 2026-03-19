import { ExternalLink } from "lucide-react";
import { useTranslation } from "react-i18next";
import { MarkdownContent } from "../MarkdownContent";
import type { McpContentBlock, McpMultiModalResult } from "./toolUtils";
import { isMarkdownText, extractText } from "./toolUtils";

// 单个 MCP content block 的预览
function McpBlockPreview({ block }: { block: McpContentBlock }) {
  const { t } = useTranslation();

  if (block.type === "image") {
    const src = block.base64
      ? `data:${block.mime_type || "image/png"};base64,${block.base64}`
      : block.url || "";
    return (
      <img
        src={src}
        alt={t("chat.message.toolOutput")}
        className="max-w-full max-h-48 rounded-md border border-stone-200 dark:border-stone-700 cursor-pointer hover:opacity-80 transition-opacity"
        onClick={() => src && window.open(src, "_blank")}
      />
    );
  }

  if (block.type === "file") {
    const url = block.url || "";
    const fileName = url.split("/").pop() || t("chat.message.toolFile");
    return (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-stone-100 dark:bg-stone-800 text-xs text-stone-600 dark:text-stone-300 hover:bg-stone-200 dark:hover:bg-stone-700 transition-colors border border-stone-200 dark:border-stone-700"
      >
        <ExternalLink size={12} />
        {fileName}
      </a>
    );
  }

  if (block.text) {
    return (
      <pre className="text-xs text-stone-600 dark:text-stone-300 whitespace-pre-wrap break-words">
        {block.text}
      </pre>
    );
  }

  return null;
}

// 工具结果渲染组件 — 支持 str / dict / MCP 多模态
export function ToolResultContent({
  result,
}: {
  result?: string | Record<string, unknown>;
}) {
  const textContent = extractText(result);

  if (
    typeof result === "object" &&
    result !== null &&
    "blocks" in result &&
    Array.isArray((result as McpMultiModalResult).blocks)
  ) {
    const mcp = result as McpMultiModalResult;
    return (
      <div className="space-y-1.5">
        {mcp.text && (
          <pre className="text-xs text-stone-600 dark:text-stone-300 whitespace-pre-wrap break-words">
            {isMarkdownText(mcp.text) ? (
              <MarkdownContent content={mcp.text} />
            ) : (
              mcp.text
            )}
          </pre>
        )}
        <div className="flex flex-wrap gap-2">
          {(mcp.blocks || []).map((block, i) => (
            <McpBlockPreview key={i} block={block} />
          ))}
        </div>
      </div>
    );
  }

  if (textContent) {
    return isMarkdownText(textContent) ? (
      <div className="text-xs text-stone-600 dark:text-stone-300 max-h-32 overflow-y-auto">
        <MarkdownContent content={textContent} />
      </div>
    ) : (
      <pre className="text-xs text-stone-600 dark:text-stone-300 max-h-32 overflow-y-auto whitespace-pre-wrap break-words">
        {textContent}
      </pre>
    );
  }

  return (
    <pre className="text-xs text-stone-600 dark:text-stone-300 max-h-32 overflow-y-auto whitespace-pre-wrap break-words">
      {JSON.stringify(result, null, 2)}
    </pre>
  );
}
