import { useLocale } from "../../i18n";
import { GraduationCap, BarChart3, Code2, Layout, CheckCircle2, Palette } from "lucide-react";
import type { ComponentType } from "react";

const STYLE_ICONS: Record<string, ComponentType<{ size?: number; strokeWidth?: number; color?: string }>> = {
  academic: GraduationCap,
  consulting: BarChart3,
  tech: Code2,
  general: Layout,
};

interface StylePickerProps {
  value: string;
  onChange: (value: string) => void;
}

export function StylePicker({ value, onChange }: StylePickerProps) {
  const { t } = useLocale();
  const styles = [
    { id: "academic", title: t("style.academic.title"), description: t("style.academic.body") },
    { id: "consulting", title: t("style.consulting.title"), description: t("style.consulting.body") },
    { id: "tech", title: t("style.tech.title"), description: t("style.tech.body") },
    { id: "general", title: t("style.general.title"), description: t("style.general.body") },
  ];

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
    </section>
  );
}
