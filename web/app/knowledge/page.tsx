"use client";

import React, { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Header } from "@/components/ui/header";
import {
  Brain,
  Activity,
  BarChart3,
  Database,
  FileText,
  Network,
  TrendingUp,
  Eye,
  Zap,
  MessageSquare,
  Circle,
} from "lucide-react";

import DatabaseKnowledgeVisualization from "@/components/memory/DatabaseKnowledgeVisualization";
import RealTimeKnowledgeFlow from "@/components/memory/RealTimeKnowledgeFlow";

const KnowledgePage: React.FC = () => {
  const [activeTab, setActiveTab] = useState("overview");

  return (
    <div className="min-h-screen bg-white">
      <Header currentPage="knowledge" />

      <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8">
        {/* Hero Section */}
        <div className="text-center mb-12">
          <div className="flex items-center justify-center gap-3 mb-4">
            <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center">
              <Brain className="h-6 w-6 text-white" />
            </div>
            <h1 className="text-3xl font-light text-gray-900">
              Knowledge System
            </h1>
          </div>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto leading-relaxed">
            Intelligent database exploration powered by LLM analysis.
            Watch as the system learns and builds knowledge through every interaction.
          </p>
        </div>

        {/* Status Indicators */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          <Card className="border-0 shadow-sm bg-gradient-to-br from-blue-50 to-blue-100">
            <CardContent className="p-6">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 bg-blue-500 rounded-lg flex items-center justify-center">
                  <FileText className="h-5 w-5 text-white" />
                </div>
                <div>
                  <p className="text-sm font-medium text-blue-700">Active Learning</p>
                  <div className="flex items-center gap-2 mt-1">
                    <Circle className="h-2 w-2 fill-green-500 text-green-500" />
                    <span className="text-xs text-blue-600">System Ready</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-0 shadow-sm bg-gradient-to-br from-purple-50 to-purple-100">
            <CardContent className="p-6">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 bg-purple-500 rounded-lg flex items-center justify-center">
                  <Network className="h-5 w-5 text-white" />
                </div>
                <div>
                  <p className="text-sm font-medium text-purple-700">LLM Analysis</p>
                  <div className="flex items-center gap-2 mt-1">
                    <Circle className="h-2 w-2 fill-green-500 text-green-500" />
                    <span className="text-xs text-purple-600">Connected</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-0 shadow-sm bg-gradient-to-br from-green-50 to-green-100">
            <CardContent className="p-6">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 bg-green-500 rounded-lg flex items-center justify-center">
                  <TrendingUp className="h-5 w-5 text-white" />
                </div>
                <div>
                  <p className="text-sm font-medium text-green-700">Insights</p>
                  <div className="flex items-center gap-2 mt-1">
                    <Circle className="h-2 w-2 fill-blue-500 text-blue-500" />
                    <span className="text-xs text-green-600">Generating</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Main Content */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-8">
          <TabsList className="grid w-full grid-cols-2 max-w-md mx-auto bg-gray-100 p-1 rounded-lg">
            <TabsTrigger
              value="overview"
              className="data-[state=active]:bg-white data-[state=active]:shadow-sm"
            >
              <Eye className="h-4 w-4 mr-2" />
              Overview
            </TabsTrigger>
            <TabsTrigger
              value="realtime"
              className="data-[state=active]:bg-white data-[state=active]:shadow-sm"
            >
              <Zap className="h-4 w-4 mr-2" />
              Real-Time
            </TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-8">
            <DatabaseKnowledgeVisualization />
          </TabsContent>

          <TabsContent value="realtime" className="space-y-8">
            <RealTimeKnowledgeFlow />
          </TabsContent>
        </Tabs>

        {/* Technical Architecture */}
        <div className="mt-16 pt-12 border-t border-gray-100">
          <div className="text-center mb-8">
            <h2 className="text-2xl font-light text-gray-900 mb-3">
              Technical Architecture
            </h2>
            <p className="text-gray-600">
              How the system processes and learns from database interactions
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <Card className="border-0 shadow-sm">
              <CardHeader className="pb-4">
                <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center mb-3">
                  <Database className="h-4 w-4 text-white" />
                </div>
                <CardTitle className="text-lg font-medium">Observation</CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <p className="text-sm text-gray-600 leading-relaxed">
                  Monitors all database interactions, SQL queries, and exploration patterns in real-time.
                </p>
              </CardContent>
            </Card>

            <Card className="border-0 shadow-sm">
              <CardHeader className="pb-4">
                <div className="w-8 h-8 bg-purple-500 rounded-lg flex items-center justify-center mb-3">
                  <Brain className="h-4 w-4 text-white" />
                </div>
                <CardTitle className="text-lg font-medium">Analysis</CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <p className="text-sm text-gray-600 leading-relaxed">
                  LLM processes interactions to extract semantic meaning, patterns, and relationships.
                </p>
              </CardContent>
            </Card>

            <Card className="border-0 shadow-sm">
              <CardHeader className="pb-4">
                <div className="w-8 h-8 bg-green-500 rounded-lg flex items-center justify-center mb-3">
                  <FileText className="h-4 w-4 text-white" />
                </div>
                <CardTitle className="text-lg font-medium">Knowledge</CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <p className="text-sm text-gray-600 leading-relaxed">
                  Generates structured insights, categorizes findings, and builds comprehensive database knowledge.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
};

export default KnowledgePage;
