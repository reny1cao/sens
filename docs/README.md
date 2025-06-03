# SENS Documentation

This directory contains design documents, architecture specifications, and implementation plans for the SENS project.

## Core Architecture Documents

### Current System
- [**Schema Context**](./schema_context.md) - Design for schema context management
- [**Schema Extraction Architecture**](./schema_extraction_architecture.md) - How schema is extracted from databases
- [**Data Source Architecture**](./data_source_architecture.md) - Multi-datasource support design
- [**CLI Commands**](./cli_commands.md) - Command-line interface specification

### Future Architecture (Agentic System)
- [**Agentic Query Architecture**](./agentic_query_architecture.md) 🆕 - Intelligent query understanding with value discovery and self-correction
- [**Agentic Implementation Plan**](./agentic_implementation_plan.md) 🆕 - Practical steps to implement the agentic system
- [**Agent Architecture Design**](./agent_architecture_design.md) - General agent architecture patterns
- [**Proactive Architecture**](./proactive_architecture.md) - Design for proactive insights and monitoring

## Feature Specifications

### UI/UX
- [**UI/UX Design**](./ui_ux_design.md) - User interface design principles
- [**UI Implementation Plan**](./ui_implementation_plan.md) - Frontend implementation strategy

### Multi-File Support
- [**Multi-File Product Architecture**](./multi_file_product_architecture.md) - Support for multiple data files

### Implementation
- [**Implementation Plan**](./implementation_plan.md) - General implementation strategy

## Key Concepts

### Value Mapping Problem
The agentic architecture addresses a fundamental limitation where user input doesn't directly map to database values:
- User says "tech companies" → Database has "Technology"
- User says "Apple" → Database has "AAPL"
- User says "large companies" → Need to infer market cap thresholds

### Agentic Solution
The new architecture introduces:
1. **ReAct-based reasoning** to explore and understand user intent
2. **Value discovery tools** to find actual database values
3. **Self-correcting execution** that diagnoses and fixes empty results
4. **Learning system** that improves mappings over time

## Reading Order

For understanding the current system:
1. Schema Context
2. Schema Extraction Architecture
3. Data Source Architecture

For understanding the future direction:
1. Agentic Query Architecture (comprehensive design)
2. Agentic Implementation Plan (how to build it)
3. Proactive Architecture (long-term vision)

## Status

- ✅ Current system is operational with basic NL2SQL
- 🚧 Agentic architecture is in design phase
- 📅 Implementation planned for Q1 2025