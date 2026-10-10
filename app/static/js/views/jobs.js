import { ApiError, listJobs } from "../api.js";
import { el } from "../dom.js";
import { JOB_STATUS, describeError, formatDateTime, plural } from "../format.js";

const PAGE_SIZE = 20;
const POLL_MS = 2000;
const ACTIVE = new Set(["PENDING", "PROCESSING"]);

function badgeClass(status) {
  if (status === "COMPLETED") {
    return "badge badge-ok";
  }
  if (status === "FAILED" || status === "COMPLETED_WITH_ERRORS") {
    return "badge badge-bad";
  }
  return "badge";
}

function rowFor(job) {
  const finished = job.counts.succeeded + job.counts.failed;
  return el(
    "tr",
    {},
    el(
      "td",
      { class: "person" },
      el("a", { href: `#/jobs/${job.id}` }, job.title),
      el("span", { class: "email" }, `${job.issuer} · ${plural(job.total, "recipient")}`),
    ),
    el("td", {}, el("span", { class: badgeClass(job.status) }, JOB_STATUS[job.status])),
    el(
      "td",
      { class: "progress-cell" },
      el("div", { class: "mini-track" }, el("div", { class: "mini-bar", style: `width:${job.progress_percent}%` })),
      el("span", { class: "email" }, `${finished} of ${job.total}${job.counts.failed ? ` · ${job.counts.failed} failed` : ""}`),
    ),
    el("td", { class: "when" }, formatDateTime(job.created_at)),
  );
}

export function renderJobs(root) {
  document.title = "Jobs - Certificate Issuer";
  const state = { page: 1, data: null, failure: "", sequence: 0 };
  let timer = null;
  let stopped = false;

  const notice = el("div", { class: "notice", role: "alert", hidden: true });
  const body = el("tbody");
  const tableWrap = el(
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
          el("th", { scope: "col" }, "Event"),
          el("th", { scope: "col" }, "Status"),
          el("th", { scope: "col" }, "Progress"),
          el("th", { scope: "col" }, "Created"),
        ),
      ),
      body,
    ),
  );
  const empty = el(
    "div",
    { class: "empty-state", hidden: true },
    el("h2", {}, "No jobs yet"),
    el("p", { class: "hint" }, "Jobs you create appear here, whether they come from this page or from the API."),
    el("a", { class: "btn btn-primary", href: "#/" }, "Issue certificates"),
  );
  const pagerText = el("p", { class: "pager-text" });
  const previous = el("button", { class: "btn", type: "button", onclick: () => go(state.page - 1) }, "Previous");
  const next = el("button", { class: "btn", type: "button", onclick: () => go(state.page + 1) }, "Next");
  const pager = el("div", { class: "pager" }, pagerText, el("div", { class: "button-row" }, previous, next));

  root.append(
    el(
      "header",
      { class: "page-head" },
      el("h1", { tabindex: "-1" }, "Jobs"),
      el("p", { class: "lede" }, "Every certificate job on this server, newest first."),
    ),
    notice,
    tableWrap,
    empty,
    pager,
  );

  function render() {
    notice.hidden = !state.failure;
    notice.textContent = state.failure;
    const { data } = state;
    if (!data) {
      return;
    }
    const isEmpty = data.total === 0;
    empty.hidden = !isEmpty;
    tableWrap.hidden = isEmpty;
    pager.hidden = isEmpty;
    body.replaceChildren(...data.items.map(rowFor));
    const start = (data.page - 1) * data.page_size + 1;
    const end = Math.min(data.page * data.page_size, data.total);
    pagerText.textContent = `${start}-${end} of ${data.total}`;
    previous.disabled = data.page <= 1;
    next.disabled = end >= data.total;
  }

  async function refresh() {
    clearTimeout(timer);
    const sequence = ++state.sequence;
    try {
      const data = await listJobs({ page: state.page, pageSize: PAGE_SIZE });
      if (stopped || sequence !== state.sequence) {
        return;
      }
      Object.assign(state, { data, failure: "" });
    } catch (error) {
      if (stopped || sequence !== state.sequence) {
        return;
      }
      state.failure = error instanceof ApiError ? error.message : describeError(error);
    }
    render();
    const active = state.data?.items.some((job) => ACTIVE.has(job.status));
    if (active || state.failure) {
      timer = setTimeout(refresh, POLL_MS);
    }
  }

  function go(page) {
    state.page = page;
    refresh();
  }

  tableWrap.hidden = true;
  pager.hidden = true;
  refresh();
  return () => {
    stopped = true;
    clearTimeout(timer);
  };
}
