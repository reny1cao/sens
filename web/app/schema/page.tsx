'use client';

import { useState, useEffect } from 'react';
import { SchemaVisualizer } from '@/components/schema-viz/SchemaVisualizer';
import { UniversalSchema } from '@/types/schema';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Database } from 'lucide-react';

// Mock schema data for demonstration
const mockSchema: UniversalSchema = {
  source: {
    type: 'postgresql',
    version: '14.5',
    name: 'financial_db'
  },
  metadata: {
    extractedAt: new Date(),
    totalTables: 9,
    totalColumns: 85,
    totalRelationships: 15
  },
  entities: [
    {
      id: 'securities',
      name: 'securities',
      type: 'table',
      category: 'Reference Data',
      displayName: 'Securities',
      description: 'Master table for all financial securities including stocks, bonds, and ETFs',
      stats: { rowCount: 15000, lastUpdated: new Date() },
      attributes: [
        {
          id: 'sec_id',
          name: 'security_id',
          dataType: 'uuid',
          semanticType: 'id' as any,
          constraints: { primaryKey: true, nullable: false }
        },
        {
          id: 'sec_symbol',
          name: 'symbol',
          dataType: 'varchar(10)',
          semanticType: 'text' as any,
          constraints: { unique: true, nullable: false }
        },
        {
          id: 'sec_name',
          name: 'name',
          dataType: 'varchar(255)',
          semanticType: 'text' as any,
          constraints: { nullable: false }
        },
        {
          id: 'sec_type',
          name: 'security_type',
          dataType: 'varchar(50)',
          semanticType: 'text' as any,
          constraints: { nullable: false }
        }
      ]
    },
    {
      id: 'daily_prices',
      name: 'daily_prices',
      type: 'table',
      category: 'Market Data',
      displayName: 'Daily Prices',
      description: 'Daily price data for all securities',
      stats: { rowCount: 5000000, lastUpdated: new Date() },
      isPartitioned: true,
      partitionInfo: {
        strategy: 'range',
        key: 'trade_date',
        parentTable: 'daily_prices'
      },
      attributes: [
        {
          id: 'dp_id',
          name: 'price_id',
          dataType: 'uuid',
          semanticType: 'id' as any,
          constraints: { primaryKey: true }
        },
        {
          id: 'dp_sec_id',
          name: 'security_id',
          dataType: 'uuid',
          semanticType: 'id' as any,
          constraints: { 
            foreignKey: { entity: 'securities', attribute: 'security_id' },
            nullable: false
          }
        },
        {
          id: 'dp_date',
          name: 'trade_date',
          dataType: 'date',
          semanticType: 'date' as any,
          constraints: { nullable: false }
        },
        {
          id: 'dp_open',
          name: 'open_price',
          dataType: 'decimal(10,2)',
          semanticType: 'money' as any,
          constraints: { nullable: false },
          metadata: { unit: 'USD' }
        },
        {
          id: 'dp_close',
          name: 'close_price',
          dataType: 'decimal(10,2)',
          semanticType: 'money' as any,
          constraints: { nullable: false },
          metadata: { unit: 'USD' }
        },
        {
          id: 'dp_volume',
          name: 'volume',
          dataType: 'bigint',
          semanticType: 'quantity' as any,
          constraints: { nullable: false }
        }
      ]
    },
    {
      id: 'portfolios',
      name: 'portfolios',
      type: 'table',
      category: 'Analytics',
      displayName: 'Portfolios',
      description: 'Investment portfolios and strategies',
      stats: { rowCount: 500, lastUpdated: new Date() },
      attributes: [
        {
          id: 'port_id',
          name: 'portfolio_id',
          dataType: 'uuid',
          semanticType: 'id' as any,
          constraints: { primaryKey: true }
        },
        {
          id: 'port_name',
          name: 'name',
          dataType: 'varchar(255)',
          semanticType: 'text' as any,
          constraints: { nullable: false }
        },
        {
          id: 'port_value',
          name: 'total_value',
          dataType: 'decimal(15,2)',
          semanticType: 'money' as any,
          constraints: { nullable: true },
          metadata: { unit: 'USD' }
        }
      ]
    },
    {
      id: 'portfolio_holdings',
      name: 'portfolio_holdings',
      type: 'table',
      category: 'Analytics',
      displayName: 'Portfolio Holdings',
      description: 'Securities held in each portfolio',
      stats: { rowCount: 25000, lastUpdated: new Date() },
      attributes: [
        {
          id: 'ph_id',
          name: 'holding_id',
          dataType: 'uuid',
          semanticType: 'id' as any,
          constraints: { primaryKey: true }
        },
        {
          id: 'ph_port_id',
          name: 'portfolio_id',
          dataType: 'uuid',
          semanticType: 'id' as any,
          constraints: { 
            foreignKey: { entity: 'portfolios', attribute: 'portfolio_id' },
            nullable: false
          }
        },
        {
          id: 'ph_sec_id',
          name: 'security_id',
          dataType: 'uuid',
          semanticType: 'id' as any,
          constraints: { 
            foreignKey: { entity: 'securities', attribute: 'security_id' },
            nullable: false
          }
        },
        {
          id: 'ph_quantity',
          name: 'quantity',
          dataType: 'decimal(15,4)',
          semanticType: 'quantity' as any,
          constraints: { nullable: false }
        },
        {
          id: 'ph_weight',
          name: 'weight_percent',
          dataType: 'decimal(5,2)',
          semanticType: 'percentage' as any,
          constraints: { nullable: true },
          metadata: { unit: '%' }
        }
      ]
    },
    {
      id: 'exchanges',
      name: 'exchanges',
      type: 'table',
      category: 'Reference Data',
      displayName: 'Exchanges',
      description: 'Stock exchanges and trading venues',
      stats: { rowCount: 50, lastUpdated: new Date() },
      attributes: [
        {
          id: 'exch_id',
          name: 'exchange_id',
          dataType: 'uuid',
          semanticType: 'id' as any,
          constraints: { primaryKey: true }
        },
        {
          id: 'exch_code',
          name: 'exchange_code',
          dataType: 'varchar(10)',
          semanticType: 'text' as any,
          constraints: { unique: true, nullable: false }
        },
        {
          id: 'exch_name',
          name: 'name',
          dataType: 'varchar(100)',
          semanticType: 'text' as any,
          constraints: { nullable: false }
        }
      ]
    },
    {
      id: 'sectors',
      name: 'sectors',
      type: 'table',
      category: 'Reference Data',
      displayName: 'Sectors',
      description: 'Business sectors classification',
      stats: { rowCount: 11, lastUpdated: new Date() },
      attributes: [
        {
          id: 'sect_id',
          name: 'sector_id',
          dataType: 'uuid',
          semanticType: 'id' as any,
          constraints: { primaryKey: true }
        },
        {
          id: 'sect_name',
          name: 'sector_name',
          dataType: 'varchar(100)',
          semanticType: 'text' as any,
          constraints: { unique: true, nullable: false }
        }
      ]
    },
    {
      id: 'industries',
      name: 'industries',
      type: 'table',
      category: 'Reference Data',
      displayName: 'Industries',
      description: 'Industry classification within sectors',
      stats: { rowCount: 150, lastUpdated: new Date() },
      attributes: [
        {
          id: 'ind_id',
          name: 'industry_id',
          dataType: 'uuid',
          semanticType: 'id' as any,
          constraints: { primaryKey: true }
        },
        {
          id: 'ind_name',
          name: 'industry_name',
          dataType: 'varchar(100)',
          semanticType: 'text' as any,
          constraints: { nullable: false }
        },
        {
          id: 'ind_sector_id',
          name: 'sector_id',
          dataType: 'uuid',
          semanticType: 'id' as any,
          constraints: { 
            foreignKey: { entity: 'sectors', attribute: 'sector_id' },
            nullable: false
          }
        }
      ]
    },
    {
      id: 'economic_indicators',
      name: 'economic_indicators',
      type: 'table',
      category: 'Market Data',
      displayName: 'Economic Indicators',
      description: 'Economic indicators and macro data',
      stats: { rowCount: 500000, lastUpdated: new Date() },
      attributes: [
        {
          id: 'ei_id',
          name: 'indicator_id',
          dataType: 'uuid',
          semanticType: 'id' as any,
          constraints: { primaryKey: true }
        },
        {
          id: 'ei_name',
          name: 'indicator_name',
          dataType: 'varchar(100)',
          semanticType: 'text' as any,
          constraints: { nullable: false }
        },
        {
          id: 'ei_value',
          name: 'value',
          dataType: 'decimal(20,4)',
          semanticType: 'quantity' as any,
          constraints: { nullable: false }
        },
        {
          id: 'ei_date',
          name: 'release_date',
          dataType: 'date',
          semanticType: 'date' as any,
          constraints: { nullable: false }
        }
      ]
    },
    {
      id: 'exchange_rates',
      name: 'exchange_rates',
      type: 'table',
      category: 'Market Data',
      displayName: 'Exchange Rates',
      description: 'Currency exchange rates',
      stats: { rowCount: 1000000, lastUpdated: new Date() },
      attributes: [
        {
          id: 'fx_id',
          name: 'rate_id',
          dataType: 'uuid',
          semanticType: 'id' as any,
          constraints: { primaryKey: true }
        },
        {
          id: 'fx_pair',
          name: 'currency_pair',
          dataType: 'varchar(10)',
          semanticType: 'text' as any,
          constraints: { nullable: false }
        },
        {
          id: 'fx_rate',
          name: 'exchange_rate',
          dataType: 'decimal(20,6)',
          semanticType: 'money' as any,
          constraints: { nullable: false }
        },
        {
          id: 'fx_date',
          name: 'rate_date',
          dataType: 'date',
          semanticType: 'date' as any,
          constraints: { nullable: false }
        }
      ]
    }
  ],
  relationships: [
    {
      id: 'rel_1',
      source: 'daily_prices',
      target: 'securities',
      type: 'many-to-one',
      sourceAttribute: 'security_id',
      targetAttribute: 'security_id',
      label: 'has prices'
    },
    {
      id: 'rel_2',
      source: 'portfolio_holdings',
      target: 'portfolios',
      type: 'many-to-one',
      sourceAttribute: 'portfolio_id',
      targetAttribute: 'portfolio_id',
      label: 'belongs to'
    },
    {
      id: 'rel_3',
      source: 'portfolio_holdings',
      target: 'securities',
      type: 'many-to-one',
      sourceAttribute: 'security_id',
      targetAttribute: 'security_id',
      label: 'holds'
    },
    {
      id: 'rel_4',
      source: 'industries',
      target: 'sectors',
      type: 'many-to-one',
      sourceAttribute: 'sector_id',
      targetAttribute: 'sector_id',
      label: 'belongs to'
    }
  ],
  categories: {
    'Reference Data': ['securities', 'exchanges', 'sectors', 'industries'],
    'Market Data': ['daily_prices', 'economic_indicators', 'exchange_rates'],
    'Analytics': ['portfolios', 'portfolio_holdings']
  }
};

export default function SchemaPage() {
  const [schema, setSchema] = useState<UniversalSchema | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Simulate loading schema from API
    setTimeout(() => {
      setSchema(mockSchema);
      setLoading(false);
    }, 1000);
  }, []);

  const handleTableSelect = (tableId: string) => {
    console.log('Selected table:', tableId);
  };

  const handleColumnSelect = (tableId: string, columnId: string) => {
    console.log('Selected column:', columnId, 'in table:', tableId);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white shadow-sm border-b border-gray-200">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-16">
              <div className="flex items-center gap-3">
                <Database className="h-6 w-6 text-blue-600" />
                <h1 className="text-xl font-semibold text-gray-900">SENS</h1>
                <span className="text-sm text-gray-500">Natural Language SQL</span>
              </div>
              <nav className="flex items-center gap-4">
                <a 
                  href="/" 
                  className="text-sm font-medium text-gray-700 hover:text-blue-600 transition-colors"
                >
                  Query
                </a>
                <a 
                  href="/schema" 
                  className="text-sm font-medium text-blue-600 transition-colors"
                >
                  Schema
                </a>
              </nav>
            </div>
          </div>
        </header>
        <div className="max-w-7xl mx-auto p-6">
          <Card className="p-6">
            <Skeleton className="h-8 w-48 mb-4" />
            <Skeleton className="h-4 w-64 mb-6" />
            <Skeleton className="h-[600px] w-full" />
          </Card>
        </div>
      </div>
    );
  }

  if (!schema) {
    return (
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white shadow-sm border-b border-gray-200">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-16">
              <div className="flex items-center gap-3">
                <Database className="h-6 w-6 text-blue-600" />
                <h1 className="text-xl font-semibold text-gray-900">SENS</h1>
                <span className="text-sm text-gray-500">Natural Language SQL</span>
              </div>
              <nav className="flex items-center gap-4">
                <a 
                  href="/" 
                  className="text-sm font-medium text-gray-700 hover:text-blue-600 transition-colors"
                >
                  Query
                </a>
                <a 
                  href="/schema" 
                  className="text-sm font-medium text-blue-600 transition-colors"
                >
                  Schema
                </a>
              </nav>
            </div>
          </div>
        </header>
        <div className="max-w-7xl mx-auto p-6">
          <Card className="p-6">
            <p className="text-center text-muted-foreground">No schema available</p>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <Database className="h-6 w-6 text-blue-600" />
              <h1 className="text-xl font-semibold text-gray-900">SENS</h1>
              <span className="text-sm text-gray-500">Natural Language SQL</span>
            </div>
            <nav className="flex items-center gap-4">
              <a 
                href="/" 
                className="text-sm font-medium text-gray-700 hover:text-blue-600 transition-colors"
              >
                Query
              </a>
              <a 
                href="/schema" 
                className="text-sm font-medium text-blue-600 transition-colors"
              >
                Schema
              </a>
            </nav>
          </div>
        </div>
      </header>
      
      <div className="max-w-7xl mx-auto p-6">
        <div className="mb-6">
          <h1 className="text-3xl font-bold mb-2">Schema Visualization</h1>
          <p className="text-muted-foreground">
            Interactive visualization of your database schema with multiple view modes
          </p>
        </div>
        
        <SchemaVisualizer
          schema={schema}
          onTableSelect={handleTableSelect}
          onColumnSelect={handleColumnSelect}
          defaultMode="graph"
        />
      </div>
    </div>
  );
}