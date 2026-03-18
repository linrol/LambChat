import { memo, useMemo } from "react";
import { MarkdownContent } from "../../chat/ChatMessage/MarkdownContent";

interface MarkdownRendererProps {
  content: string;
  t: (key: string, options?: Record<string, unknown>) => string;
}

// Reuse MarkdownContent to avoid maintaining two separate markdown renderers
const MarkdownRenderer = memo(function MarkdownRenderer({
  content,
  t,
}: MarkdownRendererProps) {
  // Limit content for very large files
  const displayContent = useMemo(() => {
    const maxChars = 100000;
    if (content.length > maxChars) {
      return (
        content.slice(0, maxChars) + `\n\n${t("documents.fileTooLargeChars")}`
      );
    }
    return content;
  }, [content, t]);

  return (
    <div className="markdown-preview overflow-auto h-full p-4 sm:p-6 lg:p-8">
      <MarkdownContent content={displayContent} />
    </div>
  );
});

export default MarkdownRenderer;
