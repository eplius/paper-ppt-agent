import { Settings2 } from "lucide-react";
import { useLocale } from "../../i18n";

interface OptionsPanelProps {
  canvasFormat: string;
  language: string;
  numPages: string;
  detailLevel: string;
  instruction: string;
  onCanvasFormatChange: (value: string) => void;
  onLanguageChange: (value: string) => void;
  onNumPagesChange: (value: string) => void;
  onDetailLevelChange: (value: string) => void;
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
          <select value={props.language} onChange={(event) => props.onLanguageChange(event.target.value)}>
            <option value="zh">{t("options.languageZh")}</option>
            <option value="en">{t("options.languageEn")}</option>
            <option value="bilingual">{t("options.languageBilingual")}</option>
          </select>
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
