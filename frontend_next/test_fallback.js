/**
 * Next.js Frontend and Static Fallback Integrity Test.
 * Validates public/forecast_static.json has exactly 12 rows with required keys.
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log('Running Next.js static fallback & integrity checks...');

const staticFile = path.join(__dirname, 'public', 'forecast_static.json');
if (!fs.existsSync(staticFile)) {
  console.error(`ERROR: Static fallback file not found at ${staticFile}`);
  process.exit(1);
}

const raw = fs.readFileSync(staticFile, 'utf-8');
let data;
try {
  data = JSON.parse(raw);
} catch (e) {
  console.error(`ERROR: forecast_static.json is not valid JSON: ${e.message}`);
  process.exit(1);
}

if (!Array.isArray(data)) {
  console.error('ERROR: forecast_static.json must contain a JSON array.');
  process.exit(1);
}

if (data.length !== 12) {
  console.error(`ERROR: Expected exactly 12 forecast points, found ${data.length}`);
  process.exit(1);
}

const requiredKeys = ['month', 'point', 'lower_80', 'upper_80', 'lower_95', 'upper_95'];

data.forEach((row, idx) => {
  for (const k of requiredKeys) {
    if (row[k] === undefined || row[k] === null) {
      console.error(`ERROR: Row ${idx} is missing key '${k}'`);
      process.exit(1);
    }
  }
  if (typeof row.point !== 'number' || isNaN(row.point)) {
    console.error(`ERROR: Row ${idx} has invalid point value: ${row.point}`);
    process.exit(1);
  }
});

console.log(`✓ forecast_static.json contains exactly 12 verified forecast rows with all required keys.`);

// Verify report.html presence
const reportFile = path.join(__dirname, 'public', 'report.html');
if (!fs.existsSync(reportFile)) {
  console.error(`ERROR: Full analysis report not found at ${reportFile}`);
  process.exit(1);
}
const reportStat = fs.statSync(reportFile);
const sizeMb = (reportStat.size / (1024 * 1024)).toFixed(2);
console.log(`✓ report.html exists (${reportStat.size} bytes / ${sizeMb} MB)`);

if (reportStat.size > 10 * 1024 * 1024) {
  console.error(`ERROR: report.html exceeds 10 MB limit (${sizeMb} MB)`);
  process.exit(1);
}

console.log('NEXT.JS STATIC FALLBACK TESTS PASSED!');
