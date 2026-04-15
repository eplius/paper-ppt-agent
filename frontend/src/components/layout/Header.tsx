import { Link, useLocation } from "react-router-dom";
import { useLocale } from "../../i18n";
import { useTheme } from "../../hooks/useTheme";
import { FileText, Sparkles, Home, Layers, Sun, Moon, Languages } from "lucide-react";

export function Header() {
  const { theme, toggleTheme } = useTheme();
  const { locale, toggleLocale, t } = useLocale();
  const location = useLocation();

  return (
    <header className="app-header">
      <div className="header-brand">
        <Link to="/" className="brand-mark">
          <span className="brand-kicker" style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
            <Sparkles size={12} />
            {t("header.kicker")}
          </span>
          <span className="brand-name" style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <FileText size={20} />
            Paper PPT Agent
          </span>
        </Link>
      </div>
      <div className="header-actions">
        <Link
          to="/"
          className={`nav-chip ${location.pathname === "/" ? "nav-chip-active" : ""}`}
          style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}
        >
          <Home size={14} />
          {t("nav.home")}
        </Link>
        <Link
          to="/generate"
          className={`nav-chip ${location.pathname === "/generate" ? "nav-chip-active" : ""}`}
          style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}
        >
          <Layers size={14} />
          {t("nav.studio")}
        </Link>
        <button
          className="icon-btn"
          onClick={toggleLocale}
          type="button"
          title={locale === "en" ? t("locale.zh") : t("locale.en")}
        >
          <Languages size={16} />
        </button>
        <button
          className="icon-btn"
          onClick={toggleTheme}
          type="button"
          title={theme === "light" ? t("theme.dark") : t("theme.light")}
        >
          {theme === "light" ? <Moon size={16} /> : <Sun size={16} />}
        </button>
      </div>
    </header>
  );
}
