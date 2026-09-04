export type ThemePreference = "light" | "dark" | "system";

export const THEME_STORAGE_KEY = "lexflow-theme";
export const THEME_CHANGE_EVENT = "lexflow:theme-change";

export function isThemePreference(value: unknown): value is ThemePreference {
  return value === "light" || value === "dark" || value === "system";
}

export function getThemePreference(): ThemePreference {
  if (typeof window === "undefined") return "system";
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isThemePreference(stored) ? stored : "system";
  } catch {
    return "system";
  }
}

export function setThemePreference(preference: ThemePreference) {
  try { window.localStorage.setItem(THEME_STORAGE_KEY, preference); } catch { /* Apply for this tab even when storage is unavailable. */ }
  window.dispatchEvent(new CustomEvent(THEME_CHANGE_EVENT, { detail: preference }));
}

// Runs before React paints so a stored light preference does not flash dark.
export const themeInitializationScript = `(() => {
  const key = ${JSON.stringify(THEME_STORAGE_KEY)};
  const eventName = ${JSON.stringify(THEME_CHANGE_EVENT)};
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  const valid = value => value === 'light' || value === 'dark' || value === 'system';
  const read = () => { try { const value = localStorage.getItem(key); return valid(value) ? value : 'system'; } catch { return 'system'; } };
  const apply = preference => {
    const selected = valid(preference) ? preference : read();
    const resolved = selected === 'system' ? (media.matches ? 'dark' : 'light') : selected;
    const root = document.documentElement;
    root.classList.remove('light', 'dark');
    root.classList.add(resolved);
    root.dataset.theme = selected;
    root.style.colorScheme = resolved;
    const themeColor = document.querySelector('meta[name="theme-color"]');
    if (themeColor) themeColor.setAttribute('content', resolved === 'dark' ? '#09090b' : '#fafafa');
  };
  apply(read());
  media.addEventListener('change', () => { if (read() === 'system') apply('system'); });
  window.addEventListener('storage', event => { if (event.key === key) apply(read()); });
  window.addEventListener(eventName, event => apply(event.detail));
})();`;
