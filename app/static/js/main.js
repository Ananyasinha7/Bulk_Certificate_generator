import { renderJob } from "./views/job.js";
import { renderJobs } from "./views/jobs.js";
import { renderNewJob } from "./views/new-job.js";

const JOB_ROUTE = /^#\/jobs\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/i;
const root = document.getElementById("view");
let dispose = () => {};

function resolve(hash) {
  const job = hash.match(JOB_ROUTE);
  if (job) {
    return { section: "jobs", render: () => renderJob(root, job[1]) };
  }
  if (hash === "#/jobs") {
    return { section: "jobs", render: () => renderJobs(root) };
  }
  return { section: "new", render: () => renderNewJob(root) };
}

function route() {
  dispose();
  root.replaceChildren();
  const { section, render } = resolve(location.hash);
  dispose = render();
  for (const link of document.querySelectorAll("[data-nav]")) {
    if (link.dataset.nav === section) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  }
  window.scrollTo(0, 0);
  root.querySelector("h1")?.focus();
}

window.addEventListener("hashchange", route);
route();
