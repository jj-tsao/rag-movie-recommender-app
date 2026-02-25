export function parseSseFrame(raw: string): { eventType: string; data: string } | null {
  if (!raw || raw.startsWith(":")) {
    return null;
  }

  const lines = raw.split(/\r?\n/);
  let eventType = "message";
  const dataLines: string[] = [];

  for (const line of lines) {
    if (!line.trim()) continue;
    if (line.startsWith(":")) continue;
    if (line.startsWith("event:")) {
      eventType = line.slice(6).trim();
      continue;
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
      continue;
    }
  }

  return { eventType, data: dataLines.join("\n") };
}

export function safeJsonParse<T>(value: string): T | null {
  try {
    return JSON.parse(value) as T;
  } catch {
    return null;
  }
}

export async function consumeSseStream<T>(
  body: ReadableStream<Uint8Array>,
  parseEvent: (raw: string) => T | null,
  onEvent: (event: T) => void,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sepIndex = buffer.indexOf("\n\n");
    while (sepIndex !== -1) {
      const rawEvent = buffer.slice(0, sepIndex);
      buffer = buffer.slice(sepIndex + 2);
      const parsed = parseEvent(rawEvent);
      if (parsed) {
        onEvent(parsed);
      }
      sepIndex = buffer.indexOf("\n\n");
    }
  }

  buffer += decoder.decode();
  if (buffer.trim()) {
    const parsed = parseEvent(buffer.trimEnd());
    if (parsed) {
      onEvent(parsed);
    }
  }
}