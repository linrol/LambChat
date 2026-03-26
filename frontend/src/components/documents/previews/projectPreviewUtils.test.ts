import test from "node:test";
import assert from "node:assert/strict";
import {
  resolveEntryFile,
  resolveSandpackTemplate,
} from "./projectPreviewUtils.ts";

test("uses react template for Vite-style React projects with index.html and main.jsx", () => {
  const template = resolveSandpackTemplate("vanilla", {
    "/index.html": '<script type="module" src="/src/main.jsx"></script>',
    "/src/main.jsx": "import React from 'react';",
  });

  assert.equal(template, "react");
});

test("uses react template for Vite-style React projects with index.html and main.tsx", () => {
  const template = resolveSandpackTemplate("vanilla", {
    "/index.html": '<script type="module" src="/src/main.tsx"></script>',
    "/src/main.tsx": "import React from 'react';",
  });

  assert.equal(template, "react");
});

test("keeps static template for plain static sites", () => {
  const template = resolveSandpackTemplate("static", {
    "/index.html": "<h1>Hello</h1>",
    "/styles.css": "body { color: red; }",
  });

  assert.equal(template, "static");
});

test("uses src main tsx as default entry when no explicit entry is provided", () => {
  const entry = resolveEntryFile({
    "/src/main.tsx": "import React from 'react';",
    "/src/App.tsx": "export default function App() { return null; }",
  });

  assert.equal(entry, "/src/main.tsx");
});

test("normalizes explicit entry paths", () => {
  const entry = resolveEntryFile(
    {
      "/src/main.jsx": "import React from 'react';",
    },
    "src/main.jsx",
  );

  assert.equal(entry, "/src/main.jsx");
});

test("uses svelte template when App.svelte is present", () => {
  const template = resolveSandpackTemplate("vanilla", {
    "/src/App.svelte": "<script>let count = 0;</script>",
    "/src/main.js": "import App from './App.svelte';",
  });

  assert.equal(template, "svelte");
});

test("uses solid template when solid entry files are present", () => {
  const template = resolveSandpackTemplate("vanilla", {
    "/src/index.tsx": "import { render } from 'solid-js/web';",
    "/src/App.tsx": "export default function App() { return <div />; }",
  });

  assert.equal(template, "solid");
});

test("uses nextjs template when next pages router files are present", () => {
  const template = resolveSandpackTemplate("vanilla", {
    "/pages/index.tsx": "export default function Page() { return <main />; }",
    "/pages/_app.tsx":
      "export default function App({ Component, pageProps }) { return <Component {...pageProps} />; }",
  });

  assert.equal(template, "nextjs");
});

test("uses angular template when angular config and main entry are present", () => {
  const template = resolveSandpackTemplate("vanilla", {
    "/angular.json": "{}",
    "/src/main.ts": "bootstrapApplication(AppComponent);",
  });

  assert.equal(template, "angular");
});

test("uses svelte main js as default entry when available", () => {
  const entry = resolveEntryFile({
    "/src/main.js": "import App from './App.svelte';",
    "/src/App.svelte": "<script></script>",
  });

  assert.equal(entry, "/src/main.js");
});

test("uses nextjs pages index as default entry when available", () => {
  const entry = resolveEntryFile({
    "/pages/index.tsx": "export default function Page() { return null; }",
    "/pages/_app.tsx":
      "export default function App({ Component, pageProps }) { return <Component {...pageProps} />; }",
  });

  assert.equal(entry, "/pages/index.tsx");
});
