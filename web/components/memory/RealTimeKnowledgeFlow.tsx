"use client";

import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Brain,
  Database,
  Zap,
  Eye,
  MessageSquare,
  FileText,
  Network,
  Activity,
  Clock,
  CheckCircle,
  AlertCircle,
  Info,
} from "lucide-react";

interface KnowledgeEvent {
  id: string;
  timestamp: string;
  type: "observation" | "analysis" | "insight" | "note_creation";
  title: string;
  content: string;
  confidence?: number;
  tables_involved?: string[];
  status: "processing" | "completed" | "failed";
}

interface LiveStats {
  active_observations: number;
  notes_created: number;
  insights_generated: number;
  confidence_avg: number;
}

const RealTimeKnowledgeFlow: React.FC = () => {
  const [events, setEvents] = useState<KnowledgeEvent[]>([]);
  const [liveStats, setLiveStats] = useState<LiveStats>({
    active_observations: 0,
    notes_created: 0,
    insights_generated: 0,
    confidence_avg: 0,
  });
  const [isActive, setIsActive] = useState(false);

  // Monitor real-time events (this would connect to actual agent events in production)
  useEffect(() => {
    if (!isActive) return;

    // In a real implementation, this would connect to a WebSocket or SSE stream
    // from the agent to receive actual events. For now, we'll show a placeholder.

    const interval = setInterval(() => {
      // This is a placeholder - in production, this would be replaced with
      // actual event streaming from the agent's note-taking system
      console.log("Real-time knowledge monitoring active...");
    }, 5000);

    return () => clearInterval(interval);
  }, [isActive]);

  const getEventIcon = (type: KnowledgeEvent["type"]) => {
    switch (type) {
      case "observation":
        return <Eye className="h-4 w-4 text-blue-600" />;
      case "analysis":
        return <Brain className="h-4 w-4 text-purple-600" />;
      case "insight":
        return <Zap className="h-4 w-4 text-yellow-600" />;
      case "note_creation":
        return <FileText className="h-4 w-4 text-green-600" />;
    }
  };

  const getStatusIcon = (status: KnowledgeEvent["status"]) => {
    switch (status) {
      case "processing":
        return <Activity className="h-4 w-4 text-blue-600 animate-spin" />;
      case "completed":
        return <CheckCircle className="h-4 w-4 text-green-600" />;
      case "failed":
        return <AlertCircle className="h-4 w-4 text-red-600" />;
    }
  };

  const getEventColor = (type: KnowledgeEvent["type"]) => {
    switch (type) {
      case "observation":
        return "bg-blue-50 border-blue-200";
      case "analysis":
        return "bg-purple-50 border-purple-200";
      case "insight":
        return "bg-yellow-50 border-yellow-200";
      case "note_creation":
        return "bg-green-50 border-green-200";
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Activity className="h-6 w-6 text-green-600" />
          <h2 className="text-2xl font-bold">Real-Time Knowledge Flow</h2>
        </div>
        <Button
          onClick={() => setIsActive(!isActive)}
          variant={isActive ? "destructive" : "default"}
          className="flex items-center space-x-2"
        >
          {isActive ? (
            <Activity className="h-4 w-4" />
          ) : (
            <Eye className="h-4 w-4" />
          )}
          <span>{isActive ? "Stop Monitoring" : "Start Monitoring"}</span>
        </Button>
      </div>

      {/* Live Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="bg-blue-50 border-blue-200">
          <CardContent className="p-4">
            <div className="flex items-center space-x-2">
              <Eye className="h-5 w-5 text-blue-600" />
              <div>
                <p className="text-sm text-blue-700">Active Observations</p>
                <p className="text-2xl font-bold text-blue-800">
                  {liveStats.active_observations}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-green-50 border-green-200">
          <CardContent className="p-4">
            <div className="flex items-center space-x-2">
              <FileText className="h-5 w-5 text-green-600" />
              <div>
                <p className="text-sm text-green-700">Notes Created</p>
                <p className="text-2xl font-bold text-green-800">
                  {liveStats.notes_created}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-yellow-50 border-yellow-200">
          <CardContent className="p-4">
            <div className="flex items-center space-x-2">
              <Zap className="h-5 w-5 text-yellow-600" />
              <div>
                <p className="text-sm text-yellow-700">Insights Generated</p>
                <p className="text-2xl font-bold text-yellow-800">
                  {liveStats.insights_generated}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-purple-50 border-purple-200">
          <CardContent className="p-4">
            <div className="flex items-center space-x-2">
              <Brain className="h-5 w-5 text-purple-600" />
              <div>
                <p className="text-sm text-purple-700">Avg Confidence</p>
                <p className="text-2xl font-bold text-purple-800">
                  {Math.round(liveStats.confidence_avg * 100)}%
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Event Stream */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <MessageSquare className="h-5 w-5 text-blue-600" />
            <span>Knowledge Event Stream</span>
            {isActive && (
              <Badge
                variant="outline"
                className="ml-2 flex items-center space-x-1"
              >
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                <span>Live</span>
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {events.length === 0 ? (
            <div className="text-center py-12">
              <Info className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600">
                {isActive
                  ? "Monitoring for database interactions... Real-time events will appear here when the agent is actively exploring the database."
                  : 'Click "Start Monitoring" to see real-time knowledge flow'}
              </p>
            </div>
          ) : (
            <ScrollArea className="h-[500px]">
              <div className="space-y-3">
                {events.map((event) => (
                  <Card
                    key={event.id}
                    className={`${getEventColor(
                      event.type
                    )} transition-all duration-300`}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex items-start space-x-3 flex-1">
                          <div className="flex items-center space-x-2">
                            {getEventIcon(event.type)}
                            {getStatusIcon(event.status)}
                          </div>
                          <div className="flex-1">
                            <div className="flex items-center space-x-2 mb-1">
                              <h4 className="font-medium text-sm">
                                {event.title}
                              </h4>
                              <Badge
                                variant="outline"
                                className="text-xs capitalize"
                              >
                                {event.type.replace("_", " ")}
                              </Badge>
                              {event.confidence && (
                                <span className="text-xs text-gray-600">
                                  {Math.round(event.confidence * 100)}%
                                  confidence
                                </span>
                              )}
                            </div>
                            <p className="text-sm text-gray-700 mb-2">
                              {event.content}
                            </p>
                            {event.tables_involved &&
                              event.tables_involved.length > 0 && (
                                <div className="flex items-center space-x-2">
                                  <Database className="h-3 w-3 text-gray-500" />
                                  <div className="flex flex-wrap gap-1">
                                    {event.tables_involved.map((table, i) => (
                                      <Badge
                                        key={i}
                                        variant="secondary"
                                        className="text-xs"
                                      >
                                        {table}
                                      </Badge>
                                    ))}
                                  </div>
                                </div>
                              )}
                          </div>
                        </div>
                        <div className="flex items-center space-x-1 text-xs text-gray-500">
                          <Clock className="h-3 w-3" />
                          <span>
                            {new Date(event.timestamp).toLocaleTimeString()}
                          </span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </ScrollArea>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default RealTimeKnowledgeFlow;
