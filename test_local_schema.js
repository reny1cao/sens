// Test script to check if schema is loading locally
const fetch = require('node-fetch');

async function testLocalSchema() {
  try {
    // Test the API directly
    console.log('Testing backend API...');
    const apiResponse = await fetch('http://localhost:8000/api/schema/visualize');
    const apiData = await apiResponse.json();
    console.log(`✓ Backend API: ${apiData.entities.length} tables found`);
    
    // Test the frontend page
    console.log('\nTesting frontend page...');
    const pageResponse = await fetch('http://localhost:3000/schema');
    const pageHtml = await pageResponse.text();
    
    if (pageHtml.includes('No schema available')) {
      console.log('✗ Frontend shows: No schema available');
    } else if (pageHtml.includes('Schema Visualization')) {
      console.log('✓ Frontend page loaded with schema visualization');
    }
    
    // Check if the frontend is using the correct API URL
    console.log('\nChecking frontend API configuration...');
    const envResponse = await fetch('http://localhost:3000/api/schema/visualize');
    console.log(`Frontend API proxy status: ${envResponse.status}`);
    
  } catch (error) {
    console.error('Error:', error.message);
  }
}

testLocalSchema();