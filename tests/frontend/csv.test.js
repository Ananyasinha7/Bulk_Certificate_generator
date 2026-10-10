import assert from "node:assert/strict";
import test from "node:test";

import { parseRecipients, toCsv } from "../../app/static/js/csv.js";

test("parses comma separated rows", () => {
  const rows = parseRecipients("Asha Verma, asha@example.com\nRohan Mehta,rohan@example.com\n");
  assert.deepEqual(
    rows.map(({ name, email, issues }) => [name, email, issues.length]),
    [
      ["Asha Verma", "asha@example.com", 0],
      ["Rohan Mehta", "rohan@example.com", 0],
    ],
  );
});

test("parses tab separated rows pasted from a spreadsheet", () => {
  const [row] = parseRecipients("Asha Verma\tasha@example.com");
  assert.equal(row.name, "Asha Verma");
  assert.equal(row.email, "asha@example.com");
});

test("skips a header row and honours its column order", () => {
  const rows = parseRecipients("Email,Full Name\nasha@example.com,Asha Verma");
  assert.equal(rows.length, 1);
  assert.equal(rows[0].name, "Asha Verma");
  assert.equal(rows[0].email, "asha@example.com");
});

test("does not mistake a gmail address for a header", () => {
  const rows = parseRecipients("Rename Smith, ravi@gmail.com");
  assert.equal(rows.length, 1);
});

test("keeps quoted commas inside a name", () => {
  const [row] = parseRecipients('"Verma, Asha",asha@example.com');
  assert.equal(row.name, "Verma, Asha");
});

test("reports problems per row", () => {
  const rows = parseRecipients(
    [",a@example.com", `${"x".repeat(101)},a@example.com`, "Asha,not-an-email", "Asha"].join("\n"),
  );
  assert.deepEqual(
    rows.map((row) => row.issues),
    [
      ["Name is required"],
      ["Name is longer than 100 characters"],
      ["Email is not valid"],
      ["Email is required"],
    ],
  );
});

test("returns no rows for blank input", () => {
  assert.deepEqual(parseRecipients("  \n\n"), []);
});

test("toCsv quotes cells and round trips", () => {
  const csv = toCsv([["Verma, Asha", 'say "hi"']]);
  assert.equal(csv, '"Verma, Asha","say ""hi"""\n');
  const [row] = parseRecipients(toCsv([["Verma, Asha", "asha@example.com"]]));
  assert.equal(row.name, "Verma, Asha");
});
