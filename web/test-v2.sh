#!/bin/bash

echo "Starting V2 SSE test..."

# Start query
RESPONSE=$(curl -s -X POST http://localhost:3000/api/nl2sql/agent/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How many users do we have?", "max_iterations": 10}')

QUERY_ID=$(echo $RESPONSE | jq -r '.query_id')
echo "Query ID: $QUERY_ID"

# Stream events and count them
echo -e "\nStreaming events..."
curl -N http://localhost:3000/api/nl2sql/agent/stream/$QUERY_ID 2>/dev/null | while IFS= read -r line; do
  if [[ $line == event:* ]]; then
    EVENT_TYPE=$(echo $line | cut -d' ' -f2)
    echo -n "[$EVENT_TYPE] "
  elif [[ $line == data:* ]]; then
    DATA=$(echo $line | cut -d' ' -f2-)
    if [[ -n "$DATA" ]]; then
      CONTENT=$(echo $DATA | jq -r '.content // ""' 2>/dev/null)
      ITERATION=$(echo $DATA | jq -r '.iteration // ""' 2>/dev/null)
      echo "iter=$ITERATION: ${CONTENT:0:60}..."
    fi
  fi
done
