export function getSessionId(): string {
  let sessionId = localStorage.getItem("reelixSessionId");
  if (!sessionId) {
    sessionId = crypto.randomUUID();
    localStorage.setItem("reelixSessionId", sessionId);
  }
  return sessionId;
}
