/** Test-only syntax checks, not a router or a data-flow analyzer. */
import { readdirSync, readFileSync, realpathSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, relative, resolve, isAbsolute } from "node:path";
import ts from "typescript";

const SRC_ROOT = realpathSync(resolve(dirname(fileURLToPath(import.meta.url)), ".."));

function readSource(path: string): string {
  const resolved = realpathSync(resolve(SRC_ROOT, path));
  const child = relative(SRC_ROOT, resolved);
  if (child.startsWith("..") || isAbsolute(child)) throw new Error("Source scan must stay inside frontend/src");
  return readFileSync(resolved, "utf8");
}

function parse(source: string): ts.SourceFile {
  // TypeScript is already a devDependency; no regex stripping or code execution.
  const result = ts.transpileModule(source, {
    fileName: "navigation.tsx", reportDiagnostics: true,
    compilerOptions: { jsx: ts.JsxEmit.Preserve, target: ts.ScriptTarget.ESNext },
  });
  const errors = result.diagnostics?.filter((d) => d.category === ts.DiagnosticCategory.Error) ?? [];
  if (errors.length) throw new Error(`Invalid navigation source: ${errors.map((d) => ts.flattenDiagnosticMessageText(d.messageText, " ")).join("; ")}`);
  return ts.createSourceFile("navigation.tsx", source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
}

function visit(node: ts.Node, action: (node: ts.Node) => void): void {
  action(node);
  ts.forEachChild(node, (child) => visit(child, action));
}

function unwrap(node: ts.Expression): ts.Expression {
  while (ts.isParenthesizedExpression(node) || ts.isAsExpression(node) || ts.isSatisfiesExpression(node)) node = node.expression;
  return node;
}

function literal(node: ts.Expression): string | undefined {
  const value = unwrap(node);
  return ts.isStringLiteral(value) ? value.text : undefined;
}

function nonempty(values: string[], description: string): string[] {
  if (!values.length) throw new Error(`No ${description} found. Update sourceScan.ts and its fixtures when changing navigation syntax.`);
  return values;
}

export function parseViewUnionIds(source: string): string[] {
  const declarations = parse(source).statements.filter((s): s is ts.TypeAliasDeclaration =>
    ts.isTypeAliasDeclaration(s) && s.name.text === "View" && !!s.modifiers?.some((m) => m.kind === ts.SyntaxKind.ExportKeyword));
  if (declarations.length !== 1) throw new Error("Expected exactly one exported View type in AppShell.tsx");
  const type = declarations[0].type;
  const members = ts.isUnionTypeNode(type) ? type.types : [type];
  return nonempty(members.map((m) => {
    if (!ts.isLiteralTypeNode(m) || !ts.isStringLiteral(m.literal)) throw new Error("View must contain only string literal members");
    return m.literal.text;
  }), "View members");
}

export function parseSwitcherViewIds(source: string): string[] {
  const ids: string[] = [];
  visit(parse(source), (node) => {
    if (!ts.isJsxExpression(node) || !node.expression) return;
    const expr = unwrap(node.expression);
    if (!ts.isBinaryExpression(expr) || expr.operatorToken.kind !== ts.SyntaxKind.AmpersandAmpersandToken) return;
    const condition = unwrap(expr.left);
    const render = unwrap(expr.right);
    if (!ts.isBinaryExpression(condition) || condition.operatorToken.kind !== ts.SyntaxKind.EqualsEqualsEqualsToken ||
        !ts.isIdentifier(condition.left) || condition.left.text !== "view") return;
    if (!ts.isJsxElement(render) && !ts.isJsxSelfClosingElement(render) && !ts.isJsxFragment(render)) return;
    const id = literal(condition.right);
    if (id === undefined) throw new Error("Workspace render branch needs a literal View ID");
    ids.push(id);
  });
  return nonempty(ids, "JSX workspace render branches in page.tsx");
}

export function parseViewMetaKeys(source: string): string[] {
  const maps: ts.VariableDeclaration[] = [];
  visit(parse(source), (node) => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.name.text === "VIEW_META") maps.push(node);
  });
  if (maps.length !== 1 || !maps[0].initializer) throw new Error("Expected one VIEW_META initializer in page.tsx");
  const object = unwrap(maps[0].initializer);
  if (!ts.isObjectLiteralExpression(object)) throw new Error("VIEW_META must be a literal object");
  return nonempty(object.properties.map((p) => {
    if (!ts.isPropertyAssignment(p) || (!ts.isIdentifier(p.name) && !ts.isStringLiteral(p.name))) throw new Error("VIEW_META keys must be explicit, not computed/spread");
    return p.name.text;
  }), "VIEW_META keys");
}

export function parseNavLiterals(source: string, name: "handleNav" | "onNav"): string[] {
  const ids: string[] = [];
  visit(parse(source), (node) => {
    if (!ts.isCallExpression(node) || !ts.isIdentifier(node.expression) || node.expression.text !== name) return;
    const id = node.arguments[0] && literal(node.arguments[0]);
    if (id !== undefined) ids.push(id);
  });
  return ids;
}

/** Only these reviewed, frontend-owned data tables use view/route as workspace IDs. */
const NAV_DATA_FIELDS: Readonly<Record<string, string>> = {
  "HomeDashboard.tsx": "view",
  "PortfolioShowcasePanel.tsx": "route",
  "DeveloperOnboardingPanel.tsx": "route",
  "ReleaseNotesCenterPanel.tsx": "route",
  "PublicReleaseCandidatePanel.tsx": "route",
};

export function parseNavDataTargets(source: string, field: string): string[] {
  const ids: string[] = [];
  visit(parse(source), (node) => {
    if (!ts.isPropertyAssignment(node) || (!ts.isIdentifier(node.name) && !ts.isStringLiteral(node.name)) || node.name.text !== field) return;
    const id = literal(node.initializer);
    if (id === undefined) throw new Error(`Navigation data field ${field} must be a literal; document any new dynamic mapping`);
    ids.push(id);
  });
  return nonempty(ids, `${field} navigation data fields`);
}

export function isProductionSource(path: string): boolean {
  const parts = path.replace(/\\/g, "/").split("/");
  return !parts.some((p) => p.startsWith(".") || ["node_modules", "__tests__", "__fixtures__", "fixtures", "generated", "test", "e2e"].includes(p)) &&
    /\.tsx?$/.test(path) && !/\.(test|spec)\.[cm]?[jt]sx?$/.test(path);
}

export const readViewUnionIds = (): string[] => parseViewUnionIds(readSource("components/AppShell.tsx"));
export const readSwitcherViewIds = (): string[] => parseSwitcherViewIds(readSource("app/page.tsx"));
export const readViewMetaKeys = (): string[] => parseViewMetaKeys(readSource("app/page.tsx"));
export const readHandleNavLiterals = (): string[] => parseNavLiterals(readSource("app/page.tsx"), "handleNav");

export function readComponentNavTargets(): { file: string; view: string }[] {
  const found: { file: string; view: string }[] = [];
  const dataFiles = new Set(Object.keys(NAV_DATA_FIELDS));
  const walk = (dir: string): void => {
    for (const entry of readdirSync(resolve(SRC_ROOT, dir), { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name, "en"))) {
      const child = join(dir, entry.name);
      if (entry.isDirectory() && isProductionSource(join(child, "probe.tsx"))) walk(child);
      else if (entry.isFile() && isProductionSource(child)) {
        const source = readSource(child);
        const ids = parseNavLiterals(source, "onNav");
        const field = NAV_DATA_FIELDS[entry.name];
        if (field) {
          dataFiles.delete(entry.name);
          ids.push(...parseNavDataTargets(source, field));
        }
        found.push(...ids.map((view) => ({ file: child.replace(/\\/g, "/"), view })));
      }
    }
  };
  walk("components");
  if (dataFiles.size) throw new Error(`Reviewed navigation data components moved: ${Array.from(dataFiles).join(", ")}`);
  return found;
}
