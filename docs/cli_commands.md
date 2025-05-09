# Sens CLI Commands and Configuration

This document describes the available Sens CLI commands, their options, and configuration settings, with a focus on utilities like `debug`, `metrics`, and `status`, as well as detailed CLI-specific configurations.

For installation instructions and basic usage of core commands such as `nl2sql`, `extract-schema`, `build-index`, `validate`, and `execute`, please refer to the main [README.md](../README.md).

---

## Table of Contents
- [Overview](#overview)
- [Commands](#commands)
  - [sens debug](#sens-debug)
  - [sens metrics](#sens-metrics)
  - [sens status](#sens-status)
- [CLI Configuration](#cli-configuration)
  - [Environment Variables](#environment-variables)
  - [Settings File Locations](#settings-file-locations)
- [Examples](#examples)

---

## Overview

The Sens CLI provides tools for debugging, monitoring, and checking the status of your AI agent system. It is designed for transparency, reliability, and ease of use.

---

## Commands

### `sens debug`
- **Purpose:** Debug components and conversations.
- **Options:**
  - `--conversation-id <id>`: Show debug info for a specific conversation.
  - `--component <schema|indices|database>`: Show status for a specific component.
- **Example:**
  ```sh
  sens debug --conversation-id 1234
  sens debug --component schema
  sens debug
  ```

### `sens metrics`
- **Purpose:** Display metrics for conversations or the system.
- **Options:**
  - `--conversation-id <id>`: Show metrics for a specific conversation.
  - `--detailed`: Show detailed metrics table.
- **Example:**
  ```sh
  sens metrics --conversation-id 1234 --detailed
  sens metrics
  ```

### `sens status`
- **Purpose:** Check system status (schema, indices, database, settings).
- **Options:**
  - `--json`: Output status as JSON.
- **Example:**
  ```sh
  sens status
  sens status --json
  ```

---

## CLI Configuration

CLI-specific settings are managed via environment variables (with the `SENS_CLI_` prefix) or configuration files. These settings control debug, metrics, output, history, and cache behavior.

### Environment Variables

| Variable                      | Description                          | Default              |
| ----------------------------- | ------------------------------------ | -------------------- |
| SENS_CLI_DEBUG_MODE           | Enable debug mode                    | false                |
| SENS_CLI_TRACE_ENABLED        | Enable trace-level logging           | false                |
| SENS_CLI_METRICS_ENABLED      | Enable metrics collection            | false                |
| SENS_CLI_METRICS_HISTORY_SIZE | Number of historical metrics entries | 100                  |
| SENS_CLI_DEFAULT_FORMAT       | Output format (json, table, summary) | json                 |
| SENS_CLI_MAX_PREVIEW_ROWS     | Max preview rows to show             | 5                    |
| SENS_CLI_PRETTY_PRINT         | Enable pretty printing               | true                 |
| SENS_CLI_HISTORY_ENABLED      | Enable conversation history          | true                 |
| SENS_CLI_HISTORY_FILE         | Path to conversation history file    | ~/.sens/history.json |
| SENS_CLI_MAX_HISTORY_SIZE     | Max number of historical entries     | 1000                 |
| SENS_CLI_CACHE_ENABLED        | Enable caching of results            | true                 |
| SENS_CLI_CACHE_DIR            | Directory for cached data            | ~/.sens/cache        |
| SENS_CLI_CACHE_TTL            | Cache TTL in seconds                 | 3600                 |

### Settings File Locations
- History: `~/.sens/history.json`
- Cache: `~/.sens/cache/`

---

## Examples

**Debug a conversation:**
```sh
sens debug --conversation-id 42
```

**Show metrics for a conversation:**
```sh
sens metrics --conversation-id 42 --detailed
```

**Check full system status in JSON:**
```sh
sens status --json
```

**Set CLI to pretty-print output:**
```sh
export SENS_CLI_PRETTY_PRINT=true
```

---

For more details, see the source code in `src/sens/cli/` and configuration in `src/sens/cli/config.py`.
