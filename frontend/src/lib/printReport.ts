/**
 * Printable-report helpers (client-side, v1).
 *
 * The PDF export reuses the existing Markdown report generator (see
 * `reportExport.ts`) as its single source of truth.  This module converts that
 * Markdown into clean, print-friendly HTML which is rendered in a preview modal;
 * the user then prints it (or chooses "Save as PDF") via the browser dialog.
 *
 * The converter only understands the small Markdown subset the report builders
 * emit (headings, GitHub tables, bullet lists, blockquotes, bold, full-line
 * italics, paragraphs).  All user-derived text is HTML-escaped, so the rendered
 * output is safe to inject with `dangerouslySetInnerHTML`.
 */

/** Escape the five HTML-significant characters. */
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/** Escape, then apply inline `**bold**` emphasis. */
function inline(s: string): string {
  return escapeHtml(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

/**
 * Split a Markdown table row into trimmed cells, honouring `\|` escapes that
 * the report generator uses for literal pipes inside a cell.
 */
function splitTableRow(line: string): string[] {
  let s = line.trim();
  if (s.startsWith("|")) s = s.slice(1);
  if (s.endsWith("|")) s = s.slice(0, -1);

  const cells: string[] = [];
  let cur = "";
  for (let i = 0; i < s.length; i++) {
    const ch = s[i];
    if (ch === "\\" && s[i + 1] === "|") {
      cur += "|";
      i++;
      continue;
    }
    if (ch === "|") {
      cells.push(cur.trim());
      cur = "";
      continue;
    }
    cur += ch;
  }
  cells.push(cur.trim());
  return cells;
}

function isSeparatorRow(cells: string[]): boolean {
  return cells.length > 0 && cells.every((c) => /^:?-{2,}:?$/.test(c));
}

function renderTable(rows: string[][]): string {
  if (!rows.length) return "";
  const header = rows[0];
  let bodyStart = 1;
  if (rows.length > 1 && isSeparatorRow(rows[1])) bodyStart = 2;

  const thead = `<thead><tr>${header
    .map((c) => `<th>${inline(c)}</th>`)
    .join("")}</tr></thead>`;
  const body = rows
    .slice(bodyStart)
    .map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`)
    .join("");
  return `<table>${thead}<tbody>${body}</tbody></table>`;
}

/**
 * Convert a QuantLab Markdown report into print-friendly HTML.
 *
 * Block grammar handled: `#`/`##`/`###` headings, `|`-delimited tables,
 * `- ` bullet lists, `> ` blockquotes, whole-line `_italic_`, and paragraphs.
 */
export function markdownToHtml(markdown: string): string {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const out: string[] = [];
  let listOpen = false;

  const closeList = () => {
    if (listOpen) {
      out.push("</ul>");
      listOpen = false;
    }
  };

  let i = 0;
  while (i < lines.length) {
    const raw = lines[i];
    const t = raw.trim();

    // Blank line — paragraph / list break.
    if (t === "") {
      closeList();
      i++;
      continue;
    }

    // Table: consume consecutive lines that look like table rows.
    if (t.startsWith("|")) {
      closeList();
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        rows.push(splitTableRow(lines[i]));
        i++;
      }
      out.push(renderTable(rows));
      continue;
    }

    // Headings.
    if (t.startsWith("### ")) {
      closeList();
      out.push(`<h3>${inline(t.slice(4))}</h3>`);
      i++;
      continue;
    }
    if (t.startsWith("## ")) {
      closeList();
      out.push(`<h2>${inline(t.slice(3))}</h2>`);
      i++;
      continue;
    }
    if (t.startsWith("# ")) {
      closeList();
      out.push(`<h1>${inline(t.slice(2))}</h1>`);
      i++;
      continue;
    }

    // Blockquote (single line).
    if (t.startsWith(">")) {
      closeList();
      out.push(`<blockquote>${inline(t.replace(/^>\s?/, ""))}</blockquote>`);
      i++;
      continue;
    }

    // Bullet list item.
    if (t.startsWith("- ")) {
      if (!listOpen) {
        out.push("<ul>");
        listOpen = true;
      }
      out.push(`<li>${inline(t.slice(2))}</li>`);
      i++;
      continue;
    }

    // Whole-line italic, e.g. `_Generated at …_` or `_No trades._`.
    const it = t.match(/^_(.+)_$/);
    if (it) {
      closeList();
      out.push(`<p><em>${escapeHtml(it[1])}</em></p>`);
      i++;
      continue;
    }

    // Paragraph.
    closeList();
    out.push(`<p>${inline(t)}</p>`);
    i++;
  }

  closeList();
  return out.join("\n");
}
