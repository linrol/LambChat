export type SandpackTemplate =
  | "react"
  | "vue"
  | "vanilla"
  | "angular"
  | "svelte"
  | "solid"
  | "node"
  | "nextjs"
  | "static";

const TEMPLATE_MAP: Record<string, SandpackTemplate> = {
  react: "react",
  vue: "vue",
  vanilla: "vanilla",
  angular: "angular",
  svelte: "svelte",
  solid: "solid",
  nextjs: "nextjs",
  static: "static",
};

const ENTRY_CANDIDATES = [
  "/pages/index.tsx",
  "/pages/index.jsx",
  "/pages/_app.tsx",
  "/pages/_app.jsx",
  "/index.html",
  "/src/index.html",
  "/public/index.html",
  "/src/main.ts",
  "/src/index.ts",
  "/src/index.tsx",
  "/src/index.jsx",
  "/src/main.tsx",
  "/src/main.jsx",
  "/src/main.js",
  "/main.ts",
  "/index.ts",
  "/index.tsx",
  "/index.jsx",
  "/index.js",
  "/main.tsx",
  "/main.jsx",
  "/main.js",
  "/src/main.vue",
  "/src/App.svelte",
  "/App.tsx",
  "/App.jsx",
] as const;

function hasAnyFile(
  files: Record<string, string>,
  candidates: readonly string[],
): boolean {
  return candidates.some((path) => path in files);
}

function hasReactEntrypoint(files: Record<string, string>): boolean {
  return hasAnyFile(files, [
    "/src/main.jsx",
    "/src/main.tsx",
    "/src/index.jsx",
    "/src/index.tsx",
    "/main.jsx",
    "/main.tsx",
    "/index.jsx",
    "/index.tsx",
    "/App.jsx",
    "/App.tsx",
  ]);
}

function hasVueEntrypoint(files: Record<string, string>): boolean {
  return hasAnyFile(files, ["/src/main.vue", "/src/App.vue", "/App.vue"]);
}

function hasSvelteEntrypoint(files: Record<string, string>): boolean {
  return hasAnyFile(files, [
    "/src/App.svelte",
    "/App.svelte",
    "/src/main.svelte",
    "/main.svelte",
  ]);
}

function hasNextJsEntrypoint(files: Record<string, string>): boolean {
  return hasAnyFile(files, [
    "/pages/index.tsx",
    "/pages/index.jsx",
    "/pages/_app.tsx",
    "/pages/_app.jsx",
  ]);
}

function hasAngularEntrypoint(files: Record<string, string>): boolean {
  return (
    "/angular.json" in files &&
    hasAnyFile(files, ["/src/main.ts", "/src/main.js", "/main.ts", "/main.js"])
  );
}

function hasSolidEntrypoint(files: Record<string, string>): boolean {
  return Object.values(files).some(
    (content) =>
      content.includes("solid-js") ||
      content.includes("solid-app-router") ||
      content.includes("from 'solid-js/web'") ||
      content.includes('from "solid-js/web"'),
  );
}

export function resolveSandpackTemplate(
  template: string,
  files: Record<string, string>,
): SandpackTemplate {
  if (template === "static") {
    return "static";
  }

  if (template === "angular") {
    return "angular";
  }

  if (template === "svelte") {
    return "svelte";
  }

  if (template === "solid") {
    return "solid";
  }

  if (template === "nextjs") {
    return "nextjs";
  }

  if (hasNextJsEntrypoint(files)) {
    return "nextjs";
  }

  if (hasAngularEntrypoint(files)) {
    return "angular";
  }

  if (hasSvelteEntrypoint(files)) {
    return "svelte";
  }

  if (hasSolidEntrypoint(files)) {
    return "solid";
  }

  if (hasReactEntrypoint(files)) {
    return "react";
  }

  if (hasVueEntrypoint(files)) {
    return "vue";
  }

  if ("/index.html" in files) {
    return "static";
  }

  return TEMPLATE_MAP[template] || "vanilla";
}

export function resolveEntryFile(
  files: Record<string, string>,
  entry?: string,
): string {
  if (entry) {
    return entry.startsWith("/") ? entry : `/${entry}`;
  }

  const matched = ENTRY_CANDIDATES.find((path) => path in files);
  return matched || Object.keys(files)[0] || "/index.js";
}

/** normalizePaths: 确保所有文件路径以 / 开头 */
function normalizePaths(files: Record<string, string>): Record<string, string> {
  const result: Record<string, string> = {};
  for (const [path, content] of Object.entries(files)) {
    result[path.startsWith("/") ? path : `/${path}`] = content;
  }
  return result;
}

export interface SandpackConfig {
  /** 传给 SandpackProvider 的 template（static 模板时为 undefined） */
  template?: SandpackTemplate;
  /** 传给 SandpackProvider 的 customSetup（static 模板或框架模板需要覆盖入口时使用） */
  customSetup?: {
    entry: string;
    environment?: "static" | "node" | "parcel";
  };
  /** 规范化后的用户文件 */
  files: Record<string, string>;
  /** 入口文件路径 */
  entryFile: string;
  /** 文件浏览器可见的文件列表 */
  visibleFiles: string[];
}

/**
 * 构建完整的 Sandpack 配置
 *
 * 核心设计：
 * - static 模板：不使用 Sandpack 内置模板，改用 customSetup 避免模板默认文件
 *   （Hello world、/styles.css、/package.json）通过 Object.assign 污染用户项目
 * - 框架模板（react/vue 等）：使用内置模板获取依赖和构建配置，同时通过
 *   customSetup.entry 覆盖模板默认入口，确保用户项目正确渲染
 */
/**
 * vfile v6+ 使用 Node.js package.json `imports` 字段定义子路径导入（#minpath 等），
 * esbuild（Sandpack 打包器底层）不支持此字段。
 *
 * 每个 shim 文件提供 vfile 浏览器兼容版本的实现：
 * - minpath.browser.js → 完整的 path polyfill（path-browserify 衍生）
 * - minproc.browser.js → 完整的 process polyfill（process 衍生）
 * - minurl.browser.js + minurl.shared.js → 完整的 url polyfill
 *
 * 关键：vfile 源码中使用 `import {minpath} from '#minpath'`，
 * 打包器尝试解析时找不到 '#minpath' 对应的文件。
 * 通过提供这些 shim，打包器能找到这些路径并正确 bundle。
 */
/**
 * vfile v6+ 使用 Node.js package.json `imports` 字段（#minpath 等），
 * esbuild（Sandpack 打包器底层）不支持此字段，导致 ModuleNotFoundError。
 *
 * 解决方案：提供 vfile 的入口文件，将所有 # 导入替换为内联实现。
 * VFileMessage 的 import 保持不变（vfile-message 不使用 imports 字段）。
 *
 * 注入位置：/node_modules/vfile/lib/index.js
 * 触发时机：Sandpack bundler 解析用户代码 → 找到 vfile → 优先使用虚拟文件覆盖 CDN 源。
 */
/**
 * 完整的 vfile 入口文件（基于 vfile@6.0.3 源码）。
 * 将原来使用 # 导入的 3 个模块内联，保留 VFileMessage 的正常 import。
 */
const VFILE_INDEX_SHIM = `import {VFileMessage} from 'vfile-message'

// 内联 minproc
const minproc = {cwd: () => '/'}

// 内联 minurl.shared
function isUrl(v) {
  return Boolean(
    v !== null &&
    typeof v === 'object' &&
    'href' in v && v.href &&
    'protocol' in v && v.protocol &&
    v.auth === undefined
  )
}

// 内联 minurl.browser
function urlToPath(p) {
  if (typeof p === 'string') p = new URL(p)
  else if (!isUrl(p)) {
    const e = new TypeError('The "path" argument must be of type string or an instance of URL')
    e.code = 'ERR_INVALID_ARG_TYPE'
    throw e
  }
  if (p.protocol !== 'file:') {
    const e = new TypeError('The URL must be of scheme file')
    e.code = 'ERR_INVALID_URL_SCHEME'
    throw e
  }
  return decodeURIComponent(p.pathname)
}

// 内联 minpath.browser
function assertPath(p) { if (typeof p !== 'string') throw new TypeError('Path must be a string') }

function basename(p, e) {
  assertPath(p)
  if (e !== undefined && typeof e !== 'string') throw new TypeError('"ext" argument must be a string')
  let i = p.length
  if (e === undefined || e.length === 0 || e.length > p.length) {
    while (i--) {
      if (p.codePointAt(i) === 47) {
        if (p.codePointAt(i + 1) !== 46 || p.codePointAt(i + 2) === 47) return p.slice(i + 1)
      }
    }
    return p || ''
  }
  let s = -1, f = e.length - 1
  while (i--) {
    if (p.codePointAt(i) === 47) {
      if (s < 0) s = i + 1
    } else {
      if (f >= 0) {
        if (p.codePointAt(i) === e.codePointAt(f--)) { if (f < 0) s = i }
        else { f = -1 }
      } else { s = i + 1 }
    }
  }
  return s
}

function dirname(p) {
  assertPath(p)
  if (p.length === 0) return '.'
  let i = p.length
  while (--i && p.codePointAt(i) !== 47);
  return i <= 0 ? '.' : p.slice(0, i)
}

function extname(p) {
  assertPath(p)
  let i = p.length, e = -1, s = 0
  while (i--) {
    if (p.codePointAt(i) === 47) {
      if (e >= 0 && s === 1 && p.codePointAt(i + 1) === 46) return p.slice(i + 1, e + 1)
      e = -1; s = 0
    } else if (p.codePointAt(i) === 46) { if (e < 0) e = i + 1 }
    else if (e >= 0) s = 1
  }
  return ''
}

function join(...s) {
  let r
  for (let i = 0; i < s.length; i++) {
    assertPath(s[i])
    r = r === undefined ? s[i] : r + (r.endsWith('/') ? '' : '/') + s[i]
  }
  return r === undefined ? '.' : r
}

const minpath = { basename, dirname, extname, join, sep: '/' }

const order = ['history', 'path', 'basename', 'stem', 'extname', 'dirname']

export class VFile {
  constructor(value) {
    let options
    if (!value) { options = {} }
    else if (isUrl(value)) { options = { path: value } }
    else if (typeof value === 'string' || isUint8Array(value)) { options = { value } }
    else { options = value }
    this.cwd = 'cwd' in options ? '' : minproc.cwd()
    this.data = {}
    this.history = []
    this.messages = []
    this.value = undefined
    this.map = undefined
    this.result = undefined
    this.stored = undefined
    let index = -1
    while (++index < order.length) {
      const field = order[index]
      if (field in options && options[field] !== undefined && options[field] !== null) {
        this[field] = field === 'history' ? [...options[field]] : options[field]
      }
    }
    let field
    for (field in options) {
      if (!order.includes(field)) this[field] = options[field]
    }
  }
  get basename() { return typeof this.path === 'string' ? minpath.basename(this.path) : undefined }
  set basename(v) {
    assertNonEmpty(v, 'basename')
    assertPart(v, 'basename')
    this.path = minpath.join(this.dirname || '', v)
  }
  get dirname() { return typeof this.path === 'string' ? minpath.dirname(this.path) : undefined }
  set dirname(v) {
    assertPath(this.basename, 'dirname')
    this.path = minpath.join(v || '', this.basename)
  }
  get extname() { return typeof this.path === 'string' ? minpath.extname(this.path) : undefined }
  set extname(v) {
    assertPart(v, 'extname')
    assertPath(this.dirname, 'extname')
    if (v) {
      if (v.codePointAt(0) !== 46) throw new Error('\`extname\` must start with \`.\`')
      if (v.includes('.', 1)) throw new Error('\`extname\` cannot contain multiple dots')
    }
    this.path = minpath.join(this.dirname, this.stem + (v || ''))
  }
  get path() { return this.history[this.history.length - 1] }
  set path(v) {
    if (isUrl(v)) v = urlToPath(v)
    assertNonEmpty(v, 'path')
    if (this.path !== v) this.history.push(v)
  }
  get stem() { return typeof this.path === 'string' ? minpath.basename(this.path, this.extname) : undefined }
  set stem(v) {
    assertNonEmpty(v, 'stem')
    assertPart(v, 'stem')
    this.path = minpath.join(this.dirname || '', v + (this.extname || ''))
  }
  fail(causeOrReason, optionsOrParentOrPlace, origin) {
    const message = this.message(causeOrReason, optionsOrParentOrPlace, origin)
    message.fatal = true
    throw message
  }
  info(causeOrReason, optionsOrParentOrPlace, origin) {
    const message = this.message(causeOrReason, optionsOrParentOrPlace, origin)
    message.fatal = undefined
    return message
  }
  message(causeOrReason, optionsOrParentOrPlace, origin) {
    const message = new VFileMessage(causeOrReason, optionsOrParentOrPlace, origin)
    if (this.path) { message.name = this.path + ':' + message.name; message.file = this.path }
    message.fatal = false
    this.messages.push(message)
    return message
  }
  toString(encoding) {
    if (this.value === undefined) return ''
    if (typeof this.value === 'string') return this.value
    return new TextDecoder(encoding || undefined).decode(this.value)
  }
}

function assertPart(part, name) {
  if (part && part.includes(minpath.sep)) {
    throw new Error('\`' + name + '\` cannot be a path: did not expect \`/\`')
  }
}

function assertNonEmpty(part, name) {
  if (!part) throw new Error('\`' + name + '\` cannot be empty')
}

function assertPath(path, name) {
  if (!path) throw new Error('Setting \`' + name + '\` requires \`path\` to be set too')
}

function isUint8Array(value) {
  return Boolean(value && typeof value === 'object' && 'byteLength' in value && 'byteOffset' in value)
}
`;

const VFILE_SHIMS: Record<string, string> = {
  // 关键：拦截 vfile 入口文件，替换 # 导入为内联实现
  // Sandpack bundler 解析 vfile 时优先使用此虚拟文件
  "/node_modules/vfile/lib/index.js": VFILE_INDEX_SHIM,
};

export function buildSandpackConfig(
  template: string,
  files: Record<string, string>,
  entry?: string,
): SandpackConfig {
  const normalized = normalizePaths(files);
  const detected = resolveSandpackTemplate(template, normalized);
  const entryFile = resolveEntryFile(normalized, entry);
  const visibleFiles = Object.keys(normalized);

  // shim 文件仅供打包器解析用，不出现在文件浏览器中
  const sandpackFiles = { ...VFILE_SHIMS, ...normalized };

  if (detected === "static") {
    return {
      customSetup: { entry: entryFile, environment: "static" },
      files: sandpackFiles,
      entryFile,
      visibleFiles,
    };
  }

  // 框架模板：使用 customSetup.entry 覆盖 Sandpack 模板默认入口，
  // 防止模板的 Hello World 默认文件污染用户项目
  return {
    template: detected,
    customSetup: { entry: entryFile },
    files: sandpackFiles,
    entryFile,
    visibleFiles,
  };
}
