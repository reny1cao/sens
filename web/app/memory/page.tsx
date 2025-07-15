"use client";

import { useState, useEffect } from "react";
import { AgentMemoryDashboard } from "@/components/memory/AgentMemoryDashboard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Brain, Database, MessageSquare, Activity } from "lucide-react";
import Link from "next/link";

export default function MemoryPage() {
  const [sessionId, setSessionId] = useState<string>("global");
  const [memoryHealth, setMemoryHealth] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Generate or get session ID from storage
    const storedSessionId = localStorage.getItem("sens_session_id");
    if (storedSessionId) {
      setSessionId(storedSessionId);
    } else {
      const newSessionId = `session_${Date.now()}_${Math.random()
        .toString(36)
        .substr(2, 9)}`;
      localStorage.setItem("sens_session_id", newSessionId);
      setSessionId(newSessionId);
    }

    // Check memory system health
    checkMemoryHealth();
  }, []);

  const checkMemoryHealth = async () => {
    try {
      const response = await fetch("/api/memory/health");
      const health = await response.json();
      setMemoryHealth(health);
    } catch (error) {
      console.error("Failed to check memory health:", error);
      setMemoryHealth({
        status: "unhealthy",
        error: "Failed to connect to memory system",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSessionSwitch = (newSessionId: string) => {
    setSessionId(newSessionId);
    if (newSessionId !== "global") {
      localStorage.setItem("sens_session_id", newSessionId);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <Database className="h-6 w-6 text-blue-600" />
              <h1 className="text-xl font-semibold text-gray-900">SENS</h1>
              <span className="text-sm text-gray-500">Memory Dashboard</span>
            </div>
            <div className="flex items-center gap-6">
              <nav className="flex items-center gap-4">
                <Link
                  href="/"
                  className="text-sm font-medium text-gray-700 hover:text-blue-600 transition-colors"
                >
                  Classic
                </Link>
                <Link
                  href="/chat"
                  className="text-sm font-medium text-gray-700 hover:text-blue-600 transition-colors flex items-center gap-1"
                >
                  <MessageSquare className="h-4 w-4" />
                  Chat
                </Link>
                <Link
                  href="/schema"
                  className="text-sm font-medium text-gray-700 hover:text-blue-600 transition-colors"
                >
                  Schema
                </Link>
                <Link
                  href="/memory"
                  className="text-sm font-medium text-blue-600 flex items-center gap-1"
                >
                  <Brain className="h-4 w-4" />
                  Memory
                </Link>
              </nav>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Memory System Status */}
        {loading ? (
          <Card className="mb-6">
            <CardContent className="p-6">
              <div className="flex items-center gap-3">
                <Activity className="h-5 w-5 animate-spin text-blue-600" />
                <span>Checking memory system status...</span>
              </div>
            </CardContent>
          </Card>
        ) : (
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Brain className="h-5 w-5" />
                Memory System Status
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="flex items-center gap-2">
                  <Badge
                    variant={
                      memoryHealth?.status === "healthy"
                        ? "default"
                        : "destructive"
                    }
                    className="capitalize"
                  >
                    {memoryHealth?.status || "unknown"}
                  </Badge>
                  <span className="text-sm text-gray-600">Overall Status</span>
                </div>

                <div className="flex items-center gap-2">
                  <Badge
                    variant={
                      memoryHealth?.memory_enabled ? "default" : "secondary"
                    }
                  >
                    {memoryHealth?.memory_enabled ? "Enabled" : "Disabled"}
                  </Badge>
                  <span className="text-sm text-gray-600">Memory System</span>
                </div>

                <div className="flex items-center gap-2">
                  <Badge
                    variant={
                      memoryHealth?.session_isolation ? "default" : "secondary"
                    }
                  >
                    {memoryHealth?.session_isolation ? "Isolated" : "Shared"}
                  </Badge>
                  <span className="text-sm text-gray-600">Session Mode</span>
                </div>
              </div>

              {memoryHealth?.error && (
                <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-md">
                  <p className="text-sm text-red-700">{memoryHealth.error}</p>
                </div>
              )}

              {memoryHealth?.configuration && (
                <div className="mt-4">
                  <h4 className="text-sm font-medium text-gray-700 mb-2">
                    Configuration
                  </h4>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
                    <div>
                      <span className="text-gray-500">Max Memories:</span>{" "}
                      <span className="font-medium">
                        {memoryHealth.configuration.max_memories_per_type}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-500">Auto Consolidation:</span>{" "}
                      <span className="font-medium">
                        {memoryHealth.configuration.auto_consolidation
                          ? "Yes"
                          : "No"}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-500">
                        Background Learning:
                      </span>{" "}
                      <span className="font-medium">
                        {memoryHealth.configuration.background_learning
                          ? "Yes"
                          : "No"}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-500">
                        Cross-Session Sharing:
                      </span>{" "}
                      <span className="font-medium">
                        {memoryHealth.configuration.cross_session_sharing
                          ? "Yes"
                          : "No"}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-500">Active Sessions:</span>{" "}
                      <span className="font-medium">
                        {memoryHealth.active_sessions || 0}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Session Selection */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Session Selection</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              <Button
                variant={sessionId === "global" ? "default" : "outline"}
                size="sm"
                onClick={() => handleSessionSwitch("global")}
              >
                Global Memory
              </Button>
              <Button
                variant={sessionId !== "global" ? "default" : "outline"}
                size="sm"
                onClick={() =>
                  handleSessionSwitch(
                    sessionId !== "global" ? sessionId : `session_${Date.now()}`
                  )
                }
              >
                Your Session (
                {sessionId === "global" ? "Create New" : sessionId.slice(-8)})
              </Button>
            </div>
            <p className="text-sm text-gray-600 mt-2">
              {sessionId === "global"
                ? "Viewing shared memories across all users"
                : "Viewing your personal session memories"}
            </p>
          </CardContent>
        </Card>

        {/* Memory Dashboard */}
        {memoryHealth?.memory_enabled ? (
          <AgentMemoryDashboard sessionId={sessionId} />
        ) : (
          <Card>
            <CardContent className="p-6 text-center">
              <Brain className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                Memory System Disabled
              </h3>
              <p className="text-gray-600 mb-4">
                The memory system is currently disabled. Enable it in your
                configuration to start learning from interactions.
              </p>
              <Button
                variant="outline"
                onClick={() => window.location.reload()}
              >
                Refresh Status
              </Button>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
