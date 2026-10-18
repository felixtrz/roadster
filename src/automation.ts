/**
 * Automation hooks (window.roadster, window.roadsterScene, window.roadsterFilmCamera, ...) drive the
 * film capture and verification tools. They are installed on the dev server, or in a production
 * build only when the page URL carries `?automation`, so a deployed page exposes nothing by default.
 */
export const AUTOMATION = import.meta.env.DEV || new URLSearchParams(window.location.search).has('automation');
