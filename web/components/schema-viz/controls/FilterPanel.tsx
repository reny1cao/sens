'use client';

import { Filter, Settings2, Eye, FileText, GitBranch, BarChart3 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import { 
  UniversalSchema, 
  SchemaVisualizationConfig 
} from '@/types/schema';

interface FilterPanelProps {
  schema: UniversalSchema;
  selectedCategories: string[];
  onCategoryChange: (categories: string[]) => void;
  config: SchemaVisualizationConfig;
  onConfigChange: (config: SchemaVisualizationConfig) => void;
}

export function FilterPanel({
  schema,
  selectedCategories,
  onCategoryChange,
  config,
  onConfigChange
}: FilterPanelProps) {
  // Extract unique categories from entities
  const categories = Array.from(
    new Set(schema.entities.map(e => e.category).filter(Boolean))
  ) as string[];

  const categoryCounts: Record<string, number> = {};
  schema.entities.forEach(entity => {
    if (entity.category) {
      categoryCounts[entity.category] = (categoryCounts[entity.category] || 0) + 1;
    }
  });

  const toggleCategory = (category: string) => {
    if (selectedCategories.includes(category)) {
      onCategoryChange(selectedCategories.filter(c => c !== category));
    } else {
      onCategoryChange([...selectedCategories, category]);
    }
  };

  const updateConfig = (key: keyof SchemaVisualizationConfig, value: any) => {
    onConfigChange({
      ...config,
      [key]: value
    });
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2">
          <Filter className="h-4 w-4" />
          <span className="hidden sm:inline">Filter</span>
          {selectedCategories.length > 0 && (
            <Badge variant="secondary" className="ml-1">
              {selectedCategories.length}
            </Badge>
          )}
        </Button>
      </PopoverTrigger>
      
      <PopoverContent className="w-80" align="end">
        <Tabs defaultValue="categories" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="categories">Categories</TabsTrigger>
            <TabsTrigger value="display">Display</TabsTrigger>
          </TabsList>
          
          <TabsContent value="categories" className="space-y-4">
            <div>
              <h4 className="font-medium text-sm mb-3">Filter by Category</h4>
              
              {categories.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No categories defined
                </p>
              ) : (
                <div className="space-y-2">
                  <div className="flex items-center justify-between mb-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onCategoryChange([])}
                      disabled={selectedCategories.length === 0}
                    >
                      Clear all
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onCategoryChange(categories)}
                      disabled={selectedCategories.length === categories.length}
                    >
                      Select all
                    </Button>
                  </div>
                  
                  {categories.map(category => (
                    <div
                      key={category}
                      className="flex items-center space-x-2 py-1"
                    >
                      <Checkbox
                        id={category}
                        checked={selectedCategories.includes(category)}
                        onCheckedChange={() => toggleCategory(category)}
                      />
                      <Label
                        htmlFor={category}
                        className="flex-1 cursor-pointer text-sm font-normal"
                      >
                        {category}
                      </Label>
                      <Badge variant="secondary" className="text-xs">
                        {categoryCounts[category]}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </TabsContent>
          
          <TabsContent value="display" className="space-y-4">
            <div>
              <h4 className="font-medium text-sm mb-3">Display Options</h4>
              
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <BarChart3 className="h-4 w-4 text-muted-foreground" />
                    <Label htmlFor="show-stats" className="text-sm cursor-pointer">
                      Show Statistics
                    </Label>
                  </div>
                  <Switch
                    id="show-stats"
                    checked={config.showStats}
                    onCheckedChange={(checked) => updateConfig('showStats', checked)}
                  />
                </div>
                
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-muted-foreground" />
                    <Label htmlFor="show-descriptions" className="text-sm cursor-pointer">
                      Show Descriptions
                    </Label>
                  </div>
                  <Switch
                    id="show-descriptions"
                    checked={config.showDescriptions}
                    onCheckedChange={(checked) => updateConfig('showDescriptions', checked)}
                  />
                </div>
                
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Settings2 className="h-4 w-4 text-muted-foreground" />
                    <Label htmlFor="group-by-category" className="text-sm cursor-pointer">
                      Group by Category
                    </Label>
                  </div>
                  <Switch
                    id="group-by-category"
                    checked={config.groupByCategory}
                    onCheckedChange={(checked) => updateConfig('groupByCategory', checked)}
                  />
                </div>
                
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <GitBranch className="h-4 w-4 text-muted-foreground" />
                    <Label htmlFor="highlight-relationships" className="text-sm cursor-pointer">
                      Animate Relationships
                    </Label>
                  </div>
                  <Switch
                    id="highlight-relationships"
                    checked={config.highlightRelationships}
                    onCheckedChange={(checked) => updateConfig('highlightRelationships', checked)}
                  />
                </div>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </PopoverContent>
    </Popover>
  );
}