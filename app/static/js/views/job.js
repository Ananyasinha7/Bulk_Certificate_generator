import { ApiError, getJob, listCertificates, zipUrl } from "../api.js";
import { toCsv } from "../csv.js";
import { el } from "../dom.js";
import {
  CERTIFICATE_STATUS,
  JOB_STATUS,
  describeError,
  failureMessage,
  formatDate,
  plural,
} from "../format.js";

const PAGE_SIZE = 50;
const EXPORT_PAGE_SIZE = 100;
const POLL_MS = 1000;
const ACTIVE = new Set(["PENDING", "PROCESSING"]);
const FILTERS = [
  ["", "All"],
  ["SUCCEEDED", "Generated"],
  ["FAILED", "Failed"],
  ["PENDING", "Queued"],
];

function badgeClass(status) {
  if (status === "COMPLETED" || status === "SUCCEEDED") {
    return "badge badge-ok";
  }
  if (status === "FAILED" || status === "COMPLETED_WITH_ERRORS") {
    return "badge badge-bad";
  }
  return "badge";
}

function saveFile(content, filename) {
  const url = URL.createObjectURL(new Blob([content], { type: "text/csv" }));
  const link = el("a", { href: url, download: filename });
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function rowFor(item) {
  let result = null;
  if (item.status === "SUCCEEDED") {
    result = el("a", { href: item.download_url, download: "" }, "Download PDF");
  } else if (item.status === "FAILED") {
    result = el("span", { class: "reason" }, failureMessage(item.error));
  }
  return el(
    "tr",
    {},
    el("td", { class: "num" }, String(item.row_index + 1)),
    el(
      "td",
      { class: "person" },
      el("span", {}, item.recipient_name || "(no name)"),
      el("span", { class: "email" }, item.recipient_email || "(no email)"),
    ),
    el("td", {}, el("span", { class: badgeClass(item.status) }, CERTIFICATE_STATUS[item.status])),
    el("td", {}, result),
  );
}

export function renderJob(root, jobId) {
  const state = { job: null, data: null, filter: "", page: 1, missing: false, failure: "", sequence: 0 };
  let timer = null;
  let stopped = false;

  const heading = el("h1", { tabindex: "-1" }, "Loading job");
  const meta = el("p", { class: "meta" });
  const badge = el("span", { class: "badge" });
  const counts = el("dl", { class: "stats" });
  const bar = el("div", { class: "bar" });
  const track = el(
    "div",
    { class: "track", role: "progressbar", "aria-label": "Certificates processed", "aria-valuemin": "0", "aria-valuemax": "100" },
    bar,
  );
  const percent = el("p", { class: "percent" });
  const zip = el("a", { class: "btn btn-primary", download: "" }, "Download all as ZIP");
  const exportButton = el("button", { class: "btn", type: "button", onclick: exportFailed, hidden: true }, "Export failed rows as CSV");
  const announce = el("p", { class: "sr-only", "aria-live": "polite" });
  const noticeText = el("span");
  const notice = el(
    "div",
    { class: "notice", role: "alert", hidden: true },
    noticeText,
    el("button", { class: "btn", type: "button", onclick: refresh }, "Retry now"),
  );
  const filterButtons = FILTERS.map(([value, label]) =>
    el("button", { class: "segment", type: "button", "aria-pressed": String(value === ""), onclick: () => setFilter(value) }, label),
  );
  const body = el("tbody");
  const pagerText = el("p", { class: "pager-text" });
  const previous = el("button", { class: "btn", type: "button", onclick: () => setPage(state.page - 1) }, "Previous");
  const next = el("button", { class: "btn", type: "button", onclick: () => setPage(state.page + 1) }, "Next");

  const content = el(
    "div",
    { class: "page-head" },
    el("section", { class: "status" }, el("div", { class: "status-line" }, badge), counts, track, percent, el("div", { class: "button-row" }, zip, exportButton)),
    el(
      "section",
      { class: "panel" },
      el("div", { class: "segmented", role: "group", "aria-label": "Filter certificates" }, filterButtons),
      el(
        "div",
        { class: "table-wrap" },
        el(
          "table",
          { class: "results" },
          el(
            "thead",
            {},
            el(
              "tr",
              {},
              el("th", { scope: "col" }, "Row"),
              el("th", { scope: "col" }, "Recipient"),
              el("th", { scope: "col" }, "Status"),
              el("th", { scope: "col" }, "Result"),
            ),
          ),
          body,
        ),
      ),
      el("div", { class: "pager" }, pagerText, el("div", { class: "button-row" }, previous, next)),
    ),
  );

  root.append(el("a", { class: "back", href: "#/jobs" }, "All jobs"), el("header", { class: "page-head" }, heading, meta), notice, content, announce);

  function render() {
    notice.hidden = !state.failure;
    noticeText.textContent = state.failure;
    if (state.missing) {
      heading.textContent = "Job not found";
      meta.textContent = "This job does not exist on the server.";
      content.hidden = true;
      return;
    }
    const { job, data } = state;
    if (!job) {
      return;
    }
    document.title = `${job.title} - Certificate Issuer`;
    heading.textContent = job.title;
    meta.textContent = `${job.issuer} · ${formatDate(job.issue_date)} · ${plural(job.total, "recipient")}`;
    badge.className = badgeClass(job.status);
    badge.textContent = JOB_STATUS[job.status];
    const { succeeded, failed, pending } = job.counts;
    counts.replaceChildren(
      ...[
        ["Generated", succeeded],
        ["Failed", failed],
        ["Queued", pending],
      ].map(([label, value]) => el("div", { class: "stat" }, el("dt", {}, label), el("dd", {}, String(value)))),
    );
    const active = ACTIVE.has(job.status);
    bar.style.width = `${job.progress_percent}%`;
    track.setAttribute("aria-valuenow", String(job.progress_percent));
    percent.textContent = `${job.progress_percent.toFixed(1)}% processed${active ? " · the ZIP is available once processing finishes" : ""}`;
    const downloadable = !active && succeeded > 0;
    if (downloadable) {
      zip.setAttribute("href", zipUrl(jobId));
      zip.removeAttribute("aria-disabled");
    } else {
      zip.removeAttribute("href");
      zip.setAttribute("aria-disabled", "true");
    }
    exportButton.hidden = failed === 0;
    filterButtons.forEach((button, index) => button.setAttribute("aria-pressed", String(FILTERS[index][0] === state.filter)));
    const items = data?.items ?? [];
    const message = data ? "No certificates match this filter." : "Loading certificates";
    body.replaceChildren(...(items.length ? items.map(rowFor) : [el("tr", {}, el("td", { class: "empty", colspan: "4" }, message))]));
    const total = data?.total ?? 0;
    const start = total ? (state.page - 1) * PAGE_SIZE + 1 : 0;
    const end = Math.min(state.page * PAGE_SIZE, total);
    pagerText.textContent = total ? `${start}-${end} of ${total}` : "";
    previous.disabled = state.page <= 1;
    next.disabled = end >= total;
  }

  async function refresh() {
    clearTimeout(timer);
    const sequence = ++state.sequence;
    try {
      const [job, data] = await Promise.all([
        getJob(jobId),
        listCertificates(jobId, { status: state.filter, page: state.page, pageSize: PAGE_SIZE }),
      ]);
      if (stopped || sequence !== state.sequence) {
        return;
      }
      if (state.job?.status !== job.status) {
        announce.textContent = `Job status: ${JOB_STATUS[job.status]}`;
      }
      Object.assign(state, { job, data, failure: "" });
    } catch (error) {
      if (stopped || sequence !== state.sequence) {
        return;
      }
      if (error instanceof ApiError && error.status === 404) {
        state.missing = true;
      } else {
        state.failure = `${describeError(error)} Showing the last data received.`;
      }
    }
    render();
    if (!state.missing && (!state.job || ACTIVE.has(state.job.status))) {
      timer = setTimeout(refresh, POLL_MS);
    }
  }

  function setFilter(value) {
    state.filter = value;
    state.page = 1;
    refresh();
  }

  function setPage(page) {
    state.page = page;
    refresh();
  }

  async function exportFailed() {
    exportButton.disabled = true;
    try {
      const table = [["name", "email", "reason"]];
      let total = Infinity;
      for (let page = 1; table.length - 1 < total; page += 1) {
        const data = await listCertificates(jobId, { status: "FAILED", page, pageSize: EXPORT_PAGE_SIZE });
        table.push(...data.items.map((item) => [item.recipient_name, item.recipient_email, failureMessage(item.error)]));
        total = data.total;
      }
      saveFile(toCsv(table), "failed-rows.csv");
    } catch (error) {
      state.failure = describeError(error);
      render();
    } finally {
      exportButton.disabled = false;
    }
  }

  refresh();
  return () => {
    stopped = true;
    clearTimeout(timer);
  };
}
