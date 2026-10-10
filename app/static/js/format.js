import { ApiError } from "./api.js";

export const JOB_STATUS = {
  PENDING: "Queued",
  PROCESSING: "Processing",
  COMPLETED: "Completed",
  COMPLETED_WITH_ERRORS: "Completed with errors",
  FAILED: "Failed",
};

export const CERTIFICATE_STATUS = {
  PENDING: "Queued",
  PROCESSING: "Processing",
  SUCCEEDED: "Generated",
  FAILED: "Failed",
};

const FAILURES = {
  INVALID_NAME: "Name is missing or longer than 100 characters",
  INVALID_EMAIL: "Email is missing or not valid",
  RENDER_ERROR: "Certificate could not be generated",
  STORAGE_ERROR: "Certificate could not be saved",
};

const dateTime = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
const dateOnly = new Intl.DateTimeFormat(undefined, { dateStyle: "long" });

export function failureMessage(error) {
  return error ? (FAILURES[error.code] ?? error.message) : "";
}

export function plural(count, noun) {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

export function formatDateTime(iso) {
  return dateTime.format(new Date(iso));
}

export function formatDate(isoDate) {
  const [year, month, day] = isoDate.split("-").map(Number);
  return dateOnly.format(new Date(year, month - 1, day));
}

export function describeError(error) {
  if (!(error instanceof ApiError)) {
    return "Cannot reach the server. Check your connection and try again.";
  }
  const first = error.details?.errors?.[0];
  return first ? `${error.message}. ${first.location.slice(1).join(".")}: ${first.message}` : error.message;
}
