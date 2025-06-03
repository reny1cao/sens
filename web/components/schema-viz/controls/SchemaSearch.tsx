'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { Search, Table, Hash, Calendar, Type, DollarSign, Percent, ToggleLeft, FileJson, Database, Key } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { 
  UniversalSchema, 
  SchemaEntity, 
  SchemaAttribute,
  SemanticType 
} from '@/types/schema';
import { cn } from '@/lib/utils';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';

interface SchemaSearchProps {
  schema: UniversalSchema;
  value: string;
  onChange: (value: string) => void;
  onSelect?: (item: SearchResult) => void;
  placeholder?: string;
  className?: string;
}

interface SearchResult {
  type: 'table' | 'column';
  entity: SchemaEntity;
  attribute?: SchemaAttribute;
  score: number;
}

function getSemanticIcon(type?: SemanticType) {
  switch (type) {
    case SemanticType.IDENTIFIER:
      return <Key className="w-3 h-3" />;
    case SemanticType.TEMPORAL:
      return <Calendar className="w-3 h-3" />;
    case SemanticType.MONETARY:
      return <DollarSign className="w-3 h-3" />;
    case SemanticType.QUANTITY:
      return <Hash className="w-3 h-3" />;
    case SemanticType.PERCENTAGE:
      return <Percent className="w-3 h-3" />;
    case SemanticType.TEXT:
      return <Type className="w-3 h-3" />;
    case SemanticType.BOOLEAN:
      return <ToggleLeft className="w-3 h-3" />;
    case SemanticType.JSON:
      return <FileJson className="w-3 h-3" />;
    default:
      return <Database className="w-3 h-3" />;
  }
}

export function SchemaSearch({
  schema,
  value,
  onChange,
  onSelect,
  placeholder = "Search tables and columns...",
  className
}: SchemaSearchProps) {
  const [open, setOpen] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  // Fuzzy search function
  const fuzzySearch = useCallback((query: string, text: string): number => {
    if (!query) return 0;
    
    const queryLower = query.toLowerCase();
    const textLower = text.toLowerCase();
    
    // Exact match
    if (textLower === queryLower) return 100;
    
    // Starts with
    if (textLower.startsWith(queryLower)) return 90;
    
    // Contains
    if (textLower.includes(queryLower)) return 70;
    
    // Fuzzy match - check if all query characters appear in order
    let queryIndex = 0;
    let score = 50;
    
    for (let i = 0; i < textLower.length && queryIndex < queryLower.length; i++) {
      if (textLower[i] === queryLower[queryIndex]) {
        queryIndex++;
        score += 5;
      }
    }
    
    return queryIndex === queryLower.length ? score : 0;
  }, []);

  // Search through schema
  const performSearch = useCallback((query: string) => {
    if (!query || query.length < 2) {
      setSearchResults([]);
      return;
    }

    const results: SearchResult[] = [];

    schema.entities.forEach(entity => {
      // Search table names
      const tableNameScore = Math.max(
        fuzzySearch(query, entity.name),
        entity.displayName ? fuzzySearch(query, entity.displayName) : 0
      );
      
      if (tableNameScore > 0) {
        results.push({
          type: 'table',
          entity,
          score: tableNameScore + 10 // Bonus for table matches
        });
      }

      // Search column names
      entity.attributes.forEach(attr => {
        const columnScore = fuzzySearch(query, attr.name);
        
        if (columnScore > 0) {
          results.push({
            type: 'column',
            entity,
            attribute: attr,
            score: columnScore
          });
        }
      });
    });

    // Sort by score and limit results
    results.sort((a, b) => b.score - a.score);
    setSearchResults(results.slice(0, 20));
  }, [schema, fuzzySearch]);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      performSearch(value);
    }, 150);

    return () => clearTimeout(timer);
  }, [value, performSearch]);

  const handleSelect = (result: SearchResult) => {
    onSelect?.(result);
    setOpen(false);
    
    // Optionally update the search value
    if (result.type === 'table') {
      onChange(result.entity.displayName || result.entity.name);
    } else if (result.attribute) {
      onChange(`${result.entity.displayName || result.entity.name}.${result.attribute.name}`);
    }
  };

  // Check if mobile
  const [isMobile, setIsMobile] = useState(false);
  
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Mobile search without popover
  if (isMobile) {
    return (
      <div className={cn("relative", className)}>
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none z-10" />
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 pl-9 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
          type="search"
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="off"
          inputMode="search"
        />
      </div>
    );
  }

  // Desktop search with popover
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <div className={cn("relative", className)}>
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
          <Input
            ref={inputRef}
            value={value}
            onChange={(e) => {
              onChange(e.target.value);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            placeholder={placeholder}
            className="pl-9 pr-3"
            type="search"
            autoComplete="off"
          />
        </div>
      </PopoverTrigger>
      
      <PopoverContent className="w-[400px] p-0" align="start">
        <Command>
          <CommandList>
            {searchResults.length === 0 && value.length >= 2 && (
              <CommandEmpty>No results found.</CommandEmpty>
            )}
            
            {searchResults.length > 0 && (
              <>
                {/* Tables */}
                {searchResults.filter(r => r.type === 'table').length > 0 && (
                  <CommandGroup heading="Tables">
                    {searchResults
                      .filter(r => r.type === 'table')
                      .map((result, index) => (
                        <CommandItem
                          key={`table-${result.entity.id}-${index}`}
                          onSelect={() => handleSelect(result)}
                          className="cursor-pointer"
                        >
                          <div className="flex items-center gap-2 w-full">
                            <Table className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                            <span className="font-medium">
                              {result.entity.displayName || result.entity.name}
                            </span>
                            {result.entity.category && (
                              <Badge variant="secondary" className="ml-auto text-xs">
                                {result.entity.category}
                              </Badge>
                            )}
                          </div>
                        </CommandItem>
                      ))}
                  </CommandGroup>
                )}
                
                {/* Columns */}
                {searchResults.filter(r => r.type === 'column').length > 0 && (
                  <CommandGroup heading="Columns">
                    {searchResults
                      .filter(r => r.type === 'column')
                      .map((result, index) => (
                        <CommandItem
                          key={`column-${result.entity.id}-${result.attribute?.id}-${index}`}
                          onSelect={() => handleSelect(result)}
                          className="cursor-pointer"
                        >
                          <div className="flex items-center gap-2 w-full">
                            {getSemanticIcon(result.attribute?.semanticType)}
                            <div className="flex-1">
                              <span className="font-mono text-sm">
                                {result.attribute?.name}
                              </span>
                              <span className="text-xs text-muted-foreground ml-2">
                                in {result.entity.displayName || result.entity.name}
                              </span>
                            </div>
                            <span className="text-xs text-muted-foreground">
                              {result.attribute?.dataType}
                            </span>
                          </div>
                        </CommandItem>
                      ))}
                  </CommandGroup>
                )}
              </>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}