/**
 * BIRD Evaluation Suite Page
 *
 * Unified page for running and monitoring different BIRD evaluations
 * (BIRD-CRITIC and BIRD-SQL-DEV) with real-time agent thinking steps display.
 *
 * Uses the next-generation unified evaluation system with:
 * - Modern hook-based architecture
 * - Robust real-time streaming without race conditions
 * - Multi-dataset support with type safety
 * - Progressive disclosure and responsive design
 */

import React from "react";
import { UnifiedEvaluationDashboard } from "@/components/evaluation/UnifiedEvaluationDashboard";

export default function EvaluationPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50 dark:from-slate-950 dark:via-slate-900 dark:to-blue-950">
      {/* Sophisticated background pattern */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_1px_1px,rgba(59,130,246,0.08)_1px,transparent_0)] bg-[size:48px_48px] dark:bg-[radial-gradient(circle_at_1px_1px,rgba(59,130,246,0.12)_1px,transparent_0)]" />

      {/* Subtle overlay for depth */}
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-white/20 to-transparent dark:via-slate-900/20" />

      {/* Main content with refined spacing */}
      <div className="relative p-6 lg:p-8">
        <UnifiedEvaluationDashboard />
      </div>
    </div>
  );
}

export const metadata = {
  title: "BIRD Evaluation Suite | SENS",
  description:
    "Unified evaluation dashboard for BIRD-CRITIC and BIRD-SQL-DEV datasets with real-time agent thinking steps",
};
