"use client";

import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Progress } from "@/components/ui/progress";
import {
  Database,
  Brain,
  Network,
  FileText,
  TrendingUp,
  Search,
  Clock,
  Tag,
  Lightbulb,
  Eye,
  BarChart3,
  GitBranch,
} from "lucide-react";

interface DatabaseNote {
  timestamp: string;
  category: string;
  title: string;
  content: string;
  tables_involved: string[];
  confidence: number;
  source: string;
  tags: string[];
  insights: string[];
}

interface TableKnowledge {
  table_name: string;
  columns: string[];
  relationships: string[];
  data_patterns: string[];
  insights: string[];
  last_updated: string;
}

interface KnowledgeStats {
  total_notes: number;
  categories: Record<string, number>;
  confidence_distribution: Record<string, number>;
  recent_discoveries: number;
  tables_covered: number;
}

const DatabaseKnowledgeVisualization: React.FC = () => {
  const [notes, setNotes] = useState<DatabaseNote[]>([]);
  const [tableKnowledge, setTableKnowledge] = useState<
    Record<string, TableKnowledge>
  >({});
  const [stats, setStats] = useState<KnowledgeStats | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  // Load real data from the knowledge API
  useEffect(() => {
    const loadKnowledgeData = async () => {
      try {
        const response = await fetch("/api/knowledge");
        if (!response.ok) {
          throw new Error("Failed to fetch knowledge data");
        }

        const data = await response.json();

        setNotes(data.notes || []);
        setTableKnowledge(data.table_knowledge || {});
        setStats(
          data.stats || {
            total_notes: 0,
            categories: {},
            confidence_distribution: { high: 0, medium: 0, low: 0 },
            recent_discoveries: 0,
            tables_covered: 0,
          }
        );
        setIsLoading(false);
      } catch (error) {
        console.error("Error loading knowledge data:", error);
        setIsLoading(false);
      }
    };

    loadKnowledgeData();
  }, []);

  const filteredNotes = notes.filter((note) => {
    const matchesCategory =
      selectedCategory === "all" || note.category === selectedCategory;
    const matchesSearch =
      searchTerm === "" ||
      note.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      note.content.toLowerCase().includes(searchTerm.toLowerCase()) ||
      note.tags.some((tag) =>
        tag.toLowerCase().includes(searchTerm.toLowerCase())
      );
    return matchesCategory && matchesSearch;
  });

  const getCategoryColor = (category: string) => {
    const colors = {
      schema_discovery: "bg-blue-100 text-blue-800",
      data_insight: "bg-green-100 text-green-800",
      relationship: "bg-purple-100 text-purple-800",
      query_pattern: "bg-yellow-100 text-yellow-800",
      performance: "bg-red-100 text-red-800",
    };
    return (
      colors[category as keyof typeof colors] || "bg-gray-100 text-gray-800"
    );
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.9) return "text-green-600";
    if (confidence >= 0.7) return "text-yellow-600";
    return "text-red-600";
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <Brain className="h-8 w-8 animate-spin mx-auto mb-4" />
          <p>Loading database knowledge...</p>
        </div>
      </div>
    );
  }

  // Show empty state if no notes are available
  if (notes.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-700 mb-2">
            No Knowledge Notes Yet
          </h3>
          <p className="text-gray-500 mb-4">
            The LLM note-taking system will create notes as you interact with
            the database through the agent.
          </p>
          <p className="text-sm text-gray-400">
            Try asking questions in the Chat interface to generate database
            knowledge.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Brain className="h-6 w-6 text-blue-600" />
          <h2 className="text-2xl font-bold">
            Database Knowledge Visualization
          </h2>
        </div>
        <Badge variant="outline" className="flex items-center space-x-1">
          <Eye className="h-4 w-4" />
          <span>LLM-Powered Analysis</span>
        </Badge>
      </div>

      {/* Stats Overview */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center space-x-2">
                <FileText className="h-5 w-5 text-blue-600" />
                <div>
                  <p className="text-sm text-gray-600">Total Notes</p>
                  <p className="text-2xl font-bold">{stats.total_notes}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-center space-x-2">
                <Database className="h-5 w-5 text-green-600" />
                <div>
                  <p className="text-sm text-gray-600">Tables Covered</p>
                  <p className="text-2xl font-bold">{stats.tables_covered}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-center space-x-2">
                <TrendingUp className="h-5 w-5 text-purple-600" />
                <div>
                  <p className="text-sm text-gray-600">Recent Discoveries</p>
                  <p className="text-2xl font-bold">
                    {stats.recent_discoveries}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-center space-x-2">
                <BarChart3 className="h-5 w-5 text-orange-600" />
                <div>
                  <p className="text-sm text-gray-600">High Confidence</p>
                  <p className="text-2xl font-bold">
                    {stats.confidence_distribution.high}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Main Content */}
      <Tabs defaultValue="notes" className="space-y-4">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="notes" className="flex items-center space-x-2">
            <FileText className="h-4 w-4" />
            <span>Knowledge Notes</span>
          </TabsTrigger>
          <TabsTrigger value="tables" className="flex items-center space-x-2">
            <Database className="h-4 w-4" />
            <span>Table Knowledge</span>
          </TabsTrigger>
          <TabsTrigger value="insights" className="flex items-center space-x-2">
            <Lightbulb className="h-4 w-4" />
            <span>Insights</span>
          </TabsTrigger>
        </TabsList>

        {/* Notes Tab */}
        <TabsContent value="notes" className="space-y-4">
          {/* Filters */}
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search notes..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="all">All Categories</option>
              <option value="schema_discovery">Schema Discovery</option>
              <option value="data_insight">Data Insights</option>
              <option value="relationship">Relationships</option>
              <option value="query_pattern">Query Patterns</option>
              <option value="performance">Performance</option>
            </select>
          </div>

          {/* Notes List */}
          <ScrollArea className="h-[600px]">
            <div className="space-y-4">
              {filteredNotes.map((note, index) => (
                <Card key={index} className="hover:shadow-md transition-shadow">
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <CardTitle className="text-lg">{note.title}</CardTitle>
                        <div className="flex items-center space-x-2 mt-1">
                          <Badge className={getCategoryColor(note.category)}>
                            {note.category.replace("_", " ")}
                          </Badge>
                          <span
                            className={`text-sm font-medium ${getConfidenceColor(
                              note.confidence
                            )}`}
                          >
                            {Math.round(note.confidence * 100)}% confidence
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center space-x-1 text-sm text-gray-500">
                        <Clock className="h-4 w-4" />
                        <span>
                          {new Date(note.timestamp).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <p className="text-gray-700">{note.content}</p>

                    {note.tables_involved.length > 0 && (
                      <div className="flex items-center space-x-2">
                        <Database className="h-4 w-4 text-gray-500" />
                        <span className="text-sm text-gray-600">Tables:</span>
                        <div className="flex flex-wrap gap-1">
                          {note.tables_involved.map((table, i) => (
                            <Badge
                              key={i}
                              variant="outline"
                              className="text-xs"
                            >
                              {table}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {note.tags.length > 0 && (
                      <div className="flex items-center space-x-2">
                        <Tag className="h-4 w-4 text-gray-500" />
                        <div className="flex flex-wrap gap-1">
                          {note.tags.map((tag, i) => (
                            <Badge
                              key={i}
                              variant="secondary"
                              className="text-xs"
                            >
                              {tag}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {note.insights.length > 0 && (
                      <div className="bg-blue-50 p-3 rounded-md">
                        <div className="flex items-center space-x-2 mb-2">
                          <Lightbulb className="h-4 w-4 text-blue-600" />
                          <span className="text-sm font-medium text-blue-800">
                            Key Insights
                          </span>
                        </div>
                        <ul className="list-disc list-inside text-sm text-blue-700 space-y-1">
                          {note.insights.map((insight, i) => (
                            <li key={i}>{insight}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </ScrollArea>
        </TabsContent>

        {/* Table Knowledge Tab */}
        <TabsContent value="tables" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {Object.values(tableKnowledge).map((table, index) => (
              <Card key={index} className="hover:shadow-md transition-shadow">
                <CardHeader>
                  <CardTitle className="flex items-center space-x-2">
                    <Database className="h-5 w-5 text-blue-600" />
                    <span>{table.table_name}</span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <h4 className="font-medium text-sm text-gray-700 mb-2">
                      Columns
                    </h4>
                    <div className="flex flex-wrap gap-1">
                      {table.columns.map((column, i) => (
                        <Badge key={i} variant="outline" className="text-xs">
                          {column}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  <div>
                    <h4 className="font-medium text-sm text-gray-700 mb-2">
                      Relationships
                    </h4>
                    <div className="space-y-1">
                      {table.relationships.map((rel, i) => (
                        <div
                          key={i}
                          className="flex items-center space-x-2 text-sm"
                        >
                          <GitBranch className="h-3 w-3 text-gray-500" />
                          <span>{rel}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div>
                    <h4 className="font-medium text-sm text-gray-700 mb-2">
                      Data Patterns
                    </h4>
                    <ul className="list-disc list-inside text-sm text-gray-600 space-y-1">
                      {table.data_patterns.map((pattern, i) => (
                        <li key={i}>{pattern}</li>
                      ))}
                    </ul>
                  </div>

                  <div className="bg-green-50 p-3 rounded-md">
                    <div className="flex items-center space-x-2 mb-2">
                      <Lightbulb className="h-4 w-4 text-green-600" />
                      <span className="text-sm font-medium text-green-800">
                        Insights
                      </span>
                    </div>
                    <ul className="list-disc list-inside text-sm text-green-700 space-y-1">
                      {table.insights.map((insight, i) => (
                        <li key={i}>{insight}</li>
                      ))}
                    </ul>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Insights Tab */}
        <TabsContent value="insights" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <BarChart3 className="h-5 w-5 text-purple-600" />
                  <span>Category Distribution</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {stats && (
                  <div className="space-y-3">
                    {Object.entries(stats.categories).map(
                      ([category, count]) => (
                        <div
                          key={category}
                          className="flex items-center justify-between"
                        >
                          <span className="text-sm capitalize">
                            {category.replace("_", " ")}
                          </span>
                          <div className="flex items-center space-x-2">
                            <Progress
                              value={(count / stats.total_notes) * 100}
                              className="w-20"
                            />
                            <span className="text-sm font-medium">{count}</span>
                          </div>
                        </div>
                      )
                    )}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <TrendingUp className="h-5 w-5 text-green-600" />
                  <span>Confidence Levels</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {stats && (
                  <div className="space-y-3">
                    {Object.entries(stats.confidence_distribution).map(
                      ([level, count]) => (
                        <div
                          key={level}
                          className="flex items-center justify-between"
                        >
                          <span className="text-sm capitalize">
                            {level} confidence
                          </span>
                          <div className="flex items-center space-x-2">
                            <Progress
                              value={(count / stats.total_notes) * 100}
                              className="w-20"
                            />
                            <span className="text-sm font-medium">{count}</span>
                          </div>
                        </div>
                      )
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default DatabaseKnowledgeVisualization;
