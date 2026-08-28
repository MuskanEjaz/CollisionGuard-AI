/**
 * End-to-End Integration Test
 * Simulates the complete data flow: Backend API → Visualization Response → Frontend Rendering
 */

const http = require('http');

console.log('\n=== CollisionGuard AI - End-to-End Integration Test ===\n');

function makeRequest(method, path, callback) {
  const options = {
    hostname: '127.0.0.1',
    port: 8000,
    path: path,
    method: method,
    headers: {
      'Content-Type': 'application/json'
    }
  };

  const req = http.request(options, (res) => {
    let data = '';
    res.on('data', (chunk) => { data += chunk; });
    res.on('end', () => {
      try {
        const json = JSON.parse(data);
        callback(null, res.statusCode, json);
      } catch (e) {
        callback(e, res.statusCode, null);
      }
    });
  });

  req.on('error', callback);
  req.end();
}

const tests = [];
let completedTests = 0;

function runTest(name, fn) {
  console.log(`\n[TEST] ${name}...`);
  fn((err, status, data) => {
    completedTests++;
    if (err) {
      console.error(`  ✗ FAILED: ${err.message}`);
      tests.push({ name, status: 'FAILED', error: err.message });
    } else if (status !== 200) {
      console.error(`  ✗ FAILED: HTTP ${status}`);
      tests.push({ name, status: 'FAILED', error: `HTTP ${status}` });
    } else {
      console.log(`  ✓ PASSED`);
      tests.push({ name, status: 'PASSED' });
    }

    if (completedTests === 5) {
      printSummary();
    }
  });
}

function printSummary() {
  console.log('\n=== Test Results ===\n');
  
  const passed = tests.filter(t => t.status === 'PASSED').length;
  const failed = tests.filter(t => t.status === 'FAILED').length;
  
  tests.forEach(t => {
    const icon = t.status === 'PASSED' ? '✓' : '✗';
    console.log(`${icon} ${t.name}`);
    if (t.error) console.log(`  Error: ${t.error}`);
  });
  
  console.log(`\nSummary: ${passed}/${tests.length} passed\n`);
  
  if (passed === tests.length) {
    console.log('🎉 Integration test PASSED! Visualization is ready.\n');
  } else {
    console.log('❌ Some tests failed. Check errors above.\n');
    process.exit(1);
  }
}

// Test 1: Health check
runTest('Backend Health Check', (done) => {
  makeRequest('GET', '/health', (err, status, data) => {
    if (err) return done(err);
    if (status !== 200) return done(null, status);
    if (!data.status || data.status !== 'ok') {
      return done(new Error('Health status not ok'));
    }
    console.log(`    Status: ${data.status}, Version: ${data.version}`);
    done(null, status, data);
  });
});

// Test 2: Scenarios endpoint
runTest('Scenarios Endpoint', (done) => {
  makeRequest('GET', '/scenarios', (err, status, data) => {
    if (err) return done(err);
    if (status !== 200) return done(null, status);
    if (!data.scenarios || !Array.isArray(data.scenarios)) {
      return done(new Error('Invalid scenarios response'));
    }
    console.log(`    Found ${data.scenarios.length} scenarios`);
    data.scenarios.forEach(s => {
      console.log(`      - ${s.id}: ${s.name}`);
    });
    done(null, status, data);
  });
});

// Test 3: Analysis endpoint - CONJ-001
runTest('Analysis Endpoint (CONJ-001)', (done) => {
  makeRequest('POST', '/scenarios/CONJ-001/analyse', (err, status, data) => {
    if (err) return done(err);
    if (status !== 200) return done(null, status);
    if (!data.visualization) {
      return done(new Error('No visualization data in response'));
    }
    console.log(`    Visualization data received`);
    done(null, status, data);
  });
});

// Test 4: Visualization data structure
runTest('Visualization Data Contract', (done) => {
  makeRequest('POST', '/scenarios/CONJ-001/analyse', (err, status, data) => {
    if (err) return done(err);
    if (status !== 200) return done(null, status);
    
    const viz = data.visualization;
    const checks = [
      { field: 'coordinate_frame', value: viz.coordinate_frame, expected: 'TEME' },
      { field: 'position_units', value: viz.position_units, expected: 'km' },
      { field: 'samples', value: Array.isArray(viz.samples), expected: true },
      { field: 'samples.length', value: viz.samples ? viz.samples.length : 0, expected: 360 },
      { field: 'tca', value: !!viz.tca, expected: true },
      { field: 'tca.timestamp_utc', value: !!viz.tca?.timestamp_utc, expected: true },
      { field: 'tca.miss_distance_km', value: typeof viz.tca?.miss_distance_km, expected: 'number' },
      { field: 'tca.relative_velocity_km_s', value: typeof viz.tca?.relative_velocity_km_s, expected: 'number' }
    ];
    
    let allValid = true;
    checks.forEach(check => {
      const valid = check.value === check.expected;
      const status = valid ? '✓' : '✗';
      console.log(`    ${status} ${check.field}: ${check.value}`);
      if (!valid) allValid = false;
    });
    
    if (!allValid) {
      return done(new Error('Visualization contract validation failed'));
    }
    
    console.log(`    Relative velocity: ${viz.tca.relative_velocity_km_s} km/s`);
    console.log(`    Miss distance: ${viz.tca.miss_distance_km} km`);
    
    done(null, status, data);
  });
});

// Test 5: First sample structure
runTest('Sample Data Integrity (First Sample)', (done) => {
  makeRequest('POST', '/scenarios/CONJ-001/analyse', (err, status, data) => {
    if (err) return done(err);
    if (status !== 200) return done(null, status);
    
    const sample = data.visualization.samples[0];
    if (!sample) {
      return done(new Error('No samples in visualization'));
    }
    
    const checks = [
      { field: 'timestamp_utc', value: !!sample.timestamp_utc, expected: true },
      { field: 'protected_position_km', value: Array.isArray(sample.protected_position_km), expected: true },
      { field: 'protected_position_km.length', value: sample.protected_position_km?.length, expected: 3 },
      { field: 'threat_position_km', value: Array.isArray(sample.threat_position_km), expected: true },
      { field: 'threat_position_km.length', value: sample.threat_position_km?.length, expected: 3 }
    ];
    
    let allValid = true;
    checks.forEach(check => {
      const valid = check.value === check.expected;
      const status = valid ? '✓' : '✗';
      console.log(`    ${status} ${check.field}: ${check.value}`);
      if (!valid) allValid = false;
    });
    
    if (!allValid) {
      return done(new Error('Sample structure validation failed'));
    }
    
    console.log(`    Sample timestamp: ${sample.timestamp_utc}`);
    console.log(`    Protected pos: [${sample.protected_position_km.map(v => v.toFixed(2)).join(', ')}] km`);
    console.log(`    Threat pos: [${sample.threat_position_km.map(v => v.toFixed(2)).join(', ')}] km`);
    
    done(null, status, data);
  });
});
