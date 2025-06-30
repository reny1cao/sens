/**
 * BIRD-CRITIC Evaluation Page
 *
 * Main page for running and monitoring BIRD-CRITIC evaluations
 * with real-time agent thinking steps display.
 *
 * Refined with Jony Ive-inspired design principles:
 * - Functional simplicity and clarity
 * - Elegant material design
 * - Progressive information disclosure
 */

import React from "react";
import { BirdCriticDashboard } from "@/components/evaluation/BirdCriticDashboard";

export default function EvaluationPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-gray-100 dark:from-gray-950 dark:via-gray-900 dark:to-gray-950">
      {/* Subtle background pattern for depth */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_1px_1px,rgba(0,0,0,0.02)_1px,transparent_0)] bg-[size:32px_32px] dark:bg-[radial-gradient(circle_at_1px_1px,rgba(255,255,255,0.02)_1px,transparent_0)]" />

      {/* Main content with refined container */}
      <div className="relative">
        <BirdCriticDashboard />
      </div>
    </div>
  );
}

export const metadata = {
  title: "BIRD-CRITIC Evaluation | SENS",
  description:
    "Run BIRD-CRITIC text-to-SQL evaluations with real-time agent thinking steps",
};
