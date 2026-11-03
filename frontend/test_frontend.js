/**
 * Frontend integrity and component validation test.
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log('Running frontend integrity checks...');

const requiredFiles = [
  'package.json',
  'vite.config.js',
  'index.html',
  'src/main.jsx',
  'src/App.jsx',
  'src/index.css',
];

for (const file of requiredFiles) {
  const p = path.join(__dirname, file);
  if (!fs.existsSync(p)) {
    console.error(`MISSING required frontend file: ${file}`);
    process.exit(1);
  }
  const stat = fs.statSync(p);
  console.log(`✓ Found ${file} (${stat.size} bytes)`);
}

// Verify App.jsx contains required UI components
const appContent = fs.readFileSync(path.join(__dirname, 'src/App.jsx'), 'utf-8');
const expectedElements = [
  'Commodity Price Forecasting',
  'SARIMA(1,1,1)(1,0,0)[12]',
  'forecast_origin',
  'point_forecast',
  'lower_80',
  'upper_80',
  'lower_95',
  'upper_95',
  'Holdout Out-of-Sample MAE',
  'Zero-Interpolation Policy',
  'footer-disclaimer',
  'handleRunPipeline',
];

for (const el of expectedElements) {
  if (!appContent.includes(el)) {
    console.error(`App.jsx missing expected content or handler: '${el}'`);
    process.exit(1);
  }
}
console.log('✓ All expected UI components, endpoints, and handlers verified in App.jsx');

console.log('FRONTEND INTEGRITY TESTS PASSED!');
