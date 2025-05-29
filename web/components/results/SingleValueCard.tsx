'use client';

interface SingleValueCardProps {
  value: any;
  label: string;
}

export function SingleValueCard({ value, label }: SingleValueCardProps) {
  const formatValue = (val: any): string => {
    if (val === null || val === undefined) return 'N/A';
    if (typeof val === 'boolean') return val ? 'Yes' : 'No';
    if (typeof val === 'number') {
      // Format large numbers with commas
      if (Number.isInteger(val) && Math.abs(val) > 999) {
        return val.toLocaleString();
      }
      // Format decimals to 2 places
      if (!Number.isInteger(val)) {
        return val.toFixed(2);
      }
      return val.toString();
    }
    if (val instanceof Date) {
      return val.toLocaleDateString();
    }
    return String(val);
  };

  const getValueSize = (val: string): string => {
    if (val.length > 10) return 'text-3xl';
    if (val.length > 6) return 'text-4xl';
    return 'text-5xl';
  };

  const formattedValue = formatValue(value);

  return (
    <div className="text-center py-8">
      <div className={`font-bold text-gray-900 ${getValueSize(formattedValue)}`}>
        {formattedValue}
      </div>
      <div className="text-lg text-gray-600 mt-2 capitalize">
        {label.replace(/_/g, ' ')}
      </div>
    </div>
  );
}
