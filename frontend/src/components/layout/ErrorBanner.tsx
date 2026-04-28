import { useEffect, useMemo, useState } from "react";
import { AlertOctagon, Copy, Check, X, ChevronDown, ChevronUp } from "lucide-react";
import { useGeneration } from "../../hooks/useGeneration";
import { useLocale } from "../../i18n";

/**
 * Floating, full-width error banner.
 *
 * Shown whenever the global ``useGeneration().error`` is set. Sits at the
 * top of the viewport (sticky / fixed) so the user cannot miss it the
 * way they could miss the small red `<p>` previously appended below the
 * "Start generating" button.
 *
 * Long error messages (e.g. multi-line stack traces from the backend
 * critic / pipeline) are truncated to a 3-line preview by default with a
 * one-click expand. A copy-to-clipboard control is provided so the user
 * can paste the full error into a bug report without scrolling.
 */
export function ErrorBanner() {
  const error = useGeneration((state) => state.error);
  const dismissError = useGeneration((state) => state.dismissError);
  const { t } = useLocale();
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  // Reset transient UI state whenever a new error replaces a previous one.
  useEffect(() => {
    setExpanded(false);
    setCopied(false);
  }, [error]);

  const isMultiline = useMemo(
    () => Boolean(error && (error.includes("\n") || error.length > 160)),
    [error],
  );

  if (!error) return null;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(error);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      // Clipboard may be blocked (e.g. http-only context). Silently no-op:
      // the message is still visible inside the banner so the user can
      // select it manually.
    }
  };

  return (
    <div className="error-banner" role="alert" aria-live="assertive">
      <div className="error-banner-inner">
        <AlertOctagon size={20} className="error-banner-icon" aria-hidden />
        <div className="error-banner-body">
          <div className="error-banner-title">{t("error.title")}</div>
          <pre
            className={`error-banner-message${expanded ? " error-banner-message-expanded" : ""}`}
          >
            {error}
          </pre>
        </div>
        <div className="error-banner-actions">
          {isMultiline ? (
            <button
              type="button"
              className="error-banner-action"
              onClick={() => setExpanded((v) => !v)}
              aria-label={expanded ? t("error.collapse") : t("error.expand")}
              title={expanded ? t("error.collapse") : t("error.expand")}
            >
              {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              <span>{expanded ? t("error.collapse") : t("error.expand")}</span>
            </button>
          ) : null}
          <button
            type="button"
            className="error-banner-action"
            onClick={handleCopy}
            aria-label={t("error.copy")}
            title={t("error.copy")}
          >
            {copied ? <Check size={16} /> : <Copy size={16} />}
            <span>{copied ? t("error.copied") : t("error.copy")}</span>
          </button>
          <button
            type="button"
            className="error-banner-close"
            onClick={dismissError}
            aria-label={t("error.dismiss")}
            title={t("error.dismiss")}
          >
            <X size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}
