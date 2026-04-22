import { useLocale } from "../../i18n";
import { GraduationCap, BarChart3, Code2, Layout, CheckCircle2, Palette, Sparkles } from "lucide-react";
import type { ComponentType } from "react";

export interface StyleOverrides {
  palette?: string[];        // e.g. ["#0b1220", "#ff8a3d", "#ffffff"]
  font?: string;             // e.g. "Inter, \"Source Han Sans\", sans-serif"
  density?: "compact" | "normal" | "spacious";
}

const STYLE_ICONS: Record<string, ComponentType<{ size?: number; strokeWidth?: number; color?: string }>> = {
  academic: GraduationCap,
  consulting: BarChart3,
  tech: Code2,
  general: Layout,
  custom: Sparkles,
};

interface StylePickerProps {
  value: string;
  onChange: (value: string) => void;
  overrides?: StyleOverrides;
  onOverridesChange?: (next: StyleOverrides) => void;
}

export function StylePicker({ value, onChange, overrides, onOverridesChange }: StylePickerProps) {
  const { t } = useLocale();
  const styles = [
    { id: "academic", title: t("style.academic.title"), description: t("style.academic.body") },
    { id: "consulting", title: t("style.consulting.title"), description: t("style.consulting.body") },
    { id: "tech", title: t("style.tech.title"), description: t("style.tech.body") },
    { id: "general", title: t("style.general.title"), description: t("style.general.body") },
    { id: "custom", title: t("style.custom.title"), description: t("style.custom.body") },
  ];

  const ov: StyleOverrides = overrides ?? {};
  const palette = ov.palette && ov.palette.length >= 3 ? ov.palette : ["#0b1220", "#ff8a3d", "#f5f7fb"];

  const patchOverrides = (patch: Partial<StyleOverrides>) => {
    onOverridesChange?.({ ...ov, ...patch });
  };

  const showCustomPanel = value === "custom" || Boolean(onOverridesChange);

  return (
    <section className="panel">
      <div className="panel-title-row" style={{ marginBottom: "0.75rem" }}>
        <Palette size={15} className="panel-title-icon" />
        <p className="panel-title">{t("style.title")}</p>
      </div>
      <div className="style-grid">
        {styles.map((style) => {
          const Icon = STYLE_ICONS[style.id];
          const isActive = value === style.id;
          return (
            <button
              key={style.id}
              type="button"
              className={`style-card ${isActive ? "style-card-active" : ""}`}
              onClick={() => onChange(style.id)}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <Icon size={18} strokeWidth={1.5} color={isActive ? "var(--accent)" : "var(--muted)"} />
                {isActive && <CheckCircle2 size={14} color="var(--accent)" />}
              </div>
              <strong>{style.title}</strong>
              <span>{style.description}</span>
            </button>
          );
        })}
      </div>

      {showCustomPanel ? (
        <div className="style-custom-panel">
          <label>
            {t("style.customPalette")}
            <div className="style-palette-row">
              {palette.map((color, i) => (
                <input
                  key={i}
                  type="color"
                  value={color}
                  onChange={(e) => {
                    const next = [...palette];
                    next[i] = e.target.value;
                    patchOverrides({ palette: next });
                  }}
                />
              ))}
            </div>
          </label>
          <label>
            {t("style.customFont")}
            <input
              type="text"
              placeholder='Inter, "Source Han Sans", sans-serif'
              value={ov.font ?? ""}
              onChange={(e) => patchOverrides({ font: e.target.value })}
            />
          </label>
          <label>
            {t("style.customDensity")}
            <select
              value={ov.density ?? "normal"}
              onChange={(e) =>
                patchOverrides({ density: e.target.value as StyleOverrides["density"] })
              }
            >
              <option value="compact">{t("style.densityCompact")}</option>
              <option value="normal">{t("style.densityNormal")}</option>
              <option value="spacious">{t("style.densitySpacious")}</option>
            </select>
          </label>
        </div>
      ) : null}
    </section>
  );
}
