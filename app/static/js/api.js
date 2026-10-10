const BASE = "/api/v1";

export class ApiError extends Error {
  constructor(status, code, message, details) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function send(path, options) {
  const response = await fetch(BASE + path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const error = body?.error;
    throw new ApiError(
      response.status,
      error?.code ?? "UNKNOWN",
      error?.message ?? response.statusText,
      error?.details ?? {},
    );
  }
  return response;
}

function postJson(path, payload) {
  return send(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function createJob(payload) {
  return (await postJson("/certificate-jobs", payload)).json();
}

export async function previewCertificate(payload) {
  return (await postJson("/certificate-previews", payload)).blob();
}

export async function getLimits() {
  return (await send("/limits")).json();
}

export async function listJobs({ page, pageSize }) {
  const query = new URLSearchParams({ page, page_size: pageSize });
  return (await send(`/certificate-jobs?${query}`)).json();
}

export async function getJob(jobId) {
  return (await send(`/certificate-jobs/${jobId}`)).json();
}

export async function listCertificates(jobId, { status, page, pageSize }) {
  const query = new URLSearchParams({ page, page_size: pageSize });
  if (status) {
    query.set("status", status);
  }
  return (await send(`/certificate-jobs/${jobId}/certificates?${query}`)).json();
}

export function zipUrl(jobId) {
  return `${BASE}/certificate-jobs/${jobId}/download`;
}
