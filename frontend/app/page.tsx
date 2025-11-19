"use client";

import { useState, useRef, useEffect } from "react";
import {
  Search,
  Loader2,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Sparkles,
  ExternalLink,
  RefreshCw,
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
  isSourcesExpanded?: boolean;
  isThinkingExpanded?: boolean;
}

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

          if (data.final_answer) {
            currentAssistantMessage.content = data.final_answer;
          } else if (data.status) {
            currentAssistantMessage.content = "";
          }

          return updatedMessages;
        });

        if (data.status === "COMPLETED" || data.status === "FAILED") {
          eventSource.close();
          setLoading(false);

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

  const toggleSourceExpansion = (messageId: string) => {
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === messageId
          ? { ...msg, isSourcesExpanded: !msg.isSourcesExpanded }
          : msg,
      ),
    );
  };

  const toggleThinkingExpansion = (messageId: string) => {
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === messageId
          ? { ...msg, isThinkingExpanded: !msg.isThinkingExpanded }
          : msg,
      ),
    );
  };

  const getStatusDisplay = (status?: string) => {
    if (!status) return null;

    const statusMap: Record<string, { label: string; icon: any }> = {
      PENDING: { label: "Initializing...", icon: Loader2 },
      DECOMPOSING: { label: "Breaking down query...", icon: RefreshCw },
      SEARCHING: { label: "Searching sources...", icon: Search },
      PROCESSING: { label: "Analyzing results...", icon: RefreshCw },
      COMPLETED: { label: "Complete", icon: null },
      FAILED: { label: "Failed", icon: AlertCircle },
      STOPPED: { label: "Stopped", icon: null },
    };

    const statusInfo = statusMap[status] || {
      label: status,
      icon: Loader2,
    };
    const Icon = statusInfo.icon;

    return (
      <div className="flex items-center gap-2 text-sm text-gray-400 mb-3">
        {Icon && (
          <Icon
            className={`w-4 h-4 ${status !== "FAILED" && status !== "STOPPED" ? "animate-spin" : ""}`}
          />
        )}
        <span>{statusInfo.label}</span>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-black text-white">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <header className="sticky top-0 z-10 bg-black/80 backdrop-blur-sm border-b border-gray-800 py-4">
          <div className="flex items-center gap-2 justify-center">
            <Sparkles className="w-6 h-6 text-blue-400" strokeWidth={2} />
            <h1 className="text-xl font-semibold text-white">Webo</h1>
          </div>
        </header>

        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center min-h-[calc(100vh-120px)]">
            <div className="w-full max-w-2xl space-y-8">
              <div className="text-center space-y-3">
                <h2 className="text-4xl font-bold text-white">
                  What can I help you research?
                </h2>
                <p className="text-lg text-gray-400">
                  Ask me anything and I'll search the web for answers
                </p>
              </div>

              <div className="relative">
                <input
                  ref={inputRef}
                  type="text"
                  placeholder="Ask anything..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) =>
                    e.key === "Enter" && !loading && handleSearch()
                  }
                  className="w-full px-6 py-4 text-base text-gray-50 placeholder-gray-500 bg-gray-900 border border-gray-700 rounded-xl shadow-xl focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                  disabled={loading}
                />
                <button
                  onClick={handleSearch}
                  disabled={!query.trim() || loading}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-500 disabled:bg-gray-800 disabled:text-gray-600 disabled:cursor-not-allowed transition-colors"
                >
                  <Search className="w-5 h-5" strokeWidth={2} />
                </button>
              </div>

              {error && (
                <div className="p-4 bg-red-950/30 border border-red-800 rounded-xl flex items-start gap-3 text-sm text-red-300">
                  <AlertCircle className="w-5 h-5 mt-0.5 flex-shrink-0" />
                  <span>{error}</span>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="py-6 pb-32">
            <div className="space-y-6">
              {messages.map((message) => (
                <div key={message.id} className="space-y-4">
                  {message.role === "user" && (
                    <div className="flex items-start gap-4">
                      <div className="flex-shrink-0 w-8 h-8 bg-gradient-to-br from-blue-500 to-blue-600 rounded-full flex items-center justify-center shadow-lg">
                        <span className="text-sm font-semibold text-white">
                          U
                        </span>
                      </div>
                      <div className="flex-1 pt-1">
                        <p className="text-gray-100 text-base leading-relaxed">
                          {message.content}
                        </p>
                      </div>
                    </div>
                  )}

                  {message.role === "assistant" && (
                    <div className="flex items-start gap-4">
                      <div className="flex-shrink-0 w-8 h-8 bg-gradient-to-br from-gray-800 to-gray-900 rounded-full flex items-center justify-center shadow-lg border border-gray-700">
                        <Sparkles
                          className="w-4 h-4 text-blue-400"
                          strokeWidth={2}
                        />
                      </div>
                      <div className="flex-1 min-w-0 space-y-4">
                        {loading &&
                          message.status &&
                          message.status !== "COMPLETED" &&
                          getStatusDisplay(message.status)}

                        {message.subQueries &&
                          message.subQueries.length > 0 && (
                            <div className="p-4 bg-gray-900/50 border border-gray-800 rounded-xl">
                              <button
                                onClick={() =>
                                  toggleThinkingExpansion(message.id)
                                }
                                className="flex items-center justify-between w-full text-left"
                              >
                                <div className="flex items-center gap-2">
                                  <RefreshCw className="w-4 h-4 text-blue-400" />
                                  <span className="text-sm font-medium text-gray-300">
                                    Breaking down into{" "}
                                    {message.subQueries.length} sub-queries
                                  </span>
                                </div>
                                {message.isThinkingExpanded ? (
                                  <ChevronUp className="w-4 h-4 text-gray-500" />
                                ) : (
                                  <ChevronDown className="w-4 h-4 text-gray-500" />
                                )}
                              </button>

                              {message.isThinkingExpanded && (
                                <div className="mt-3 space-y-2 pl-6">
                                  {message.subQueries.map((subQuery, idx) => (
                                    <div
                                      key={idx}
                                      className="flex items-start gap-3 text-sm text-gray-400"
                                    >
                                      <span className="flex-shrink-0 w-5 h-5 bg-gray-800 rounded-full flex items-center justify-center text-xs text-gray-500 font-medium">
                                        {idx + 1}
                                      </span>
                                      <span className="flex-1">{subQuery}</span>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}

                        {message.sources && message.sources.length > 0 && (
                          <div>
                            <div className="flex items-center gap-2 mb-3">
                              <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                                Sources
                              </span>
                              <div className="flex-1 h-px bg-gray-800"></div>
                            </div>
                            <div className="flex items-center gap-2 flex-wrap">
                              {message.sources
                                .slice(
                                  0,
                                  message.isSourcesExpanded
                                    ? message.sources.length
                                    : 5,
                                )
                                .map((source, sourceIdx) => (
                                  <a
                                    key={sourceIdx}
                                    href={source.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="group inline-flex items-center gap-2 px-3 py-2 text-xs text-gray-300 bg-gray-900 hover:bg-gray-800 rounded-lg border border-gray-800 hover:border-gray-700 transition-all"
                                  >
                                    <span className="flex-shrink-0 w-5 h-5 bg-gray-800 rounded border border-gray-700 flex items-center justify-center text-[10px] font-semibold text-blue-400">
                                      {sourceIdx + 1}
                                    </span>
                                    <span className="max-w-[180px] truncate">
                                      {source.title ||
                                        new URL(source.url).hostname}
                                    </span>
                                    <ExternalLink className="w-3 h-3 text-gray-500 group-hover:text-gray-400 transition-colors" />
                                  </a>
                                ))}
                            </div>

                            {message.sources.length > 5 && (
                              <button
                                onClick={() =>
                                  toggleSourceExpansion(message.id)
                                }
                                className="mt-3 text-sm text-blue-400 hover:text-blue-300 flex items-center gap-1 transition-colors"
                              >
                                <span>
                                  {message.isSourcesExpanded
                                    ? "Show less"
                                    : `View all ${message.sources.length} sources`}
                                </span>
                                {message.isSourcesExpanded ? (
                                  <ChevronUp className="w-4 h-4" />
                                ) : (
                                  <ChevronDown className="w-4 h-4" />
                                )}
                              </button>
                            )}
                          </div>
                        )}

                        {message.content && (
                          <div className="prose prose-sm max-w-none prose-invert prose-headings:font-semibold prose-headings:text-white prose-headings:mb-3 prose-p:text-gray-300 prose-p:leading-relaxed prose-p:mb-4 prose-a:text-blue-400 prose-a:no-underline hover:prose-a:underline prose-strong:text-white prose-strong:font-semibold prose-ul:text-gray-300 prose-ul:ml-4 prose-ol:text-gray-300 prose-ol:ml-4 prose-li:mb-1 prose-code:text-blue-400 prose-code:bg-gray-900 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-pre:bg-gray-900 prose-pre:border prose-pre:border-gray-800 prose-blockquote:border-l-blue-500 prose-blockquote:text-gray-400">
                            <ReactMarkdown>{message.content}</ReactMarkdown>
                          </div>
                        )}

                        {/* {!message.content &&
                          loading &&
                          message.status !== "COMPLETED" && (
                            <div className="flex items-center gap-3 text-gray-500 py-4">
                              <Loader2 className="w-5 h-5 animate-spin" />
                              <span className="text-sm">
                                Gathering information...
                              </span>
                            </div>
                          )} */}
                      </div>
                    </div>
                  )}
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            <div className="fixed bottom-0 left-0 right-0 bg-gradient-to-t from-black via-black to-transparent pt-8 pb-6">
              <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="relative">
                  <input
                    ref={inputRef}
                    type="text"
                    placeholder="Ask a follow up..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={(e) =>
                      e.key === "Enter" && !loading && handleSearch()
                    }
                    className="w-full px-6 py-4 pr-14 text-base text-gray-50 placeholder-gray-500 bg-gray-900 border border-gray-700 rounded-xl shadow-xl focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
                    disabled={loading}
                  />
                  {loading ? (
                    <button
                      onClick={stopSearch}
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-2.5 bg-red-600 text-white rounded-lg hover:bg-red-500 transition-colors"
                      title="Stop search"
                    >
                      <div className="w-4 h-4 border-2 border-white rounded-sm"></div>
                    </button>
                  ) : (
                    <button
                      onClick={handleSearch}
                      disabled={!query.trim()}
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-500 disabled:bg-gray-800 disabled:text-gray-600 disabled:cursor-not-allowed transition-colors"
                    >
                      <Search className="w-5 h-5" strokeWidth={2} />
                    </button>
                  )}
                </div>
                {error && (
                  <div className="mt-3 p-4 bg-red-950/30 border border-red-800 rounded-xl flex items-start gap-3 text-sm text-red-300">
                    <AlertCircle className="w-5 h-5 mt-0.5 flex-shrink-0" />
                    <span>{error}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
