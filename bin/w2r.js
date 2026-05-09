#!/usr/bin/env node

const { spawnSync } = require("node:child_process");
const path = require("node:path");

const cliPath = path.resolve(__dirname, "..", "src", "w2r", "cli.py");
const args = [cliPath, ...process.argv.slice(2)];

function runWith(pythonBin) {
  return spawnSync(pythonBin, args, {
    stdio: "inherit",
    env: process.env
  });
}

let result = runWith("python3");
if (result.error) {
  result = runWith("python");
}

if (result.error) {
  console.error("Error: Python 3.10+ is required to run w2r.");
  process.exit(2);
}

process.exit(result.status ?? 1);
