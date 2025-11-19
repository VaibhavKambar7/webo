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

  const getStatusDisplay = (status?: string) => {
    if (!status) return null;

    const statusMap: Record<
      string,
      { label: string; icon: any; color: string }
    > = {
      PENDING: {
        label: "Initializing...",
        icon: Loader,
        color: "text-gray-400",
      },
      DECOMPOSING: {
        label: "Breaking down request...",
        icon: Layers,
        color: "text-blue-600",
      },
      SEARCHING: {
        label: "Searching internet...",
        icon: Search,
        color: "text-blue-600",
      },
      PROCESSING: {
        label: "Analyzing sources...",
        icon: Loader,
        color: "text-purple-600",
      },
      COMPLETED: { label: "Completed", icon: null, color: "text-green-600" },
      FAILED: { label: "Failed", icon: AlertCircle, color: "text-red-600" },
      STOPPED: { label: "Stopped", icon: StopCircle, color: "text-yellow-600" },
    };

    const statusInfo = statusMap[status] || {
      label: status,
      icon: Loader,
      color: "text-gray-400",
    };
    const Icon = statusInfo.icon;

    return (
      <div
        className={`flex items-center gap-2 text-sm ${statusInfo.color} font-medium mb-4`}
      >
        {Icon && (
          <Icon
            className={`w-4 h-4 ${
              status !== "FAILED" &&
              status !== "STOPPED" &&
              status !== "COMPLETED"
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
        /* Light Theme Markdown Styles */
        .markdown-content > *:first-child {
          margin-top: 0;
        }
        .markdown-content > *:last-child {
          margin-bottom: 0;
        }

        .markdown-content p {
          margin-bottom: 1.25rem;
          line-height: 1.75;
          color: #374151; /* gray-700 */
        }

        .markdown-content h1,
        .markdown-content h2,
        .markdown-content h3,
        .markdown-content h4 {
          margin-top: 2rem;
          margin-bottom: 1rem;
          font-weight: 600;
          color: #111827; /* gray-900 */
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
          color: #374151;
        }

        .markdown-content li {
          margin-bottom: 0.5rem;
          padding-left: 0.25rem;
        }

        .markdown-content li::marker {
          color: #9ca3af; /* gray-400 */
        }

        .markdown-content a {
          color: #2563eb; /* blue-600 */
          text-decoration: none;
          cursor: pointer;
        }
        .markdown-content a:hover {
          text-decoration: underline;
        }

        .markdown-content code {
          background-color: #f3f4f6; /* gray-100 */
          color: #1f2937; /* gray-800 */
          padding: 0.2em 0.4em;
          border-radius: 0.25rem;
          font-size: 0.875em;
          font-family:
            ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }

        .markdown-content pre {
          background-color: #1f2937; /* gray-800 */
          padding: 1rem;
          border-radius: 0.5rem;
          overflow-x: auto;
          margin-bottom: 1.5rem;
        }

        .markdown-content pre code {
          background-color: transparent;
          color: #f3f4f6; /* gray-100 */
          padding: 0;
          font-size: 0.875em;
        }

        .markdown-content blockquote {
          border-left: 4px solid #e5e7eb; /* gray-200 */
          padding-left: 1rem;
          margin-bottom: 1.25rem;
          font-style: italic;
          color: #6b7280; /* gray-500 */
        }

        .markdown-content strong {
          color: #111827; /* gray-900 */
          font-weight: 600;
        }
      `}</style>

      <div className="min-h-screen bg-gray-50 text-gray-900 font-sans">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pt-8">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center min-h-[60vh]">
              <div className="w-full max-w-lg space-y-8">
                <div className="text-center space-y-2">
                  <h2 className="text-3xl font-semibold text-gray-900 tracking-tight">
                    WEBO
                  </h2>
                  <p className="text-gray-500 text-lg">
                    Ask complex questions. Get comprehensive answers.
                  </p>
                </div>

                <div className="relative">
                  <div className="relative bg-white rounded-xl border border-gray-200 shadow-sm focus-within:border-gray-400 focus-within:ring-1 focus-within:ring-gray-400 transition-all duration-200">
                    <input
                      ref={inputRef}
                      type="text"
                      placeholder="What do you want to know?"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      onKeyDown={(e) =>
                        e.key === "Enter" && !loading && handleSearch()
                      }
                      className="w-full px-5 py-4 text-base text-gray-900 placeholder-gray-400 bg-transparent focus:outline-none rounded-xl"
                      disabled={loading}
                    />
                    <div className="absolute right-2 top-1/2 -translate-y-1/2">
                      <button
                        onClick={handleSearch}
                        disabled={!query.trim() || loading}
                        className="p-2 bg-gray-900 text-white rounded-lg hover:bg-gray-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                      >
                        <ArrowUp className="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                </div>

                {error && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3 text-sm text-red-600">
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
                      <div className="text-xl font-medium text-gray-900 leading-relaxed max-w-[90%]">
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
                            <div className="border border-gray-200 rounded-lg overflow-hidden bg-white shadow-sm mb-6">
                              <button
                                onClick={() => toggleExpansion(message.id)}
                                className="w-full flex items-center justify-between px-4 py-2.5 bg-gray-50 hover:bg-gray-100 transition-colors cursor-pointer border-b border-gray-100"
                              >
                                <div className="flex items-center gap-2 text-xs font-medium text-gray-500 uppercase tracking-wide">
                                  <Layers className="w-3.5 h-3.5" />
                                  <span>
                                    {message.sources?.length
                                      ? `${message.sources.length} Sources Analyzed`
                                      : "Processing Request"}
                                  </span>
                                </div>
                                {message.isExpanded ? (
                                  <ChevronUp className="w-4 h-4 text-gray-400" />
                                ) : (
                                  <ChevronDown className="w-4 h-4 text-gray-400" />
                                )}
                              </button>

                              {message.isExpanded && (
                                <div className="p-4 space-y-6 bg-white">
                                  {message.subQueries &&
                                    message.subQueries.length > 0 && (
                                      <div className="space-y-2">
                                        <div className="text-xs font-semibold text-gray-400 uppercase">
                                          Research Steps
                                        </div>
                                        <div className="flex flex-col gap-2">
                                          {message.subQueries.map(
                                            (subQuery, idx) => (
                                              <div
                                                key={idx}
                                                className="flex items-start gap-2.5 text-sm text-gray-600"
                                              >
                                                <div className="mt-0.5 text-gray-400">
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
                                        <div className="text-xs font-semibold text-gray-400 uppercase">
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
                                                  className="flex items-center gap-3 p-2.5 bg-white border border-gray-200 hover:border-gray-300 hover:bg-gray-50 rounded-lg transition-all group cursor-pointer"
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
                                                    <div className="text-sm text-gray-800 font-medium truncate group-hover:text-blue-600 transition-colors">
                                                      {source.title || hostname}
                                                    </div>
                                                    <div className="text-xs text-gray-500 truncate">
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
                                <div className="h-2 bg-gray-200 rounded w-1/3"></div>
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
          <div className="fixed bottom-0 left-0 right-0 z-20 bg-gray-50 border-t border-gray-200">
            <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
              <div className="relative bg-white border border-gray-200 rounded-xl shadow-sm flex items-center focus-within:border-gray-400 transition-colors">
                <input
                  ref={inputRef}
                  type="text"
                  placeholder="Ask a follow up..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) =>
                    e.key === "Enter" && !loading && handleSearch()
                  }
                  className="flex-1 px-4 py-3 text-base text-gray-900 bg-transparent focus:outline-none placeholder-gray-400"
                  disabled={loading}
                />
                <div className="pr-2 flex items-center gap-2">
                  {loading ? (
                    <button
                      onClick={stopSearch}
                      className="p-2 text-gray-400 hover:text-red-500 transition-colors cursor-pointer"
                      title="Stop search"
                    >
                      <StopCircle className="w-5 h-5" />
                    </button>
                  ) : (
                    <button
                      onClick={handleSearch}
                      disabled={!query.trim()}
                      className="p-2 text-gray-400 hover:text-gray-900 transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                    >
                      <ArrowUp className="w-5 h-5" />
                    </button>
                  )}
                </div>
              </div>
              {error && (
                <div className="absolute -top-10 left-1/2 -translate-x-1/2 px-4 py-2 bg-red-50 text-red-600 text-xs rounded-full border border-red-200 flex items-center gap-2 shadow-sm">
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
