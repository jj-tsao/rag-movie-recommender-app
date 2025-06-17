import { useEffect, useState, useRef, useMemo } from "react";
import type { FilterSettings } from "../types/types";
import { streamChatResponse, logFinalRecs } from "../api";
import { getSessionId } from "../utils/session";
import { getDeviceInfo } from "../utils/detectDevice"
import ReactMarkdown from "react-markdown";
import MovieCard from "./MovieCard";
import { parseMarkdown } from "../utils/parseMarkdown";
import type { ParsedMovie } from "../utils/parseMarkdown";

interface Props {
  question: string;
  filters: FilterSettings;
  onDoneStreaming?: () => void;
  onStreamingStatusChange?: (isStreaming: boolean) => void;
}

export default function ChatBox({
  question,
  filters,
  onDoneStreaming,
  onStreamingStatusChange,
}: Props) {
  const [intro, setIntro] = useState("");
  const [outro, setOutro] = useState("");
  const [cards, setCards] = useState<ParsedMovie[]>([]);
  const [chatResponse, setChatResponse] = useState("");
  const [loading, setLoading] = useState(false);

  const queryIdRef = useRef(`${getSessionId()}_${Date.now()}`);
  const onDoneStreamingRef = useRef(onDoneStreaming);
  const onStreamingStatusChangeRef = useRef(onStreamingStatusChange);
  const currentCardsRef = useRef<ParsedMovie[]>([]);
  const introCapturedRef = useRef(false);
  const finalBufferRef = useRef("");
  const hasStartedRef = useRef(false); // ✅ Prevent duplicate stream calls

  const deviceInfo = useMemo(() => getDeviceInfo(), []);

  useEffect(() => {
    onDoneStreamingRef.current = onDoneStreaming;
    onStreamingStatusChangeRef.current = onStreamingStatusChange;
  }, [onDoneStreaming, onStreamingStatusChange]);

  const filtersRef = useRef(filters);
  const questionRef = useRef(question);

  useEffect(() => {
    filtersRef.current = filters;
  }, [filters]);

  useEffect(() => {
    questionRef.current = question;
  }, [question]);

  useEffect(() => {
    if (!question.trim()) return;
    if (hasStartedRef.current) return;
    hasStartedRef.current = true;

    setIntro("");
    setOutro("");
    setCards([]);
    setChatResponse("");
    setLoading(true);
    currentCardsRef.current = [];
    introCapturedRef.current = false;
    let localBuffer = "";
    let mode: "unknown" | "recommendation" | "chat" = "unknown";

    onStreamingStatusChangeRef.current?.(true);

    streamChatResponse(
      {
        question: questionRef.current,
        ...filtersRef.current,
        session_id: getSessionId(),
        query_id: queryIdRef.current,
        device_info: deviceInfo,
      },
      (chunk: string) => {
        localBuffer += chunk;
        finalBufferRef.current = localBuffer;

        if (mode === "unknown") {
          const match = localBuffer.match(/\[\[MODE:(recommendation|chat)\]\]/);
          if (match) {
            mode = match[1] as "recommendation" | "chat";
            localBuffer = localBuffer.replace(match[0], "");
          } else {
            return;
          }
        }

        if (mode === "chat") {
          // Ignore all chunks until tag is detected
          if (!introCapturedRef.current) {
            // Start streaming cleanly after [[MODE:chat]] tag
            const tagIndex = localBuffer.indexOf("[[MODE:chat]]");
            if (tagIndex !== -1) {
              const afterTag = localBuffer.slice(
                tagIndex + "[[MODE:chat]]".length
              );
              setChatResponse(afterTag);
              introCapturedRef.current = true;
            }
          } else {
            setChatResponse((prev) => prev + chunk);
          }
          return;
        }

        if (!introCapturedRef.current) {
          const endIdx = localBuffer.indexOf("<!-- END_INTRO -->");
          if (endIdx !== -1) {
            const introText = localBuffer
              .slice(0, endIdx)
              .replace(/\[\[.*?\]\]/g, "")
              .trim();
            setIntro((prev) => (prev ? prev : introText));
            localBuffer = localBuffer.slice(
              endIdx + "<!-- END_INTRO -->".length
            );
            introCapturedRef.current = true;
          } else {
            return;
          }
        }

        if (!localBuffer.includes("<!-- END_MOVIE -->")) return;

        const movieBlocks = localBuffer.split(/<!--\s*END_MOVIE\s*-->/g);
        if (movieBlocks.length > 1) {
          const completed = movieBlocks.slice(0, -1);
          localBuffer = movieBlocks[movieBlocks.length - 1];

          const newCards = parseMarkdown(
            completed.join("<!-- END_MOVIE -->")
          ).filter(
            (movie) =>
              movie &&
              !currentCardsRef.current.some((c) => c.title === movie.title) &&
              movie.why.length > 60 &&
              movie.why.split(/[.!?]/).filter(Boolean).length >= 2
          );

          if (newCards.length > 0) {
            currentCardsRef.current = [...currentCardsRef.current, ...newCards];
            setCards([...currentCardsRef.current]);
          }
        }
      }
    ).finally(() => {
      const potentialOutro = finalBufferRef.current.trim();
      if (
        !potentialOutro.includes("###") &&
        !potentialOutro.includes("WHY_YOU_MIGHT_ENJOY_IT") &&
        potentialOutro.length > 50
      ) {
        setOutro(potentialOutro);
      }

      if (currentCardsRef.current.length > 0) {
        logFinalRecs({
          queryId: queryIdRef.current,
          finalRecs: currentCardsRef.current.map((movie) => ({
            media_id: movie.mediaId,
            why: movie.why,
          })),
        });
      }

      setLoading(false);
      onStreamingStatusChangeRef.current?.(false);
      onDoneStreamingRef.current?.();
    });
  }, [question, deviceInfo]);

  return (
    <div className="space-y-4">
      {chatResponse ? (
        <div className="prose prose-invert max-w-none">
          <ReactMarkdown>{chatResponse}</ReactMarkdown>
        </div>
      ) : (
        <>
          {intro && (
            <div className="prose prose-invert max-w-none min-h-[6rem]">
              <ReactMarkdown>{"✨  " + intro}</ReactMarkdown>
            </div>
          )}

          {cards.length > 0 && (
            <div className="space-y-4">
              {cards.map((movie, i) => (
                <MovieCard key={movie.title + i} movie={movie} />
              ))}
            </div>
          )}

          {outro && (
            <div className="prose prose-invert max-w-none min-h-[6rem]">
              <ReactMarkdown>{outro}</ReactMarkdown>
            </div>
          )}
        </>
      )}

      {loading && (
        <div className="text-sm text-zinc-400">
          Curating your recommendations...
        </div>
      )}
    </div>
  );
}
