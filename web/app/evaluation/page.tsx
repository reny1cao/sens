/**
 * BIRD-CRITIC Evaluation Page
 *
 * Main page for running and monitoring BIRD-CRITIC evaluations
 * with real-time agent thinking steps display.
 */

import React from 'react';
import { BirdCriticDashboard } from '@/components/evaluation/BirdCriticDashboard';

export default function EvaluationPage() {
  return (
    <div className="min-h-screen bg-background">
      <BirdCriticDashboard />
    </div>
  );
}

export const metadata = {
  title: 'BIRD-CRITIC Evaluation | SENS',
  description: 'Run BIRD-CRITIC text-to-SQL evaluations with real-time agent thinking steps',
};
