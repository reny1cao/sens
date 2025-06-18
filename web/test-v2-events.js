// Test script to monitor V2 events
import EventSource from 'eventsource';

async function testV2Events() {
  console.log('Starting V2 event test...');

  // Start a query
  const response = await fetch('http://localhost:3000/api/nl2sql/agent/query', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      question: 'How many users do we have?',
      max_iterations: 10
    }),
  });

  const data = await response.json();
  console.log('Query started:', data);

  // Connect to SSE
  const eventSource = new EventSource(`http://localhost:3000/api/nl2sql/agent/stream/${data.query_id}`);

  const events = [];
  const eventCounts = {};

  // Track all events
  ['connection', 'thought', 'action', 'observation', 'answer', 'complete', 'error'].forEach(eventType => {
    eventSource.addEventListener(eventType, (event) => {
      eventCounts[eventType] = (eventCounts[eventType] || 0) + 1;
      const eventData = {
        type: eventType,
        count: eventCounts[eventType],
        data: JSON.parse(event.data),
        timestamp: new Date().toISOString()
      };
      events.push(eventData);
      console.log(`\n[${eventType} #${eventCounts[eventType]}]`, JSON.stringify(eventData.data, null, 2));
    });
  });

  // Wait for completion
  await new Promise((resolve) => {
    eventSource.addEventListener('complete', () => {
      setTimeout(() => {
        eventSource.close();
        resolve();
      }, 1000);
    });

    eventSource.addEventListener('error', () => {
      eventSource.close();
      resolve();
    });

    // Timeout after 30 seconds
    setTimeout(() => {
      eventSource.close();
      resolve();
    }, 30000);
  });

  console.log('\n\nEvent Summary:');
  console.log('Total events:', events.length);
  console.log('Event counts:', eventCounts);

  // Check for duplicate content
  const thoughtEvents = events.filter(e => e.type === 'thought');
  console.log('\nThought events:', thoughtEvents.length);
  thoughtEvents.forEach((event, i) => {
    console.log(`  ${i + 1}. [iter ${event.data.iteration}] ${event.data.content.substring(0, 50)}...`);
  });
}

testV2Events().catch(console.error);
