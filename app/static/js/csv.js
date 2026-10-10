export const NAME_MAX = 100;

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function splitLine(line, delimiter) {
  const cells = [];
  let cell = "";
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    if (quoted) {
      if (char !== '"') {
        cell += char;
      } else if (line[index + 1] === '"') {
        cell += '"';
        index += 1;
      } else {
        quoted = false;
      }
    } else if (char === '"') {
      quoted = true;
    } else if (char === delimiter) {
      cells.push(cell);
      cell = "";
    } else {
      cell += char;
    }
  }
  cells.push(cell);
  return cells.map((value) => value.trim());
}

function findHeader(cells) {
  const lower = cells.map((value) => value.toLowerCase());
  const name = lower.findIndex((value) => value.includes("name"));
  const email = lower.findIndex((value) => value.includes("mail"));
  const found = name >= 0 && email >= 0 && name !== email && !EMAIL.test(cells[email]);
  return found ? { name, email } : null;
}

export function validate({ name, email }) {
  const issues = [];
  if (!name) {
    issues.push("Name is required");
  } else if (name.length > NAME_MAX) {
    issues.push(`Name is longer than ${NAME_MAX} characters`);
  }
  if (!email) {
    issues.push("Email is required");
  } else if (!EMAIL.test(email)) {
    issues.push("Email is not valid");
  }
  return issues;
}

export function parseRecipients(text) {
  const lines = text.split(/\r?\n/).filter((line) => line.trim() !== "");
  if (lines.length === 0) {
    return [];
  }
  const delimiter = lines[0].includes("\t") ? "\t" : ",";
  const table = lines.map((line) => splitLine(line, delimiter));
  const header = findHeader(table[0]);
  const columns = header ?? { name: 0, email: 1 };
  return table.slice(header ? 1 : 0).map((cells) => {
    const row = { name: cells[columns.name] ?? "", email: cells[columns.email] ?? "" };
    return { ...row, issues: validate(row) };
  });
}

function quote(value) {
  return /[",\r\n]/.test(value) ? `"${value.replaceAll('"', '""')}"` : value;
}

export function toCsv(table) {
  return table.map((row) => row.map(quote).join(",")).join("\n") + "\n";
}
