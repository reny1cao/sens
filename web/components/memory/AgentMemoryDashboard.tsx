import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Brain, Search, Trash2, Link, BarChart3, Eye } from "lucide-react";

interface Memory {
  id: string;
  type: string;
  name: string;
  content: any;
  confidence: number;
  usage_count: number;
  success_rate: number;
  created_at: string;
  last_used?: string;
}

interface MemoryStats {
  total_memories: number;
  memories_by_type: Record<string, number>;
  total_relationships: number;
  performance: {
    memories_stored: number;
    queries_executed: number;
    avg_query_time: number;
  };
}

interface AgentMemoryDashboardProps {
  sessionId: string;
}

export const AgentMemoryDashboard: React.FC<AgentMemoryDashboardProps> = ({
  sessionId,
}) => {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [memoryStats, setMemoryStats] = useState<MemoryStats | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedMemory, setSelectedMemory] = useState<Memory | null>(null);
  const [activeTab, setActiveTab] = useState<
    "overview" | "memories" | "relationships" | "analytics"
  >("overview");

  useEffect(() => {
    fetchMemoryStats();
    fetchMemories();
  }, [sessionId]);

  const fetchMemoryStats = async () => {
    try {
      const response = await fetch(`/api/memory/stats?session_id=${sessionId}`);
      const data = await response.json();
      if (data.success) {
        setMemoryStats(data);
      }
    } catch (error) {
      console.error("Failed to fetch memory stats:", error);
    }
  };

  const fetchMemories = async () => {
    try {
      const response = await fetch(
        `/api/memory/search?session_id=${sessionId}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query: "",
            limit: 50,
          }),
        }
      );
      const data = await response.json();
      if (data.success) {
        setMemories(data.memories || []);
      }
    } catch (error) {
      console.error("Failed to fetch memories:", error);
    }
  };

  const searchMemories = async () => {
    if (!searchQuery.trim()) {
      fetchMemories();
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(
        `/api/memory/search?session_id=${sessionId}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query: searchQuery,
            limit: 20,
          }),
        }
      );
      const data = await response.json();
      if (data.success) {
        setMemories(data.memories || []);
      }
    } catch (error) {
      console.error("Failed to search memories:", error);
    } finally {
      setLoading(false);
    }
  };

  const forgetMemory = async (memoryId: string) => {
    try {
      const response = await fetch(
        `/api/memory/${memoryId}?session_id=${sessionId}`,
        {
          method: "DELETE",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            reason: "User requested removal",
          }),
        }
      );
      const data = await response.json();
      if (data.success) {
        setMemories((prev) => prev.filter((m) => m.id !== memoryId));
        setSelectedMemory(null);
        fetchMemoryStats();
      }
    } catch (error) {
      console.error("Failed to forget memory:", error);
    }
  };

  const viewMemoryDetails = (memory: Memory) => {
    setSelectedMemory(memory);
  };

  const getMemoryTypeColor = (type: string) => {
    const colors = {
      concept: "bg-blue-100 text-blue-800",
      pattern: "bg-green-100 text-green-800",
      mapping: "bg-purple-100 text-purple-800",
      error_fix: "bg-red-100 text-red-800",
      rule: "bg-yellow-100 text-yellow-800",
    };
    return colors[type as keyof typeof colors] || "bg-gray-100 text-gray-800";
  };

  const getPerformanceLevel = (successRate: number) => {
    if (successRate >= 0.9)
      return { label: "Excellent", color: "text-green-600" };
    if (successRate >= 0.7) return { label: "Good", color: "text-blue-600" };
    if (successRate >= 0.5) return { label: "Fair", color: "text-yellow-600" };
    return { label: "Poor", color: "text-red-600" };
  };

  return (
    <div className="w-full max-w-7xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Brain className="h-8 w-8 text-blue-600" />
          <h1 className="text-2xl font-bold">Agent Memory Dashboard</h1>
          <Badge variant="outline">Session: {sessionId.slice(-8)}</Badge>
        </div>
        <Button onClick={() => window.location.reload()} variant="outline">
          Refresh
        </Button>
      </div>

      {/* Stats Overview */}
      {memoryStats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">
                Total Memories
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {memoryStats.total_memories}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">
                Relationships
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {memoryStats.total_relationships}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">
                Avg Query Time
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {memoryStats.performance.avg_query_time.toFixed(1)}ms
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">
                Queries Executed
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {memoryStats.performance.queries_executed}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Memory Type Distribution */}
      {memoryStats && (
        <Card>
          <CardHeader>
            <CardTitle>Memory Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {Object.entries(memoryStats.memories_by_type).map(
                ([type, count]) => (
                  <Badge key={type} className={getMemoryTypeColor(type)}>
                    {type}: {count}
                  </Badge>
                )
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Search */}
      <Card>
        <CardHeader>
          <CardTitle>Search Memories</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex space-x-2">
            <Input
              placeholder="Search memories by content..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && searchMemories()}
            />
            <Button onClick={searchMemories} disabled={loading}>
              <Search className="h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Memory List */}
      <Card>
        <CardHeader>
          <CardTitle>Memories ({memories.length})</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {memories.map((memory) => {
              const performance = getPerformanceLevel(memory.success_rate);
              return (
                <div
                  key={memory.id}
                  className="border rounded-lg p-4 hover:bg-gray-50 cursor-pointer"
                  onClick={() => setSelectedMemory(memory)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-2">
                        <Badge className={getMemoryTypeColor(memory.type)}>
                          {memory.type}
                        </Badge>
                        <span className="font-medium">{memory.name}</span>
                        <span className={`text-sm ${performance.color}`}>
                          {performance.label}
                        </span>
                      </div>
                      <div className="text-sm text-gray-600 mb-2">
                        {typeof memory.content === "string"
                          ? memory.content.slice(0, 100) + "..."
                          : JSON.stringify(memory.content).slice(0, 100) +
                            "..."}
                      </div>
                      <div className="flex items-center space-x-4 text-xs text-gray-500">
                        <span>Used: {memory.usage_count} times</span>
                        <span>
                          Success: {(memory.success_rate * 100).toFixed(1)}%
                        </span>
                        <span>Confidence: {memory.confidence.toFixed(1)}</span>
                        <span>
                          Created:{" "}
                          {new Date(memory.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                    <div className="flex space-x-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={(e) => {
                          e.stopPropagation();
                          viewMemoryDetails(memory);
                        }}
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={(e) => {
                          e.stopPropagation();
                          forgetMemory(memory.id);
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Memory Detail Modal */}
      {selectedMemory && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <Card className="w-full max-w-2xl max-h-[80vh] overflow-y-auto">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center space-x-2">
                  <Badge className={getMemoryTypeColor(selectedMemory.type)}>
                    {selectedMemory.type}
                  </Badge>
                  <span>{selectedMemory.name}</span>
                </CardTitle>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setSelectedMemory(null)}
                >
                  ×
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <h3 className="font-medium mb-2">Content</h3>
                  <pre className="bg-gray-100 p-3 rounded text-sm overflow-x-auto">
                    {JSON.stringify(selectedMemory.content, null, 2)}
                  </pre>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <h3 className="font-medium">Performance</h3>
                    <div className="text-sm text-gray-600">
                      <div>Usage: {selectedMemory.usage_count} times</div>
                      <div>
                        Success Rate:{" "}
                        {(selectedMemory.success_rate * 100).toFixed(1)}%
                      </div>
                      <div>
                        Confidence: {selectedMemory.confidence.toFixed(1)}
                      </div>
                    </div>
                  </div>
                  <div>
                    <h3 className="font-medium">Timestamps</h3>
                    <div className="text-sm text-gray-600">
                      <div>
                        Created:{" "}
                        {new Date(selectedMemory.created_at).toLocaleString()}
                      </div>
                      {selectedMemory.last_used && (
                        <div>
                          Last Used:{" "}
                          {new Date(selectedMemory.last_used).toLocaleString()}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};
