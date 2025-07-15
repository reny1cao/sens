"use client";

import React from "react";
import { Database, MessageSquare, BarChart3, Brain } from "lucide-react";

interface HeaderProps {
  currentPage: "chat" | "schema" | "knowledge" | "eval";
}

export const Header: React.FC<HeaderProps> = ({ currentPage }) => {
  const navItems = [
    { key: "chat", label: "Chat", href: "/chat", icon: MessageSquare },
    { key: "schema", label: "Schema", href: "/schema", icon: BarChart3 },
    { key: "knowledge", label: "Knowledge", href: "/knowledge", icon: Brain },
    { key: "eval", label: "Eval", href: "/evaluation", icon: BarChart3 },
  ];

  return (
    <header className="bg-white/80 backdrop-blur-sm border-b border-gray-100 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          {/* Logo Section - Jony Ive inspired simplicity */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg flex items-center justify-center">
                <Database className="h-4 w-4 text-white" />
              </div>
              <div className="flex flex-col">
                <h1 className="text-lg font-medium text-gray-900 tracking-tight">
                  SENS
                </h1>
                <span className="text-xs text-gray-500 -mt-1">
                  Natural Language SQL
                </span>
              </div>
            </div>
          </div>

          {/* Navigation - Clean and minimal */}
          <nav className="flex items-center">
            <div className="flex items-center bg-gray-50 rounded-lg p-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = currentPage === item.key;

                return (
                  <a
                    key={item.key}
                    href={item.href}
                    className={`
                      flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all duration-200
                      ${
                        isActive
                          ? "bg-white text-blue-600 shadow-sm"
                          : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"
                      }
                    `}
                  >
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </a>
                );
              })}
            </div>
          </nav>
        </div>
      </div>
    </header>
  );
};
