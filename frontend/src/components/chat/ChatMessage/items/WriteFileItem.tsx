import { memo } from "react";
import { clsx } from "clsx";
import { FilePlus } from "lucide-react";
import { useTranslation } from "react-i18next";
import { CollapsiblePill } from "../../../common";
import { extractText } from "./toolUtils";

const WriteFileItem = memo(function WriteFileItem({
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
  const filePath = (args.file_path as string) || "";
  const fileName = filePath.split("/").pop() || filePath;
  const content = (args.content as string) || "";

  const canExpand = !!content || !!result;

  return (
    <CollapsiblePill
      status={isPending ? "loading" : success ? "success" : "error"}
      icon={<FilePlus size={12} className="shrink-0 opacity-50" />}
      label={`${t("chat.message.toolWrite")} ${fileName || ""}`}
      variant="tool"
      expandable={canExpand}
    >
      {canExpand && (
        <div className="mt-2 ml-4 pl-3 border-l-2 border-stone-200/60 dark:border-stone-700/50">
          <div className="flex items-center gap-2 mb-2 px-2 py-1.5 rounded-md bg-stone-100 dark:bg-stone-800 text-xs text-stone-500 dark:text-stone-400 font-mono">
            <span className="truncate">{filePath}</span>
          </div>
          {content && (
            <pre
              className={clsx(
                "text-xs max-h-64 overflow-y-auto rounded-md p-3",
                "bg-stone-50 dark:bg-stone-900 border border-stone-200/60 dark:border-stone-700/50",
                "text-stone-700 dark:text-stone-300 whitespace-pre-wrap break-words font-mono",
              )}
            >
              {content}
            </pre>
          )}
          {result &&
            (() => {
              const text = extractText(result);
              return text ? (
                <pre className="text-xs text-stone-500 dark:text-stone-400 whitespace-pre-wrap break-words mt-1">
                  {text}
                </pre>
              ) : null;
            })()}
        </div>
      )}
    </CollapsiblePill>
  );
});

export { WriteFileItem };
