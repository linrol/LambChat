/**
 * Session management hooks
 */

import { useState, useCallback, useEffect, useRef } from "react";
import { useInView } from "react-intersection-observer";
import { sessionApi, type BackendSession } from "../services/api";

const PAGE_SIZE = 20;

// ─── Paginated session list with auto-fill (sidebar) ─────────────────

interface UseSessionListReturn {
  sessions: BackendSession[];
  isLoading: boolean;
  isLoadingMore: boolean;
  hasMore: boolean;
  error: string | null;
  loadSessions: (reset?: boolean) => Promise<void>;
  loadMoreSessions: () => void;
  setSessions: React.Dispatch<React.SetStateAction<BackendSession[]>>;
  scrollContainerRef: React.RefObject<HTMLDivElement | null>;
  loadMoreRef: React.RefCallback<HTMLElement>;
}

export function useSessionList(
  refreshKey?: number,
  isProjectsCollapsed?: boolean,
  setIsProjectsCollapsed?: (collapsed: boolean) => void,
): UseSessionListReturn {
  const [sessions, setSessions] = useState<BackendSession[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [skip, setSkip] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const scrollContainerRef = useRef<HTMLDivElement | null>(null);

  const { ref: loadMoreRef, inView } = useInView({
    threshold: 0.1,
  });

  const loadSessions = async (reset = false) => {
    if (!reset && (isLoading || isLoadingMore)) return;
    if (!reset && !hasMore) return;

    if (reset) {
      setIsLoading(true);
      setSkip(0);
    } else {
      setIsLoadingMore(true);
    }
    setError(null);

    try {
      const currentSkip = reset ? 0 : skip;
      const response = await sessionApi.list({
        limit: PAGE_SIZE,
        skip: currentSkip,
        status: "active",
      });

      const newSessions =
        "sessions" in response
          ? response.sessions
          : Array.isArray(response)
            ? response
            : [];
      const newHasMore = "has_more" in response ? response.has_more : false;

      if (reset) {
        setSessions(newSessions);
      } else {
        setSessions((prev) => [...prev, ...newSessions]);
      }
      setSkip(currentSkip + newSessions.length);
      setHasMore(newHasMore);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sessions");
    } finally {
      setIsLoading(false);
      setIsLoadingMore(false);
    }
  };

  const loadMoreSessions = useCallback(() => {
    if (hasMore && !isLoadingMore && !isLoading) {
      loadSessions(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasMore, isLoadingMore, isLoading]);

  // Infinite scroll via sentinel
  useEffect(() => {
    if (inView && hasMore && !isLoadingMore) {
      loadMoreSessions();
    }
  }, [inView, hasMore, isLoadingMore, loadMoreSessions]);

  // Auto-fill sidebar: keep loading or expand projects until container is filled
  const loadSessionsRef = useRef(loadSessions);
  loadSessionsRef.current = loadSessions;

  useEffect(() => {
    if (isLoading || isLoadingMore) return;
    const container = scrollContainerRef.current;
    if (!container || container.scrollHeight > container.clientHeight) return;

    if (hasMore) {
      loadSessionsRef.current(false);
    } else if (isProjectsCollapsed && setIsProjectsCollapsed) {
      const hasProjectSessions = sessions.some((s) => s.metadata?.project_id);
      if (hasProjectSessions) {
        setIsProjectsCollapsed(false);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessions, hasMore, isLoading, isLoadingMore, isProjectsCollapsed]);

  // Initial load on mount / refresh
  useEffect(() => {
    loadSessions(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey]);

  return {
    sessions,
    isLoading,
    isLoadingMore,
    hasMore,
    error,
    loadSessions,
    loadMoreSessions,
    setSessions,
    scrollContainerRef,
    loadMoreRef,
  };
}

// ─── Single session operations ──────────────────────────────────────

interface UseSessionReturn {
  currentSession: BackendSession | null;
  isLoading: boolean;
  error: string | null;
  loadSession: (sessionId: string) => Promise<BackendSession | null>;
  deleteSession: (sessionId: string) => Promise<void>;
  switchSession: (sessionId: string | null) => void;
  clearError: () => void;
}

export function useSession(): UseSessionReturn {
  const [currentSession, setCurrentSession] = useState<BackendSession | null>(
    null,
  );
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSession = useCallback(
    async (sessionId: string): Promise<BackendSession | null> => {
      setIsLoading(true);
      setError(null);

      try {
        const session = await sessionApi.get(sessionId);
        if (session) {
          setCurrentSession(session);
        }
        return session;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load session");
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  const deleteSession = useCallback(
    async (sessionId: string) => {
      try {
        await sessionApi.delete(sessionId);
        if (currentSession?.id === sessionId) {
          setCurrentSession(null);
        }
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to delete session",
        );
      }
    },
    [currentSession],
  );

  const switchSession = useCallback(
    (sessionId: string | null) => {
      if (sessionId) {
        loadSession(sessionId);
      } else {
        setCurrentSession(null);
      }
    },
    [loadSession],
  );

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    currentSession,
    isLoading,
    error,
    loadSession,
    deleteSession,
    switchSession,
    clearError,
  };
}

// ─── Message history loader ─────────────────────────────────────────

interface UseMessageHistoryReturn {
  loadHistory: (sessionId: string) => Promise<void>;
  isLoading: boolean;
  error: string | null;
}

export function useMessageHistory(
  onHistoryLoaded: (session: BackendSession) => void,
): UseMessageHistoryReturn {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = useCallback(
    async (sessionId: string) => {
      setIsLoading(true);
      setError(null);

      try {
        const session = await sessionApi.get(sessionId);
        if (session) {
          onHistoryLoaded(session);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load history");
      } finally {
        setIsLoading(false);
      }
    },
    [onHistoryLoaded],
  );

  return {
    loadHistory,
    isLoading,
    error,
  };
}
