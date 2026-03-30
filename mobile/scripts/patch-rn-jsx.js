#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

const rnDir = path.join(__dirname, "..", "node_modules", "react-native");

for (const name of ["jsx-dev-runtime.js", "jsx-runtime.js"]) {
  const target = path.join(rnDir, name);
  if (!fs.existsSync(target)) {
    const mod = name.replace(".js", "").replace("react-native/", "");
    fs.writeFileSync(
      target,
      `'use strict';\nmodule.exports = require('react/${mod}');\n`
    );
    console.log(`Created ${name} shim`);
  }
}
