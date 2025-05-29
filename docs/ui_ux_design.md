# SENS UI/UX Design Document

## Core Design Principles

### 1. **Conversational First**
- Chat-like interface that feels natural
- Show both user questions and system responses
- Maintain conversation context

### 2. **Trust Through Transparency**
- Always show the generated SQL
- Explain what the query will do before running
- Show confidence levels when uncertain

### 3. **Progressive Complexity**
- Simple interface for basic users
- Advanced features available but not overwhelming
- Tooltips and help readily available

## UI Components

### Primary Interface Elements

#### 1. **Smart Query Input**
```javascript
// Features:
- Autocomplete for common patterns
- Natural language suggestions as you type
- Voice input option
- Template shortcuts (e.g., "Show me all..." → template)

// Example suggestions:
"Show me..." → ["all users", "revenue by month", "top products"]
"How many..." → ["users", "orders today", "active customers"]
```

#### 2. **Multi-Modal Results Display**
```javascript
// Adaptive display based on result type:
- Single value: Big number card
- List: Clean table with sorting/filtering
- Time series: Automatic chart
- Geographic: Map visualization

// Always include:
- Export options (CSV, Excel, JSON)
- Share link
- Save as favorite
```

#### 3. **Query Builder Assistant**
```javascript
// For complex queries:
- Visual query builder as alternative
- Drag & drop table relationships
- Natural language describes what you're building
- Real-time SQL preview
```

## User Flow Examples

### New User Onboarding
```
1. Welcome screen with 3 example queries
2. Click example → See it execute → Understand the pattern
3. Guided first query with tooltips
4. Unlock features progressively
```

### Power User Workflow
```
1. Slash commands for quick actions (/tables, /schema, /history)
2. Keyboard shortcuts (Ctrl+Enter to run, Ctrl+K for command palette)
3. SQL edit mode for manual tweaking
4. Query variables and parameters
```

## Visual Design System

### Color Palette
```css
/* Primary */
--primary-blue: #3B82F6;      /* CTAs, links */
--primary-green: #10B981;     /* Success, run query */
--primary-amber: #F59E0B;     /* Warnings */
--primary-red: #EF4444;       /* Errors */

/* Neutral */
--gray-50: #F9FAFB;          /* Background */
--gray-100: #F3F4F6;         /* Cards */
--gray-600: #4B5563;         /* Text */
--gray-900: #111827;         /* Headers */

/* Syntax Highlighting */
--sql-keyword: #7C3AED;      /* SELECT, FROM */
--sql-string: #059669;       /* 'values' */
--sql-number: #DC2626;       /* 123 */
--sql-function: #2563EB;     /* COUNT(), SUM() */
```

### Typography
```css
/* Headers */
--font-display: "Inter", system-ui;
--font-mono: "JetBrains Mono", monospace;

/* Sizes */
--text-xs: 0.75rem;
--text-sm: 0.875rem;
--text-base: 1rem;
--text-lg: 1.125rem;
--text-xl: 1.25rem;
```

## Implementation Recommendations

### Frontend Stack
```javascript
// Option 1: React + Tailwind (Modern, lots of components)
- React 18+ with TypeScript
- Tailwind CSS for styling
- Recharts for visualizations
- React Query for data fetching

// Option 2: Vue 3 + Naive UI (Simpler, great DX)
- Vue 3 with Composition API
- Naive UI component library
- ECharts for visualizations
- Pinia for state management

// Option 3: Vanilla + Alpine.js (Lightweight)
- Alpine.js for reactivity
- Tailwind CSS
- Chart.js for visualizations
- Native fetch API
```

### Key Features to Implement First

1. **Query Interface**
   ```javascript
   // Minimum viable query interface
   - Text input with submit button
   - Loading state
   - Results table
   - Error display
   ```

2. **SQL Display**
   ```javascript
   // Collapsible SQL panel with:
   - Syntax highlighting
   - Copy button
   - Format button
   - Explain plan option
   ```

3. **Results Handler**
   ```javascript
   // Smart result display:
   if (resultCount === 1) showBigNumber();
   else if (hasTimeColumn) showTimeChart();
   else if (hasGeoData) showMap();
   else showTable();
   ```

4. **History Sidebar**
   ```javascript
   // Query history with:
   - Search/filter
   - Favorite marking
   - Re-run capability
   - Delete option
   ```

## Responsive Design

### Mobile First
```css
/* Mobile (default) */
.query-interface {
  flex-direction: column;
  padding: 1rem;
}

/* Tablet (768px+) */
@media (min-width: 768px) {
  .query-interface {
    flex-direction: row;
    padding: 2rem;
  }
}

/* Desktop (1024px+) */
@media (min-width: 1024px) {
  /* Show sidebars */
  .history-panel { display: block; }
  .schema-panel { display: block; }
}
```

## Accessibility

### WCAG 2.1 AA Compliance
- Keyboard navigation for all features
- ARIA labels for screen readers
- High contrast mode support
- Focus indicators
- Error messages linked to inputs

### Performance
- Lazy load visualizations
- Virtual scrolling for large tables
- Debounced autocomplete
- Optimistic UI updates
- Progressive enhancement

## Next Steps

1. Create wireframes for main screens
2. Build component library
3. Implement core query interface
4. Add results display
5. Layer in advanced features
