'use client';

import { Card, CardContent } from '@/components/ui/card';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface SingleValueCardProps {
  value: any;
  label: string;
}

export function SingleValueCard({ value, label }: SingleValueCardProps) {
  const formatValue = (val: any): { display: string; type: string } => {
    if (val === null || val === undefined) {
      return { display: 'N/A', type: 'null' };
    }

    if (typeof val === 'boolean') {
      return { display: val ? 'Yes' : 'No', type: 'boolean' };
    }

    if (typeof val === 'number') {
      let display: string;
      let type = 'number';

      // Check if it's a percentage (column name contains 'percent' or 'rate')
      if (label.toLowerCase().includes('percent') ||
          label.toLowerCase().includes('rate') ||
          label.toLowerCase().includes('ratio')) {
        display = `${val.toFixed(2)}%`;
        type = 'percentage';
      }
      // Check if it's currency (column name contains 'price', 'amount', 'cost')
      else if (label.toLowerCase().includes('price') ||
               label.toLowerCase().includes('amount') ||
               label.toLowerCase().includes('cost') ||
               label.toLowerCase().includes('revenue')) {
        display = `$${val.toLocaleString(undefined, {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2
        })}`;
        type = 'currency';
      }
      // Check if it's volume
      else if (label.toLowerCase().includes('volume')) {
        const formatted = val.toLocaleString();
        display = formatted;
        type = 'volume';
      }
      // Regular number formatting
      else if (Number.isInteger(val) && Math.abs(val) > 999) {
        display = val.toLocaleString();
      } else if (!Number.isInteger(val)) {
        display = val.toFixed(2);
      } else {
        display = val.toString();
      }

      return { display, type };
    }

    if (val instanceof Date ||
        (typeof val === 'string' && !isNaN(Date.parse(val)) &&
         (label.toLowerCase().includes('date') || label.toLowerCase().includes('time')))) {
      const date = val instanceof Date ? val : new Date(val);
      return {
        display: date.toLocaleDateString(undefined, {
          year: 'numeric',
          month: 'long',
          day: 'numeric'
        }),
        type: 'date'
      };
    }

    return { display: String(val), type: 'string' };
  };

  const getValueSize = (val: string): string => {
    if (val.length > 20) return 'text-2xl';
    if (val.length > 15) return 'text-3xl';
    if (val.length > 10) return 'text-4xl';
    return 'text-5xl';
  };

  const { display: formattedValue, type: valueType } = formatValue(value);
  const cleanLabel = label
    .replace(/_/g, ' ')
    .split(' ')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');

  // Determine if we should show a trend indicator (for percentages)
  const getTrendIcon = () => {
    if (valueType === 'percentage' && typeof value === 'number') {
      if (value > 0) return <TrendingUp className="h-5 w-5 text-green-500" />;
      if (value < 0) return <TrendingDown className="h-5 w-5 text-red-500" />;
      return <Minus className="h-5 w-5 text-gray-400" />;
    }
    return null;
  };

  const getValueColor = () => {
    if (valueType === 'percentage' && typeof value === 'number') {
      if (value > 0) return 'text-green-600';
      if (value < 0) return 'text-red-600';
    }
    return 'text-foreground';
  };

  return (
    <Card className="bg-gradient-to-br from-background to-muted/20">
      <CardContent className="flex flex-col items-center justify-center py-12">
        <div className="text-sm text-muted-foreground mb-2 uppercase tracking-wider">
          {cleanLabel}
        </div>
        <div className="flex items-center gap-3">
          {getTrendIcon()}
          <div className={`font-bold ${getValueSize(formattedValue)} ${getValueColor()}`}>
            {formattedValue}
          </div>
        </div>
        {valueType === 'date' && (
          <div className="text-xs text-muted-foreground mt-2">
            {new Date(value).toLocaleTimeString()}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
