"use client";

import { useState, useRef, useEffect } from "react";
import {
  Search,
  ExternalLink,
  FileText,
  Loader2,
  AlertCircle,
  Brain,
  ChevronDown,
  ChevronUp,
  MessageSquareText,
  User,
} from "lucide-react";
import ReactMarkdown from "react-markdown";

interface Source {
  title: string;
  url: string;
  content?: string;
  summary?: string;
}

interface ThinkingStep {
  type: string;
  timestamp: string;
  tool?: string;
  tool_input?: string;
  text?: string;
  output?: string;
  log?: string;
  tool_name?: string;
  input?: string;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  thinkingSteps?: ThinkingStep[];
  status?: string;
  error?: string;
}

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [query, setQuery] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedSource, setExpandedSource] = useState<number | null>(null);
  const [showThinking, setShowThinking] = useState<boolean>(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, showThinking]);

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
    setShowThinking(true);

    const assistantMessageId = Date.now().toString() + "-assistant";
    setMessages((prev) => [
      ...prev,
      {
        id: assistantMessageId,
        role: "assistant",
        content: "Searching...",
        thinkingSteps: [],
        status: "Starting research...",
      },
    ]);

    try {
      const eventSource = new EventSource(
        `http://localhost:8000/research/stream?query=${encodeURIComponent(userMessage.content)}`,
      );
      eventSourceRef.current = eventSource;

      eventSource.onmessage = (event) => {
        const eventData = JSON.parse(event.data);
        setMessages((prevMessages) => {
          const updatedMessages = [...prevMessages];
          const currentAssistantMessageIndex = updatedMessages.findIndex(
            (msg) => msg.id === assistantMessageId,
          );

          if (currentAssistantMessageIndex === -1) return prevMessages;

          const currentAssistantMessage =
            updatedMessages[currentAssistantMessageIndex];

          switch (eventData.type) {
            case "status":
              currentAssistantMessage.status = eventData.message;
              break;
            case "thinking_step":
              currentAssistantMessage.thinkingSteps = [
                ...(currentAssistantMessage.thinkingSteps || []),
                eventData.data,
              ];
              currentAssistantMessage.status = `Thinking: ${formatThinkingStep(eventData.data).title}`;
              break;
            case "final_result":
              currentAssistantMessage.content = eventData.answer;
              currentAssistantMessage.sources = eventData.raw_sources;
              currentAssistantMessage.status = "Research complete!";
              break;
            case "complete":
              eventSource.close();
              setLoading(false);
              currentAssistantMessage.status = "Research complete!";
              break;
            case "error":
              setError(eventData.message);
              currentAssistantMessage.error = eventData.message;
              currentAssistantMessage.content = `Error: ${eventData.message}`;
              eventSource.close();
              setLoading(false);
              break;
          }
          return updatedMessages;
        });
      };

      eventSource.onerror = (err) => {
        console.error("EventSource error:", err);
        setError("Connection error during research. Please try again.");
        setLoading(false);
        eventSource.close();
      };
    } catch (err) {
      setError("Search failed. Please try again.");
      setLoading(false);
    }
  };

  const stopSearch = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setLoading(false);
    setMessages((prevMessages) => {
      const updatedMessages = [...prevMessages];
      const lastAssistantMessageIndex = updatedMessages.findLastIndex(
        (msg) => msg.role === "assistant",
      );
      if (lastAssistantMessageIndex !== -1) {
        updatedMessages[lastAssistantMessageIndex].status = "Search stopped.";
        updatedMessages[lastAssistantMessageIndex].content +=
          "\n\n**Search stopped.**";
      }
      return updatedMessages;
    });
  };

  const toggleSourceExpansion = (index: number) => {
    setExpandedSource(expandedSource === index ? null : index);
  };

  const formatThinkingStep = (step: ThinkingStep) => {
    switch (step.type) {
      case "action":
        return {
          title: `🔧 Action: ${step.tool}`,
          content: `Input: ${step.tool_input}\n\nReasoning: ${step.log}`,
        };
      case "tool_start":
        return {
          title: `🚀 Starting: ${step.tool_name}`,
          content: `Input: ${step.input}`,
        };
      case "tool_end":
        return {
          title: `✅ Tool Complete`,
          content: step.output || "Tool execution finished",
        };
      case "thought":
        return {
          title: `💭 Thinking`,
          content: step.text || "",
        };
      case "finish":
        return {
          title: `🎯 Final Answer Ready`,
          content: step.log || "Research complete",
        };
      default:
        return {
          title: `📝 ${step.type}`,
          content: JSON.stringify(step, null, 2),
        };
    }
  };

  return (
    <div className="flex flex-col h-screen bg-neutral-950 text-neutral-100">
      <header className="py-4 border-b border-neutral-800 text-center">
        <h1 className="text-2xl font-bold text-neutral-100">
          AI Research Assistant
        </h1>
      </header>

      <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
        <div className="max-w-3xl mx-auto space-y-8">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-neutral-500">
              <MessageSquareText className="w-16 h-16 mb-4" />
              <p className="text-lg">Start a new research query below.</p>
            </div>
          )}

          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex items-start gap-4 ${
                message.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              {message.role === "assistant" && (
                <div className="flex-shrink-0 p-2 bg-indigo-600 rounded-full">
                  <Brain className="w-5 h-5 text-white" />
                </div>
              )}
              <div
                className={`flex-1 p-4 rounded-lg shadow-md ${
                  message.role === "user"
                    ? "bg-blue-700 text-white"
                    : "bg-neutral-800 text-neutral-100"
                }`}
              >
                <div className="prose prose-invert max-w-none">
                  <ReactMarkdown>{message.content}</ReactMarkdown>
                </div>
                {message.sources && message.sources.length > 0 && (
                  <div className="mt-4 border-t border-neutral-700 pt-4">
                    <h3 className="text-md font-semibold mb-2">Sources:</h3>
                    <ul className="space-y-2">
                      {message.sources.map((source, index) => (
                        <li key={index} className="flex items-center text-sm">
                          <ExternalLink className="w-4 h-4 mr-2 text-neutral-400" />
                          <a
                            href={source.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-400 hover:underline break-all"
                          >
                            {source.title || source.url}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {message.status && (
                  <div className="mt-2 text-xs text-neutral-400 italic">
                    Status: {message.status}
                  </div>
                )}
                {message.error && (
                  <div className="mt-2 text-xs text-red-400 flex items-center">
                    <AlertCircle className="w-4 h-4 mr-1" />
                    Error: {message.error}
                  </div>
                )}
              </div>
              {message.role === "user" && (
                <div className="flex-shrink-0 p-2 bg-neutral-600 rounded-full">
                  <User className="w-5 h-5 text-white" />
                </div>
              )}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {messages.some(
        (msg) => msg.thinkingSteps && msg.thinkingSteps.length > 0,
      ) && (
        <div className="max-w-3xl mx-auto w-full mb-4 px-4">
          <div className="bg-neutral-800 rounded-lg shadow-lg border border-neutral-700 overflow-hidden">
            <div
              className="bg-neutral-700 px-6 py-3 cursor-pointer flex items-center justify-between"
              onClick={() => setShowThinking(!showThinking)}
            >
              <h2 className="text-lg font-semibold text-neutral-100 flex items-center">
                <Brain className="w-4 h-4 mr-2" />
                Thinking Process (
                {messages.findLast((msg) => msg.thinkingSteps)?.thinkingSteps
                  ?.length || 0}{" "}
                steps)
              </h2>
              {showThinking ? (
                <ChevronUp className="w-4 h-4 text-neutral-100" />
              ) : (
                <ChevronDown className="w-4 h-4 text-neutral-100" />
              )}
            </div>

            {showThinking && (
              <div className="max-h-60 overflow-y-auto custom-scrollbar">
                <div className="divide-y divide-neutral-700">
                  {messages
                    .findLast((msg) => msg.thinkingSteps)
                    ?.thinkingSteps?.map((step, index) => {
                      const formatted = formatThinkingStep(step);
                      return (
                        <div
                          key={index}
                          className="p-4 hover:bg-neutral-700 transition-colors"
                        >
                          <div className="flex items-start space-x-3">
                            <div className="flex-shrink-0 w-6 h-6 bg-indigo-700 rounded-full flex items-center justify-center text-indigo-100 font-semibold text-xs">
                              {index + 1}
                            </div>
                            <div className="flex-1 min-w-0">
                              <h4 className="text-sm font-semibold text-neutral-100 mb-1">
                                {formatted.title}
                              </h4>
                              <div className="text-xs text-neutral-300 whitespace-pre-wrap">
                                {formatted.content}
                              </div>
                              <div className="text-xs text-neutral-500 mt-1">
                                {new Date(step.timestamp).toLocaleTimeString()}
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="sticky bottom-0 bg-neutral-950 p-4 border-t border-neutral-800">
        <div className="relative max-w-3xl mx-auto">
          <div className="flex items-center bg-neutral-800 rounded-xl shadow-lg border border-neutral-700 overflow-hidden">
            <div className="pl-4 pr-2">
              <Search className="w-5 h-5 text-neutral-500" />
            </div>
            <input
              type="text"
              placeholder="Ask me anything..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !loading && handleSearch()}
              className="flex-1 py-3 px-2 bg-neutral-800 text-neutral-100 placeholder-neutral-500 focus:outline-none text-base"
              disabled={loading}
            />
            {loading ? (
              <button
                onClick={stopSearch}
                className="m-2 px-4 py-2 rounded-lg font-semibold bg-red-600 hover:bg-red-700 text-white transition-all duration-200 flex items-center justify-center"
              >
                <Loader2 className="w-4 h-4 animate-spin mr-2" /> Stop
              </button>
            ) : (
              <button
                onClick={handleSearch}
                disabled={!query.trim()}
                className={`m-2 px-4 py-2 rounded-lg font-semibold transition-all duration-200 flex items-center justify-center ${
                  !query.trim()
                    ? "bg-neutral-700 text-neutral-500 cursor-not-allowed"
                    : "bg-blue-600 hover:bg-blue-700 text-white shadow-md hover:shadow-lg"
                }`}
              >
                <Search className="w-4 h-4 mr-2" /> Ask
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
