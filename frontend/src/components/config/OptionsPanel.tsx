import { Settings2 } from "lucide-react";
import { useLocale } from "../../i18n";

interface OptionsPanelProps {
  canvasFormat: string;
  languageMode: "zh" | "en" | "custom";
  customLanguage: string;
  numPages: string;
  detailLevel: string;
  timeoutSeconds: string;
  instruction: string;
  onCanvasFormatChange: (value: string) => void;
  onLanguageModeChange: (value: "zh" | "en" | "custom") => void;
  onCustomLanguageChange: (value: string) => void;
  onNumPagesChange: (value: string) => void;
  onDetailLevelChange: (value: string) => void;
  onTimeoutSecondsChange: (value: string) => void;
  onInstructionChange: (value: string) => void;
}

export function OptionsPanel(props: OptionsPanelProps) {
  const { t } = useLocale();
  return (
    <section className="panel">
      <div className="panel-title-row" style={{ marginBottom: "0.75rem" }}>
        <Settings2 size={15} className="panel-title-icon" />
        <p className="panel-title">{t("options.title")}</p>
      </div>
      <div className="options-grid">
        <label className="form-field">
          <span>{t("options.canvas")}</span>
          <select value={props.canvasFormat} onChange={(event) => props.onCanvasFormatChange(event.target.value)}>
            <option value="ppt169">{t("options.canvas169")}</option>
            <option value="ppt43">{t("options.canvas43")}</option>
          </select>
        </label>
        <label className="form-field">
          <span>{t("options.language")}</span>
          <select
            value={props.languageMode}
            onChange={(event) =>
              props.onLanguageModeChange(event.target.value as "zh" | "en" | "custom")
            }
          >
            <option value="zh">{t("options.languageZh")}</option>
            <option value="en">{t("options.languageEn")}</option>
            <option value="custom">{t("options.languageCustom")}</option>
          </select>
          {props.languageMode === "custom" ? (
            <input
              type="text"
              value={props.customLanguage}
              onChange={(event) => props.onCustomLanguageChange(event.target.value)}
              placeholder={t("options.languageCustomPlaceholder")}
            />
          ) : null}
        </label>
        <label className="form-field">
          <span>{t("options.pages")}</span>
          <input
            type="number"
            min="0"
            value={props.numPages}
            onChange={(event) => props.onNumPagesChange(event.target.value)}
            placeholder={t("options.auto")}
          />
        </label>
        <label className="form-field">
          <span>{t("options.detailLevel")}</span>
          <select value={props.detailLevel} onChange={(event) => props.onDetailLevelChange(event.target.value)}>
            <option value="normal">{t("options.detailNormal")}</option>
            <option value="high">{t("options.detailHigh")}</option>
            <option value="very_high">{t("options.detailVeryHigh")}</option>
          </select>
        </label>
        <label className="form-field">
          <span>{t("options.timeout")}</span>
          <input
            type="number"
            min="1"
            value={props.timeoutSeconds}
            onChange={(event) => props.onTimeoutSecondsChange(event.target.value)}
            placeholder={t("options.timeoutPlaceholder")}
          />
        </label>
      </div>
      <label className="form-field">
        <span>{t("options.instruction")}</span>
        <textarea
          rows={4}
          value={props.instruction}
          onChange={(event) => props.onInstructionChange(event.target.value)}
          placeholder={t("options.instructionPlaceholder")}
        />
      </label>
    </section>
  );
}
