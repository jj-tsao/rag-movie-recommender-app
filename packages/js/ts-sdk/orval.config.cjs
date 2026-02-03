const path = require('path');

// Orval v7 expects either a single top-level project (input/output)
// or named projects. Using the single project shape here.
module.exports = {
  input: {
    target: path.resolve(__dirname, '../../schemas/openapi.yaml'),
  },
  output: {
    mode: 'single',
    target: path.resolve(__dirname, './src/index.ts'),
    client: 'fetch',
    clean: true,
  },
};

// Ensure compatibility when loaded via ESM dynamic import
module.exports.default = module.exports;

