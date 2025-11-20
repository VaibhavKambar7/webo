"use client";

import { useState, useRef, useEffect } from "react";
import {
  Search,
  Loader,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Layers,
  ArrowUp,
  StopCircle,
  Moon,
  Sun,
} from "lucide-react";
import ReactMarkdown from "react-markdown";

interface Source {
  title: string;
  url: string;
  favicon?: string;
}

interface ReActAction {
  tool: string;
  input?: string;
}

interface ReActStep {
  thought: string;
  action: ReActAction;
  observation?: string;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  thinkingSteps?: ReActStep[];
  subQueries?: string[];
  status?: string;
  error?: string;
  jobId?: string;
  isExpanded?: boolean;
}

const getFaviconUrl = (url: string) => {
  try {
    const hostname = new URL(url).hostname;
    return `https://www.google.com/s2/favicons?domain=${hostname}&sz=64`;
  } catch (e) {
    return "";
  }
};

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [query, setQuery] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [theme, setTheme] = useState<"light" | "dark">("light");

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const prevMessagesLengthRef = useRef(messages.length);
  useEffect(() => {
    const shouldScroll =
      messages.length !== prevMessagesLengthRef.current ||
      (loading && messages.length > 0);

    if (shouldScroll) {
      scrollToBottom();
    }

    prevMessagesLengthRef.current = messages.length;
  }, [messages, loading]);

  useEffect(() => {
    if (!loading && inputRef.current) {
      inputRef.current.focus();
    }
  }, [loading]);

  useEffect(() => {
    let value = localStorage.getItem("webo-theme");
    if (value === "light" || value === "dark") {
      setTheme(value);
    }
  }, []);

  const eventStreamer = async (jobId: string, assistantMessageId: string) => {
    try {
      const eventSource = new EventSource(
        `http://localhost:8000/stream/${jobId}`,
      );

      eventSource.onmessage = (e) => {
        const data = JSON.parse(e.data);

        setMessages((prevMessages) => {
          const updatedMessages = [...prevMessages];
          const currentAssistantMessageIndex = updatedMessages.findIndex(
            (msg) => msg.id === assistantMessageId,
          );

          if (currentAssistantMessageIndex === -1) return prevMessages;

          const currentAssistantMessage =
            updatedMessages[currentAssistantMessageIndex];

          currentAssistantMessage.status = data.status;
          currentAssistantMessage.thinkingSteps = data.memory || [];
          currentAssistantMessage.subQueries = data.sub_queries || [];
          currentAssistantMessage.sources = data.sources || [];

          if (data.final_answer && !currentAssistantMessage.content) {
            currentAssistantMessage.isExpanded = false;
          }

          if (data.final_answer) {
            currentAssistantMessage.content = data.final_answer;
          }

          return updatedMessages;
        });

        if (data.status === "COMPLETED" || data.status === "FAILED") {
          eventSource.close();
          setLoading(false);

          if (data.status === "COMPLETED") {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMessageId
                  ? { ...msg, isExpanded: false }
                  : msg,
              ),
            );
          }

          if (data.status === "FAILED") {
            setError("Job failed. Please try again.");
          }
        }
      };

      eventSource.onerror = (error) => {
        console.error("EventSource error:", error);
        eventSource.close();
        setError("Connection lost. Please try again.");
        setLoading(false);
      };
    } catch (err) {
      console.error("Streaming error:", err);
      setError("Failed to establish connection. Please try again.");
      setLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!query.trim() || loading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString() + "-user",
      role: "user",
      content: query,
    };
    setMessages((prev) => [...prev, userMessage]);
    setQuery("");
    setError(null);
    setLoading(true);

    const assistantMessageId = Date.now().toString() + "-assistant";
    setMessages((prev) => [
      ...prev,
      {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        thinkingSteps: [],
        status: "PENDING",
        sources: [],
        isExpanded: true,
      },
    ]);

    try {
      const response = await fetch("http://localhost:8000/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query: userMessage.content }),
      });

      if (!response.ok) {
        throw new Error("Failed to submit query");
      }

      const { job_id } = await response.json();

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId ? { ...msg, jobId: job_id } : msg,
        ),
      );

      await eventStreamer(job_id, assistantMessageId);
    } catch (err) {
      console.error("Search error:", err);
      setError("Failed to submit query. Please try again.");
      setLoading(false);
    }
  };

  const stopSearch = () => {
    setLoading(false);
    setMessages((prevMessages) => {
      const updatedMessages = [...prevMessages];
      const lastAssistantMessageIndex = updatedMessages.findLastIndex(
        (msg) => msg.role === "assistant",
      );
      if (lastAssistantMessageIndex !== -1) {
        updatedMessages[lastAssistantMessageIndex].status = "STOPPED";
        if (!updatedMessages[lastAssistantMessageIndex].content) {
          updatedMessages[lastAssistantMessageIndex].content =
            "Search was stopped.";
        }
      }
      return updatedMessages;
    });
  };

  const toggleExpansion = (messageId: string) => {
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === messageId ? { ...msg, isExpanded: !msg.isExpanded } : msg,
      ),
    );
  };

  const toggleTheme = () => {
    setTheme((prev) => {
      const next = prev === "light" ? "dark" : "light";
      localStorage.setItem("webo-theme", next);
      return next;
    });
  };

  const getStatusDisplay = (status?: string) => {
    if (!status) return null;

    const statusMap: Record<
      string,
      { label: string; icon: any; color: string }
    > = {
      PENDING: {
        label: "Initializing...",
        icon: Loader,
        color: theme === "dark" ? "text-gray-400" : "text-gray-400",
      },
      DECOMPOSING: {
        label: "Breaking down request...",
        icon: Layers,
        color: theme === "dark" ? "text-gray-400" : "text-gray-500",
      },
      WORKING: {
        label: "Searching internet...",
        icon: Search,
        color: theme === "dark" ? "text-gray-300" : "text-gray-600",
      },
      SYNTHESIZING: {
        label: "Synthesizing answer...",
        icon: Loader,
        color: theme === "dark" ? "text-gray-300" : "text-gray-700",
      },
      COMPLETED: { label: "Completed", icon: null, color: "text-green-600" },
      FAILED: { label: "Failed", icon: AlertCircle, color: "text-red-600" },
      STOPPED: { label: "Stopped", icon: StopCircle, color: "text-yellow-600" },
    };

    const statusInfo = statusMap[status] || {
      label: status,
      icon: Loader,
      color: theme === "dark" ? "text-gray-400" : "text-gray-400",
    };
    const Icon = statusInfo.icon;

    return (
      <div
        className={`flex items-center gap-2 text-sm ${statusInfo.color} font-medium mb-4`}
      >
        {Icon && (
          <Icon
            className={`w-4 h-4 ${
              status === "PENDING" || status === "SYNTHESIZING"
                ? "animate-spin"
                : ""
            }`}
          />
        )}
        <span>{statusInfo.label}</span>
      </div>
    );
  };

  return (
    <>
      <style jsx global>{`
        .markdown-content > *:first-child {
          margin-top: 0;
        }
        .markdown-content > *:last-child {
          margin-bottom: 0;
        }

        .markdown-content p {
          margin-bottom: 1.25rem;
          line-height: 1.75;
          color: ${theme === "dark" ? "#d1d5db" : "#374151"};
        }

        .markdown-content h1,
        .markdown-content h2,
        .markdown-content h3,
        .markdown-content h4 {
          margin-top: 2rem;
          margin-bottom: 1rem;
          font-weight: 600;
          color: ${theme === "dark" ? "#f9fafb" : "#111827"};
          line-height: 1.3;
        }

        .markdown-content h1 {
          font-size: 1.5rem;
        }
        .markdown-content h2 {
          font-size: 1.25rem;
        }
        .markdown-content h3 {
          font-size: 1.125rem;
        }

        .markdown-content ul,
        .markdown-content ol {
          margin-bottom: 1.25rem;
          padding-left: 1.5rem;
          color: ${theme === "dark" ? "#d1d5db" : "#374151"};
        }

        .markdown-content li {
          margin-bottom: 0.5rem;
          padding-left: 0.25rem;
        }

        .markdown-content li::marker {
          color: ${theme === "dark" ? "#6b7280" : "#9ca3af"};
        }

        .markdown-content a {
          color: ${theme === "dark" ? "#60a5fa" : "#2563eb"};
          text-decoration: none;
          cursor: pointer;
        }
        .markdown-content a:hover {
          text-decoration: underline;
        }

        .markdown-content code {
          background-color: ${theme === "dark" ? "#374151" : "#f3f4f6"};
          color: ${theme === "dark" ? "#e5e7eb" : "#1f2937"};
          padding: 0.2em 0.4em;
          border-radius: 0.25rem;
          font-size: 0.875em;
          font-family:
            ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }

        .markdown-content pre {
          background-color: ${theme === "dark" ? "#1f2937" : "#1f2937"};
          padding: 1rem;
          border-radius: 0.5rem;
          overflow-x: auto;
          margin-bottom: 1.5rem;
        }

        .markdown-content pre code {
          background-color: transparent;
          color: #f3f4f6;
          padding: 0;
          font-size: 0.875em;
        }

        .markdown-content blockquote {
          border-left: 4px solid ${theme === "dark" ? "#4b5563" : "#e5e7eb"};
          padding-left: 1rem;
          margin-bottom: 1.25rem;
          font-style: italic;
          color: ${theme === "dark" ? "#9ca3af" : "#6b7280"};
        }

        .markdown-content strong {
          color: ${theme === "dark" ? "#f3f4f6" : "#111827"};
          font-weight: 600;
        }
      `}</style>

      <div
        className={`min-h-screen font-sans ${theme === "dark" ? "bg-gray-900 text-gray-100" : "bg-gray-50 text-gray-900"}`}
      >
        <div className="fixed top-4 right-4 z-50">
          <button
            onClick={toggleTheme}
            className={`p-2 rounded-lg transition-colors ${
              theme === "dark"
                ? "bg-gray-800 hover:bg-gray-700 text-gray-200"
                : "bg-white hover:bg-gray-100 text-gray-700 border border-gray-200"
            }`}
          >
            {theme === "dark" ? (
              <Sun className="w-5 h-5 cursor-pointer" />
            ) : (
              <Moon className="w-5 h-5 cursor-pointer" />
            )}
          </button>
        </div>

        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pt-8">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center min-h-[60vh]">
              <div className="w-full max-w-lg space-y-8">
                <div className="text-center space-y-2">
                  <h2
                    className={`text-3xl font-semibold tracking-tight ${theme === "dark" ? "text-gray-100" : "text-gray-900"}`}
                  >
                    WEBO
                  </h2>
                  <p
                    className={`text-lg ${theme === "dark" ? "text-gray-400" : "text-gray-500"}`}
                  >
                    Ask complex questions. Get comprehensive answers.
                  </p>
                </div>

                <div className="relative">
                  <div
                    className={`relative rounded-xl shadow-sm focus-within:ring-1 transition-all duration-200 ${
                      theme === "dark"
                        ? "bg-gray-800 border border-gray-700 focus-within:border-gray-600 focus-within:ring-gray-600"
                        : "bg-white border border-gray-200 focus-within:border-gray-400 focus-within:ring-gray-400"
                    }`}
                  >
                    <input
                      ref={inputRef}
                      type="text"
                      placeholder="What do you want to know?"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      onKeyDown={(e) =>
                        e.key === "Enter" && !loading && handleSearch()
                      }
                      className={`w-full px-5 py-4 text-base bg-transparent focus:outline-none rounded-xl ${
                        theme === "dark"
                          ? "text-gray-100 placeholder-gray-500"
                          : "text-gray-900 placeholder-gray-400"
                      }`}
                      disabled={loading}
                    />
                    <div className="absolute right-2 top-1/2 -translate-y-1/2">
                      <button
                        onClick={handleSearch}
                        disabled={!query.trim() || loading}
                        className={`p-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer ${
                          theme === "dark"
                            ? "bg-gray-700 text-white hover:bg-gray-600"
                            : "bg-gray-900 text-white hover:bg-gray-700"
                        }`}
                      >
                        <ArrowUp className="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                </div>

                {error && (
                  <div
                    className={`p-3 rounded-lg flex items-center gap-3 text-sm ${
                      theme === "dark"
                        ? "bg-red-900/20 border border-red-800 text-red-400"
                        : "bg-red-50 border border-red-200 text-red-600"
                    }`}
                  >
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    <span>{error}</span>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="pb-40 space-y-10">
              {messages.map((message) => (
                <div key={message.id} className="fade-in">
                  {message.role === "user" && (
                    <div className="flex justify-end mb-4">
                      <div
                        className={`text-xl font-medium leading-relaxed max-w-[90%] ${
                          theme === "dark" ? "text-gray-100" : "text-gray-900"
                        }`}
                      >
                        {message.content}
                      </div>
                    </div>
                  )}

                  {message.role === "assistant" && (
                    <div className="flex gap-6">
                      <div className="flex-1 min-w-0 space-y-4">
                        <div>
                          {loading &&
                            message.status &&
                            message.status !== "COMPLETED" &&
                            getStatusDisplay(message.status)}

                          {((message.subQueries &&
                            message.subQueries.length > 0) ||
                            (message.sources &&
                              message.sources.length > 0)) && (
                            <div
                              className={`rounded-lg overflow-hidden shadow-sm mb-6 ${
                                theme === "dark"
                                  ? "border border-gray-700 bg-gray-800"
                                  : "border border-gray-200 bg-white"
                              }`}
                            >
                              <button
                                onClick={() => toggleExpansion(message.id)}
                                className={`w-full flex items-center justify-between px-4 py-2.5 transition-colors cursor-pointer ${
                                  theme === "dark"
                                    ? "bg-gray-800/50 hover:bg-gray-700/50 border-b border-gray-700"
                                    : "bg-gray-50 hover:bg-gray-100 border-b border-gray-100"
                                }`}
                              >
                                <div
                                  className={`flex items-center gap-2 text-xs font-medium uppercase tracking-wide ${
                                    theme === "dark"
                                      ? "text-gray-400"
                                      : "text-gray-500"
                                  }`}
                                >
                                  <Layers className="w-3.5 h-3.5" />
                                  <span>
                                    {message.sources?.length
                                      ? `${message.sources.length} Sources Analyzed`
                                      : "Processing Request"}
                                  </span>
                                </div>
                                {message.isExpanded ? (
                                  <ChevronUp
                                    className={`w-4 h-4 ${theme === "dark" ? "text-gray-500" : "text-gray-400"}`}
                                  />
                                ) : (
                                  <ChevronDown
                                    className={`w-4 h-4 ${theme === "dark" ? "text-gray-500" : "text-gray-400"}`}
                                  />
                                )}
                              </button>

                              {message.isExpanded && (
                                <div
                                  className={`p-4 space-y-6 ${theme === "dark" ? "bg-gray-800" : "bg-white"}`}
                                >
                                  {message.subQueries &&
                                    message.subQueries.length > 0 && (
                                      <div className="space-y-2">
                                        <div
                                          className={`text-xs font-semibold uppercase ${
                                            theme === "dark"
                                              ? "text-gray-500"
                                              : "text-gray-400"
                                          }`}
                                        >
                                          Research Steps
                                        </div>
                                        <div className="flex flex-col gap-2">
                                          {message.subQueries.map(
                                            (subQuery, idx) => (
                                              <div
                                                key={idx}
                                                className={`flex items-start gap-2.5 text-sm ${
                                                  theme === "dark"
                                                    ? "text-gray-300"
                                                    : "text-gray-600"
                                                }`}
                                              >
                                                <div
                                                  className={`mt-0.5 ${theme === "dark" ? "text-gray-500" : "text-gray-400"}`}
                                                >
                                                  <Search className="w-3.5 h-3.5" />
                                                </div>
                                                <span>{subQuery}</span>
                                              </div>
                                            ),
                                          )}
                                        </div>
                                      </div>
                                    )}

                                  {message.sources &&
                                    message.sources.length > 0 && (
                                      <div className="space-y-2">
                                        <div
                                          className={`text-xs font-semibold uppercase ${
                                            theme === "dark"
                                              ? "text-gray-500"
                                              : "text-gray-400"
                                          }`}
                                        >
                                          References
                                        </div>
                                        <div className="flex flex-col gap-2">
                                          {message.sources.map(
                                            (source, idx) => {
                                              const hostname = new URL(
                                                source.url,
                                              ).hostname.replace("www.", "");
                                              return (
                                                <a
                                                  key={idx}
                                                  href={source.url}
                                                  target="_blank"
                                                  rel="noopener noreferrer"
                                                  className={`flex items-center gap-3 p-2.5 rounded-lg transition-all group cursor-pointer ${
                                                    theme === "dark"
                                                      ? "bg-gray-800/50 border border-gray-700 hover:border-gray-600 hover:bg-gray-700/50"
                                                      : "bg-white border border-gray-200 hover:border-gray-300 hover:bg-gray-50"
                                                  }`}
                                                >
                                                  <div className="flex-shrink-0 w-4 h-4 rounded-sm overflow-hidden opacity-70">
                                                    <img
                                                      src={getFaviconUrl(
                                                        source.url,
                                                      )}
                                                      alt=""
                                                      className="w-full h-full object-cover"
                                                      onError={(e) => {
                                                        (
                                                          e.target as HTMLImageElement
                                                        ).style.display =
                                                          "none";
                                                      }}
                                                    />
                                                  </div>
                                                  <div className="flex-1 min-w-0">
                                                    <div
                                                      className={`text-sm font-medium truncate transition-colors ${
                                                        theme === "dark"
                                                          ? "text-gray-200 group-hover:text-blue-400"
                                                          : "text-gray-800 group-hover:text-blue-600"
                                                      }`}
                                                    >
                                                      {source.title || hostname}
                                                    </div>
                                                    <div
                                                      className={`text-xs truncate ${
                                                        theme === "dark"
                                                          ? "text-gray-500"
                                                          : "text-gray-500"
                                                      }`}
                                                    >
                                                      {hostname}
                                                    </div>
                                                  </div>
                                                </a>
                                              );
                                            },
                                          )}
                                        </div>
                                      </div>
                                    )}
                                </div>
                              )}
                            </div>
                          )}
                        </div>

                        <div className="markdown-content">
                          {message.content ? (
                            <ReactMarkdown>{message.content}</ReactMarkdown>
                          ) : (
                            loading &&
                            message.status !== "COMPLETED" && (
                              <div className="flex flex-col gap-2 animate-pulse mt-2">
                                <div
                                  className={`h-2 rounded w-1/3 ${
                                    theme === "dark"
                                      ? "bg-gray-700"
                                      : "bg-gray-200"
                                  }`}
                                ></div>
                              </div>
                            )
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
              <div ref={messagesEndRef} className="h-2" />
            </div>
          )}
        </div>

        {messages.length > 0 && (
          <div
            className={`fixed bottom-0 left-0 right-0 z-20 ${
              theme === "dark"
                ? "bg-gray-900 border-t border-gray-800"
                : "bg-gray-50 border-t border-gray-200"
            }`}
          >
            <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
              <div
                className={`relative rounded-xl shadow-sm flex items-center transition-colors ${
                  theme === "dark"
                    ? "bg-gray-800 border border-gray-700 focus-within:border-gray-600"
                    : "bg-white border border-gray-200 focus-within:border-gray-400"
                }`}
              >
                <input
                  ref={inputRef}
                  type="text"
                  placeholder="Ask a follow up..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) =>
                    e.key === "Enter" && !loading && handleSearch()
                  }
                  className={`flex-1 px-4 py-3 text-base bg-transparent focus:outline-none ${
                    theme === "dark"
                      ? "text-gray-100 placeholder-gray-500"
                      : "text-gray-900 placeholder-gray-400"
                  }`}
                  disabled={loading}
                />
                <div className="pr-2 flex items-center gap-2">
                  {loading ? (
                    <button
                      onClick={stopSearch}
                      className={`p-2 transition-colors cursor-pointer ${
                        theme === "dark"
                          ? "text-gray-500 hover:text-red-400"
                          : "text-gray-400 hover:text-red-500"
                      }`}
                      title="Stop search"
                    >
                      <StopCircle className="w-5 h-5" />
                    </button>
                  ) : (
                    <button
                      onClick={handleSearch}
                      disabled={!query.trim()}
                      className={`p-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer ${
                        theme === "dark"
                          ? "text-gray-500 hover:text-gray-200"
                          : "text-gray-400 hover:text-gray-900"
                      }`}
                    >
                      <ArrowUp className="w-5 h-5" />
                    </button>
                  )}
                </div>
              </div>
              {error && (
                <div
                  className={`absolute -top-10 left-1/2 -translate-x-1/2 px-4 py-2 text-xs rounded-full flex items-center gap-2 shadow-sm ${
                    theme === "dark"
                      ? "bg-red-900/20 text-red-400 border border-red-800"
                      : "bg-red-50 text-red-600 border border-red-200"
                  }`}
                >
                  <AlertCircle className="w-3 h-3" /> {error}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
