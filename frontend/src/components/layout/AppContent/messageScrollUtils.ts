type ScrollBehaviorMode = "auto" | "smooth";

interface VirtuosoLike {
  scrollTo: (args: { top: number; behavior: ScrollBehaviorMode }) => void;
}

interface ScrollerLike {
  scrollTop: number;
  clientHeight: number;
  scrollHeight: number;
}

interface FooterLike {
  scrollIntoView: (args?: { behavior?: ScrollBehaviorMode }) => void;
}

interface StartVirtuosoScrollToBottomOptions {
  virtuoso?: VirtuosoLike | null;
  scroller?: ScrollerLike | null;
  footer?: FooterLike | null;
  intervalMs?: number;
  maxAttempts?: number;
}

export function startVirtuosoScrollToBottom({
  virtuoso,
  scroller,
  footer,
  intervalMs = 30,
  maxAttempts = 20,
}: StartVirtuosoScrollToBottomOptions): () => void {
  if (!virtuoso || !scroller) {
    footer?.scrollIntoView({ behavior: "auto" });
    return () => undefined;
  }

  let attempts = 0;
  const scroll = () => {
    virtuoso.scrollTo({
      top: Number.MAX_SAFE_INTEGER,
      behavior: "auto",
    });
  };

  scroll();

  const timer = setInterval(() => {
    const isAtBottom =
      scroller.scrollTop + scroller.clientHeight >= scroller.scrollHeight - 1;

    if (isAtBottom || attempts >= maxAttempts) {
      clearInterval(timer);
      return;
    }

    attempts += 1;
    scroll();
  }, intervalMs);

  return () => clearInterval(timer);
}
