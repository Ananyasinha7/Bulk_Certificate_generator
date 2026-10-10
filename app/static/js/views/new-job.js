import { createJob, getLimits, previewCertificate } from "../api.js";
import { parseRecipients, toCsv } from "../csv.js";
import { el } from "../dom.js";
import { describeError, formatDate, plural } from "../format.js";
import { PRESETS } from "../presets.js";

const PREVIEW_LIMIT = 100;
const PLACEHOLDER = "Asha Verma, asha@example.com\nRohan Mehta, rohan@example.com";
const SAMPLE_CSV = "name,email\nAsha Verma,asha@example.com\nRohan Mehta,rohan@example.com\n";
const SAMPLE_HREF = `data:text/csv;charset=utf-8,${encodeURIComponent(SAMPLE_CSV)}`;

function field(id, label, attributes) {
  const input = el("input", { id, name: id, autocomplete: "off", ...attributes });
  return { input, node: el("div", { class: "field" }, el("label", { for: id }, label), input) };
}

function createPaper() {
  const lines = {
    heading: el("p", { class: "paper-heading" }),
    intro: el("p", { class: "paper-small" }),
    name: el("p", { class: "paper-name" }),
    statement: el("p", { class: "paper-small" }),
    title: el("p", { class: "paper-title" }),
    issuer: el("p", { class: "paper-small" }),
    date: el("p", { class: "paper-tiny" }),
  };
  const node = el(
    "div",
    { class: "paper", role: "img", "aria-label": "Sketch of the certificate wording" },
    ...Object.values(lines),
  );
  return { node, lines };
}

function recipientTable(rows) {
  const numbered = rows.map((row, index) => ({ ...row, number: index + 1 }));
  const problems = numbered.filter((row) => row.issues.length);
  const ready = numbered.filter((row) => !row.issues.length);
  const shown = [...problems, ...ready].slice(0, PREVIEW_LIMIT).sort((a, b) => a.number - b.number);
  const body = shown.map((row) =>
    el(
      "tr",
      {},
      el("td", { class: "num" }, String(row.number)),
      el(
        "td",
        { class: "person" },
        el("span", {}, row.name || "(no name)"),
        el("span", { class: "email" }, row.email || "(no email)"),
      ),
      el("td", { class: row.issues.length ? "issue" : "ready" }, row.issues.length ? row.issues.join(". ") : "Ready"),
    ),
  );
  const head = el(
    "tr",
    {},
    el("th", { scope: "col" }, "Row"),
    el("th", { scope: "col" }, "Recipient"),
    el("th", { scope: "col" }, "Check"),
  );
  const more = rows.length > PREVIEW_LIMIT ? el("p", { class: "hint" }, `Showing ${PREVIEW_LIMIT} of ${rows.length} rows. Problem rows are listed first.`) : null;
  return [
    el("div", { class: "table-wrap" }, el("table", { class: "results" }, el("thead", {}, head), el("tbody", {}, body))),
    more,
  ];
}

export function renderNewJob(root) {
  document.title = "Issue certificates - Certificate Issuer";
  let rows = [];
  let busy = false;
  let maxRecipients = null;
  let previewToken = 0;
  let previewUrl = null;

  const title = field("title", "Event or course name", { placeholder: "Python Bootcamp", maxlength: "200", required: true });
  const issuer = field("issuer", "Issued by", { placeholder: "Acme Academy", maxlength: "200", required: true });
  const issueDate = field("issue_date", "Issue date", {
    type: "date",
    required: true,
    value: new Date().toLocaleDateString("en-CA"),
  });
  const [defaults] = PRESETS;
  const heading = field("heading", "Certificate heading", { maxlength: "200", required: true, value: defaults.heading });
  const intro = field("intro", "Introduction line", { maxlength: "200", required: true, value: defaults.intro });
  const statement = field("statement", "Statement line", { maxlength: "200", required: true, value: defaults.statement });
  const preset = el(
    "select",
    { id: "preset", name: "preset", onchange: applyPreset },
    PRESETS.map((item) => el("option", { value: item.id }, item.label)),
    el("option", { value: "custom" }, "Custom"),
  );
  const paper = createPaper();

  const textarea = el("textarea", {
    id: "recipients",
    name: "recipients",
    spellcheck: "false",
    placeholder: PLACEHOLDER,
    oninput: onRecipientsInput,
  });
  const fileInput = el("input", {
    type: "file",
    accept: ".csv,.tsv,.txt,text/csv,text/plain",
    hidden: true,
    onchange: () => readFile(fileInput.files[0]),
  });
  const limitNote = el("p", { class: "hint" });
  const recipientPreview = el("div", { id: "recipient-preview", "aria-live": "polite" });
  const errorBox = el("p", { class: "error", role: "alert" });
  const summary = el("p", { class: "summary", "aria-live": "polite" });
  const previewButton = el("button", { class: "btn", type: "button", onclick: openPreview }, "Preview first certificate");
  const submit = el("button", { class: "btn btn-primary", type: "submit" }, "Generate certificates");

  const dialogName = el("h2", { id: "preview-title" });
  const dialogStatus = el("p", { class: "hint", role: "status" });
  const frame = el("iframe", { class: "pdf-frame", title: "Certificate preview", hidden: true });
  const openLink = el("a", { class: "btn", target: "_blank", rel: "noopener", hidden: true }, "Open PDF in new tab");
  const dialogSubmit = el("button", { class: "btn btn-primary", type: "button", onclick: generateFromDialog }, "Generate certificates");
  const dialog = el(
    "dialog",
    { class: "preview-dialog", "aria-labelledby": "preview-title", onclose: releasePreview },
    el(
      "div",
      { class: "dialog-body" },
      el(
        "header",
        { class: "dialog-head" },
        dialogName,
        el("p", { class: "hint" }, "A sample of the first valid row. Every certificate in the job uses this layout."),
      ),
      dialogStatus,
      frame,
      el(
        "footer",
        { class: "dialog-actions" },
        openLink,
        el("div", { class: "button-row" }, el("button", { class: "btn", type: "button", onclick: () => dialog.close() }, "Back to editing"), dialogSubmit),
      ),
    ),
  );
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) {
      dialog.close();
    }
  });

  function spec() {
    return {
      title: title.input.value.trim(),
      issuer: issuer.input.value.trim(),
      issue_date: issueDate.input.value,
      heading: heading.input.value.trim(),
      intro: intro.input.value.trim(),
      statement: statement.input.value.trim(),
    };
  }

  function applyPreset() {
    const chosen = PRESETS.find((item) => item.id === preset.value);
    if (!chosen) {
      return;
    }
    heading.input.value = chosen.heading;
    intro.input.value = chosen.intro;
    statement.input.value = chosen.statement;
    sync();
  }

  function syncPreset() {
    const match = PRESETS.find(
      (item) =>
        item.heading === heading.input.value.trim() &&
        item.intro === intro.input.value.trim() &&
        item.statement === statement.input.value.trim(),
    );
    preset.value = match ? match.id : "custom";
  }

  function onWordingInput() {
    syncPreset();
    sync();
  }

  function onRecipientsInput() {
    rows = parseRecipients(textarea.value);
    sync();
  }

  async function readFile(file) {
    if (!file) {
      return;
    }
    textarea.value = await file.text();
    fileInput.value = "";
    onRecipientsInput();
  }

  function removeProblems() {
    textarea.value = toCsv(rows.filter((row) => !row.issues.length).map((row) => [row.name, row.email]));
    onRecipientsInput();
    textarea.focus();
  }

  function trimToLimit() {
    textarea.value = toCsv(rows.slice(0, maxRecipients).map((row) => [row.name, row.email]));
    onRecipientsInput();
    textarea.focus();
  }

  function sync() {
    const problems = rows.filter((row) => row.issues.length).length;
    const ready = rows.length - problems;
    const first = rows.find((row) => !row.issues.length);
    const label = ready > 0 ? `Generate ${plural(ready, "certificate")}` : "Submit rows";

    paper.lines.heading.textContent = heading.input.value;
    paper.lines.intro.textContent = intro.input.value;
    paper.lines.name.textContent = first?.name ?? "Recipient name";
    paper.lines.statement.textContent = statement.input.value;
    paper.lines.title.textContent = title.input.value || "Event or course name";
    paper.lines.issuer.textContent = issuer.input.value ? `Issued by ${issuer.input.value}` : "Issued by";
    paper.lines.date.textContent = issueDate.input.value ? formatDate(issueDate.input.value) : "";

    summary.textContent = rows.length
      ? `${ready} of ${plural(rows.length, "row")} ready${problems ? ` · ${problems} need attention` : ""}${maxRecipients !== null && rows.length > maxRecipients ? ` · over the ${maxRecipients.toLocaleString()} row limit` : ""}`
      : "No recipients yet";
    submit.textContent = label;
    dialogSubmit.textContent = label;
    const overLimit = maxRecipients !== null && rows.length > maxRecipients;
    if (maxRecipients === null) {
      limitNote.textContent = "";
    } else if (overLimit) {
      limitNote.textContent = `${rows.length.toLocaleString()} rows is over the limit of ${maxRecipients.toLocaleString()} per job. Split the list into smaller jobs.`;
    } else {
      limitNote.textContent = `Up to ${maxRecipients.toLocaleString()} recipients per job.`;
    }
    limitNote.className = overLimit ? "hint issue" : "hint";
    submit.disabled = busy || rows.length === 0 || overLimit;
    dialogSubmit.disabled = submit.disabled;
    previewButton.disabled = busy || !first;

    if (rows.length === 0) {
      recipientPreview.replaceChildren(el("p", { class: "hint" }, "Rows appear here as you type or after you add a file."));
      return;
    }
    const overNote = overLimit
      ? el(
          "div",
          { class: "toolbar" },
          el("p", { class: "error" }, `This list has ${rows.length.toLocaleString()} rows but a job can include at most ${maxRecipients.toLocaleString()}. Trim the list or split it into several jobs.`),
          el("button", { class: "btn", type: "button", onclick: trimToLimit }, `Keep first ${maxRecipients.toLocaleString()} rows`),
        )
      : null;
    const note = problems
      ? el(
          "div",
          { class: "toolbar" },
          el("p", { class: "hint" }, "Rows that need attention are still submitted and will be listed as failed."),
          el("button", { class: "btn", type: "button", onclick: removeProblems }, "Remove problem rows"),
        )
      : null;
    recipientPreview.replaceChildren(...[overNote, note, ...recipientTable(rows)].filter(Boolean));
  }

  function releasePreview() {
    previewToken += 1;
    frame.src = "about:blank";
    frame.hidden = true;
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      previewUrl = null;
    }
  }

  async function openPreview() {
    errorBox.textContent = "";
    if (!root.querySelector("form").reportValidity()) {
      return;
    }
    const first = rows.find((row) => !row.issues.length);
    if (!first) {
      errorBox.textContent = "Add at least one valid recipient to preview a certificate.";
      return;
    }
    const token = ++previewToken;
    dialogName.textContent = `Preview for ${first.name}`;
    dialogStatus.textContent = "Rendering the preview";
    openLink.hidden = true;
    frame.hidden = true;
    dialog.showModal();
    try {
      const blob = await previewCertificate({ certificate: spec(), recipient_name: first.name });
      if (token !== previewToken) {
        return;
      }
      previewUrl = URL.createObjectURL(blob);
      frame.src = `${previewUrl}#toolbar=0&navpanes=0&view=Fit`;
      openLink.href = previewUrl;
      frame.hidden = false;
      openLink.hidden = false;
      dialogStatus.textContent = "";
    } catch (error) {
      if (token === previewToken) {
        dialogStatus.textContent = `Preview not available. ${describeError(error)}`;
      }
    }
  }

  function generateFromDialog() {
    dialog.close();
    submitJob();
  }

  async function submitJob() {
    if (busy || rows.length === 0) {
      return;
    }
    busy = true;
    sync();
    errorBox.textContent = "";
    try {
      const job = await createJob({
        certificate: spec(),
        recipients: rows.map(({ name, email }) => ({ name, email })),
      });
      location.hash = `#/jobs/${job.id}`;
    } catch (error) {
      errorBox.textContent = describeError(error);
      busy = false;
      sync();
    }
  }

  textarea.addEventListener("dragover", (event) => {
    event.preventDefault();
    textarea.classList.add("dragging");
  });
  textarea.addEventListener("dragleave", () => textarea.classList.remove("dragging"));
  textarea.addEventListener("drop", (event) => {
    event.preventDefault();
    textarea.classList.remove("dragging");
    readFile(event.dataTransfer.files[0]);
  });
  for (const input of [title.input, issuer.input, issueDate.input]) {
    input.addEventListener("input", sync);
  }
  for (const input of [heading.input, intro.input, statement.input]) {
    input.addEventListener("input", onWordingInput);
  }

  const form = el(
    "form",
    {
      class: "narrow",
      onsubmit: (event) => {
        event.preventDefault();
        submitJob();
      },
    },
    el(
      "section",
      { class: "panel" },
      el("h2", {}, "Certificate details"),
      el("div", { class: "fields" }, title.node, issuer.node, issueDate.node),
    ),
    el(
      "section",
      { class: "panel" },
      el("h2", {}, "Wording"),
      el(
        "div",
        { class: "wording" },
        el(
          "div",
          { class: "stack" },
          el("div", { class: "field" }, el("label", { for: "preset" }, "Style"), preset),
          heading.node,
          intro.node,
          statement.node,
        ),
        paper.node,
      ),
    ),
    el(
      "section",
      { class: "panel" },
      el("h2", {}, "Recipients"),
      el(
        "div",
        { class: "toolbar" },
        el("label", { for: "recipients" }, "One recipient per line: name, email"),
        el(
          "div",
          { class: "button-row" },
          el("a", { class: "link-button", href: SAMPLE_HREF, download: "recipients-sample.csv" }, "Sample CSV"),
          el("button", { class: "btn", type: "button", onclick: () => fileInput.click() }, "Upload CSV"),
          fileInput,
        ),
      ),
      textarea,
      el(
        "p",
        { class: "hint" },
        "Paste from a spreadsheet or drop a CSV onto the box. Names are drawn in a Latin-script font; other scripts, such as Devanagari, are not supported yet and will be listed as failed.",
      ),
      limitNote,
      recipientPreview,
    ),
    errorBox,
    el("div", { class: "action-bar" }, summary, el("div", { class: "button-row" }, previewButton, submit)),
  );

  root.append(
    el(
      "header",
      { class: "page-head narrow" },
      el("h1", { tabindex: "-1" }, "Issue certificates"),
      el("p", { class: "lede" }, "Set the wording once, add your recipients, check a preview, then generate. One bad row never blocks the rest."),
    ),
    form,
    dialog,
  );
  sync();
  getLimits()
    .then((limits) => {
      maxRecipients = limits.max_recipients;
      sync();
    })
    .catch(() => sync());
  return () => {
    releasePreview();
    dialog.close();
  };
}
