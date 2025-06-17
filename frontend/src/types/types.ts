export type ChatRequest = {
  question: string;
  media_type: "movie" | "tv";
  genres: string[];
  providers: string[];
  year_range: [number, number];
  session_id: string;
  query_id: string;
  device_info?: {
    device_type: string;
    platform: string;
    user_agent: string;
  };
};

export type FilterSettings = Omit<
  ChatRequest,
  "question" | "session_id" | "query_id"
>;
