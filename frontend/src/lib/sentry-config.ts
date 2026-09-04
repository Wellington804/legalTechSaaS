import type { ErrorEvent } from "@sentry/nextjs";

const REDACTIONS: Array<[RegExp, string]> = [
  [/Bearer\s+[A-Za-z0-9._~-]+/gi, "Bearer [redacted]"],
  [/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "[email]"],
  [/\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b/g, "[cpf]"],
  [/\+?\d[\d\s().-]{8,}\d/g, "[phone]"],
];

function redact(value?: string | null) {
  if (!value) return value;
  return REDACTIONS.reduce((result, [pattern, replacement]) => result.replace(pattern, replacement), value);
}

export function scrubSentryEvent(event: ErrorEvent): ErrorEvent {
  event.breadcrumbs = undefined;
  event.contexts = undefined;
  event.extra = undefined;
  event.tags = undefined;
  if (event.request) {
    event.request.cookies = undefined;
    event.request.data = undefined;
    event.request.query_string = undefined;
    event.request.headers = undefined;
    if (event.request.url) {
      try {
        const url = new URL(event.request.url);
        if (!['http:', 'https:'].includes(url.protocol)) throw new Error('Invalid request URL');
        url.username = "";
        url.password = "";
        url.search = "";
        url.hash = "";
        event.request.url = url.toString();
      } catch {
        event.request.url = undefined;
      }
    }
  }
  if (event.user) event.user = event.user.id ? { id: String(event.user.id) } : undefined;
  if (event.message) event.message = redact(event.message) || undefined;
  event.exception?.values?.forEach((exception) => {
    exception.value = redact(exception.value) || undefined;
    exception.stacktrace?.frames?.forEach((frame) => {
      frame.vars = undefined;
    });
  });
  return event;
}
