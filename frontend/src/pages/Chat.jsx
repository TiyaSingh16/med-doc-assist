import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { useParams, useNavigate } from "react-router-dom";
import { askQuestion } from "../api/chat";
import { getDocument } from "../api/documents";
import { getChatHistory } from "../api/chat";

export default function Chat() {
  const { documentId } = useParams();
  const navigate = useNavigate();
  const [document, setDocument] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef(null);

  useEffect(() => {
  getDocument(documentId)
    .then((res) => setDocument(res.data))
    .catch(() => setError("Could not load document"));

  getChatHistory(documentId)
    .then((res) => {
      const loaded = res.data.map((m) => ({
        role: m.role,
        text: m.content,
        chunksUsed: m.chunks_used,
      }));
      setMessages(loaded);
    })
    .catch(() => {
      // no history yet is fine — just start with an empty conversation
    });
}, [documentId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (e) => {
  e.preventDefault();
  const question = input.trim();
  if (!question || sending) return;

  setMessages((prev) => [...prev, { role: "user", text: question }]);
  setInput("");
  setError("");
  setSending(true);

  // Add an empty assistant message that we'll fill in as tokens arrive
  setMessages((prev) => [...prev, { role: "assistant", text: "", chunksUsed: null }]);

  try {
    const token = localStorage.getItem("token");
    const response = await fetch(
      `${import.meta.env.VITE_API_URL}/chat/query/stream`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ document_id: documentId, question }),
      }
    );

    if (!response.ok) {
      throw new Error("Stream request failed");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE messages are separated by double newlines
      const parts = buffer.split("\n\n");
      buffer = parts.pop(); // keep the last (possibly incomplete) chunk in the buffer

      for (const part of parts) {
        if (!part.startsWith("data: ")) continue;
        const jsonStr = part.slice(6);
        const event = JSON.parse(jsonStr);

        if (event.type === "token") {
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            updated[updated.length - 1] = { ...last, text: last.text + event.content };
            return updated;
          });
        } else if (event.type === "done") {
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            updated[updated.length - 1] = { ...last, chunksUsed: event.chunks_used };
            return updated;
          });
        } else if (event.type === "error") {
          setError(event.content);
        }
      }
    }
  } catch (err) {
    setError("Failed to get an answer");
  } finally {
    setSending(false);
  }
};

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <header className="bg-white border-b border-slate-200 px-8 py-4 flex items-center gap-4">
        <button
          onClick={() => navigate("/dashboard")}
          className="text-sm text-slate-500 hover:text-slate-800 transition"
        >
          ← Back
        </button>
        <h1 className="text-sm font-medium text-slate-800 truncate">
          {document ? document.filename : "Loading..."}
        </h1>
      </header>

      <main className="flex-1 max-w-2xl w-full mx-auto px-6 py-6 flex flex-col">
        <div className="flex-1 space-y-4 overflow-y-auto mb-4">
          {messages.length === 0 && (
            <p className="text-sm text-slate-400 text-center mt-12">
              Ask a question about this document to get started.
            </p>
          )}

          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[80%] px-4 py-2 rounded-2xl text-sm ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white rounded-br-sm"
                    : "bg-white border border-slate-200 text-slate-800 rounded-bl-sm"
                }`}
              >
                {msg.role === "assistant" ? (
                    <div className="prose prose-sm max-w-none prose-p:my-1 prose-strong:text-slate-900">
                        <ReactMarkdown>{msg.text}</ReactMarkdown>
                    </div>
                ) : (
                msg.text
                )}
                {msg.role === "assistant" && (
                  <p className="text-xs text-slate-400 mt-1">
                    Based on {msg.chunksUsed} document excerpt{msg.chunksUsed !== 1 ? "s" : ""}
                  </p>
                )}
              </div>
            </div>
          ))}

          {sending && (
            <div className="flex justify-start">
              <div className="bg-white border border-slate-200 px-4 py-2 rounded-2xl text-sm text-slate-400">
                Thinking...
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {error && <p className="text-sm text-red-600 mb-2">{error}</p>}

        <form onSubmit={handleSend} className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question about this document..."
            disabled={sending}
            className="flex-1 px-4 py-2 border border-slate-300 rounded-full focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            className="bg-blue-600 text-white px-5 py-2 rounded-full text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition"
          >
            Send
          </button>
        </form>
      </main>
    </div>
  );
}