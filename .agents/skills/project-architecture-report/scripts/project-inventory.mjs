#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";

const ignoredDirs = new Set([
  ".git",
  ".hg",
  ".svn",
  ".scratch",
  "node_modules",
  ".next",
  ".nuxt",
  "dist",
  "build",
  "coverage",
  ".turbo",
  ".cache",
  ".pytest_cache",
  "__pycache__",
  ".venv",
  "venv",
]);

const symbolExts = new Set([
  ".cs",
  ".go",
  ".java",
  ".js",
  ".jsx",
  ".kt",
  ".mjs",
  ".php",
  ".py",
  ".rb",
  ".rs",
  ".svelte",
  ".ts",
  ".tsx",
  ".vue",
]);

function parseArgs(argv) {
  const options = {
    root: process.cwd(),
    out: "",
    maxFiles: 50000,
    maxReadBytes: 512 * 1024,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--root") options.root = argv[++i];
    else if (arg === "--out") options.out = argv[++i];
    else if (arg === "--max-files") options.maxFiles = Number(argv[++i]);
    else if (arg === "--help" || arg === "-h") {
      console.log("Usage: node project-inventory.mjs --root /path [--out file]");
      process.exit(0);
    } else {
      throw new Error(`Unknown option: ${arg}`);
    }
  }

  options.root = path.resolve(options.root);
  return options;
}

async function exists(filePath) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function walk(root, options) {
  const files = [];
  const dirs = [];

  async function visit(dir) {
    if (files.length >= options.maxFiles) return;
    const entries = await fs.readdir(dir, { withFileTypes: true });

    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      const relPath = path.relative(root, fullPath).replaceAll(path.sep, "/");

      if (entry.isDirectory()) {
        if (ignoredDirs.has(entry.name)) continue;
        dirs.push(relPath);
        await visit(fullPath);
        continue;
      }

      if (!entry.isFile()) continue;
      const stat = await fs.stat(fullPath);
      files.push({
        path: relPath,
        name: entry.name,
        ext: path.extname(entry.name).toLowerCase() || "[none]",
        size: stat.size,
      });
    }
  }

  await visit(root);
  return { files, dirs };
}

function groupBy(items, keyFn) {
  const groups = new Map();
  for (const item of items) {
    const key = keyFn(item);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  }
  return groups;
}

function extensionSummary(files) {
  return [...groupBy(files, (file) => file.ext).entries()]
    .map(([ext, group]) => ({
      ext,
      count: group.length,
      bytes: group.reduce((sum, file) => sum + file.size, 0),
    }))
    .sort((a, b) => b.count - a.count || a.ext.localeCompare(b.ext));
}

function topDirs(files) {
  return [...groupBy(files, (file) => (file.path.includes("/") ? file.path.split("/")[0] : ".")).entries()]
    .map(([dir, group]) => ({ dir, files: group.length }))
    .sort((a, b) => b.files - a.files || a.dir.localeCompare(b.dir));
}

function extractSymbols(content, ext) {
  const patterns = [];

  if ([".js", ".jsx", ".mjs", ".ts", ".tsx", ".svelte", ".vue"].includes(ext)) {
    patterns.push(
      { kind: "function", regex: /\b(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)/g },
      { kind: "class", regex: /\b(?:export\s+)?class\s+([A-Za-z_$][\w$]*)/g },
      { kind: "interface", regex: /\b(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)/g },
      { kind: "type", regex: /\b(?:export\s+)?type\s+([A-Za-z_$][\w$]*)\s*=/g },
      { kind: "const", regex: /\b(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=/g },
    );
  }

  if (ext === ".py") {
    patterns.push(
      { kind: "function", regex: /^\s*def\s+([A-Za-z_]\w*)/gm },
      { kind: "class", regex: /^\s*class\s+([A-Za-z_]\w*)/gm },
    );
  }

  if ([".cs", ".java", ".kt"].includes(ext)) {
    patterns.push(
      { kind: "class", regex: /\bclass\s+([A-Za-z_]\w*)/g },
      { kind: "interface", regex: /\binterface\s+([A-Za-z_]\w*)/g },
      { kind: "enum", regex: /\benum\s+([A-Za-z_]\w*)/g },
      { kind: "record", regex: /\brecord\s+([A-Za-z_]\w*)/g },
    );
  }

  if (ext === ".go") {
    patterns.push(
      { kind: "function", regex: /\bfunc\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)/g },
      { kind: "type", regex: /\btype\s+([A-Za-z_]\w*)\s+(?:struct|interface)/g },
    );
  }

  if (ext === ".rs") {
    patterns.push(
      { kind: "function", regex: /\bfn\s+([A-Za-z_]\w*)/g },
      { kind: "struct", regex: /\bstruct\s+([A-Za-z_]\w*)/g },
      { kind: "enum", regex: /\benum\s+([A-Za-z_]\w*)/g },
      { kind: "trait", regex: /\btrait\s+([A-Za-z_]\w*)/g },
    );
  }

  const symbols = [];
  for (const pattern of patterns) {
    for (const match of content.matchAll(pattern.regex)) {
      symbols.push({ kind: pattern.kind, name: match[1] });
    }
  }
  return symbols;
}

async function collectSymbols(root, files, options) {
  const result = [];
  for (const file of files) {
    if (!symbolExts.has(file.ext) || file.size > options.maxReadBytes) continue;
    const content = await fs.readFile(path.join(root, file.path), "utf8").catch(() => "");
    const symbols = extractSymbols(content, file.ext);
    if (symbols.length > 0) result.push({ path: file.path, symbols });
  }
  return result;
}

async function readJson(filePath) {
  return JSON.parse(await fs.readFile(filePath, "utf8"));
}

async function collectPackageJson(root, files) {
  const packageFiles = files.filter((file) => file.name === "package.json");
  const packages = [];

  for (const file of packageFiles) {
    const fullPath = path.join(root, file.path);
    const json = await readJson(fullPath).catch(() => null);
    if (!json) continue;
    packages.push({
      path: file.path,
      name: json.name ?? null,
      private: json.private ?? false,
      scripts: json.scripts ?? {},
      dependencies: Object.keys(json.dependencies ?? {}).sort(),
      devDependencies: Object.keys(json.devDependencies ?? {}).sort(),
      peerDependencies: Object.keys(json.peerDependencies ?? {}).sort(),
      exports: json.exports ?? null,
      main: json.main ?? null,
      type: json.type ?? null,
    });
  }

  return packages;
}

function likelyEntrypoints(files) {
  const entryPattern = /(^|\/)(app|main|index|server|route|routes|api|cli|worker|middleware|handler)\.[A-Za-z0-9]+$/i;
  return files
    .filter((file) => entryPattern.test(file.path))
    .map((file) => file.path)
    .sort()
    .slice(0, 200);
}

async function collectManifests(root, files) {
  const names = new Set([
    "AGENTS.md",
    "CLAUDE.md",
    "CONTEXT.md",
    "Dockerfile",
    "README.md",
    "compose.yaml",
    "docker-compose.yml",
    "package.json",
    "pnpm-workspace.yaml",
    "pyproject.toml",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
    "Gemfile",
    ".env.example",
  ]);

  const manifestPaths = files
    .filter((file) => names.has(file.name) || file.path.startsWith(".github/workflows/") || file.path.startsWith("docs/adr/"))
    .map((file) => file.path)
    .sort();

  const rootReadme = path.join(root, "README.md");
  const readmePreview = (await exists(rootReadme))
    ? (await fs.readFile(rootReadme, "utf8")).slice(0, 2000)
    : "";

  return { manifestPaths, readmePreview };
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const { files, dirs } = await walk(options.root, options);
  const manifests = await collectManifests(options.root, files);
  const inventory = {
    root: options.root,
    generatedAt: new Date().toISOString(),
    totals: { files: files.length, directories: dirs.length },
    extensions: extensionSummary(files),
    topDirectories: topDirs(files),
    manifests,
    packages: await collectPackageJson(options.root, files),
    likelyEntrypoints: likelyEntrypoints(files),
    symbols: await collectSymbols(options.root, files, options),
    largestFiles: [...files].sort((a, b) => b.size - a.size).slice(0, 50),
  };

  const output = `${JSON.stringify(inventory, null, 2)}\n`;
  if (options.out) {
    await fs.mkdir(path.dirname(path.resolve(options.out)), { recursive: true });
    await fs.writeFile(options.out, output);
  } else {
    process.stdout.write(output);
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
