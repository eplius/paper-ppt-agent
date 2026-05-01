import { useState } from "react";
import type { DeepSeekSettings, OpenAISettings, ProviderListItem } from "../../lib/types";
import { useLocale } from "../../i18n";
import { Bot, Cpu, Zap, Globe, Key, Eye, EyeOff, BrainCircuit } from "lucide-react";

interface ModelSelectorProps {
  providers: ProviderListItem[];
  provider: string;
  model: string;
  baseUrl: string;
  apiKey: string;
  deepSeekSettings: DeepSeekSettings;
  openAISettings: OpenAISettings;
  onProviderChange: (provider: string) => void;
  onModelChange: (model: string) => void;
  onBaseUrlChange: (baseUrl: string) => void;
  onApiKeyChange: (apiKey: string) => void;
  onDeepSeekSettingsChange: (settings: DeepSeekSettings) => void;
  onOpenAISettingsChange: (settings: OpenAISettings) => void;
}

export function ModelSelector({
  providers,
  provider,
  model,
  baseUrl,
  apiKey,
  deepSeekSettings,
  openAISettings,
  onProviderChange,
  onModelChange,
  onBaseUrlChange,
  onApiKeyChange,
  onDeepSeekSettingsChange,
  onOpenAISettingsChange,
}: ModelSelectorProps) {
  const selectedProvider = providers.find((item) => item.name === provider);
  const { t } = useLocale();
  const datalistId = `model-options-${provider || "default"}`;
  const [showKey, setShowKey] = useState(false);
  const isDeepSeek = provider === "deepseek";
  const showOpenAISettings = provider === "openai" && isGpt5OrNewer(model);

  return (
    <section className="panel">
      <div className="panel-header-row">
        <div>
          <div className="panel-title-row">
            <Bot size={15} className="panel-title-icon" />
            <p className="panel-title">{t("model.title")}</p>
          </div>
          <p className="panel-support-text">{selectedProvider?.display_name ?? t("model.waiting")}</p>
        </div>
      </div>

      <label className="form-field">
        <span>{t("model.provider")}</span>
        <div className="form-field-icon">
          <Cpu size={14} className="field-icon" />
          <select value={provider} onChange={(event) => onProviderChange(event.target.value)}>
            {providers.map((item) => (
              <option key={item.name} value={item.name}>
                {item.display_name}
              </option>
            ))}
          </select>
        </div>
      </label>

      <label className="form-field">
        <span>{t("model.model")}</span>
        <div className="form-field-icon">
          <Zap size={14} className="field-icon" />
          <input
            list={datalistId}
            value={model}
            placeholder={t("model.modelPlaceholder")}
            onChange={(event) => onModelChange(event.target.value)}
          />
        </div>
        <datalist id={datalistId}>
          {selectedProvider?.models.map((item) => (
            <option key={item.id} value={item.id}>
              {item.display_name}
            </option>
          ))}
        </datalist>
      </label>

      <label className="form-field">
        <span>{t("model.baseUrl")}</span>
        <div className="form-field-icon">
          <Globe size={14} className="field-icon" />
          <input
            type="url"
            placeholder={t("model.baseUrlPlaceholder")}
            value={baseUrl}
            onChange={(event) => onBaseUrlChange(event.target.value)}
          />
        </div>
      </label>

      <label className="form-field">
        <span>{t("model.apiKey")}</span>
        <div className="form-field-icon api-key-wrapper">
          <Key size={14} className="field-icon" />
          <input
            type={showKey ? "text" : "password"}
            placeholder={t("model.apiPlaceholder")}
            value={apiKey}
            onChange={(event) => onApiKeyChange(event.target.value)}
          />
          <button
            type="button"
            className="api-key-toggle"
            onClick={() => setShowKey((v) => !v)}
            tabIndex={-1}
          >
            {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
        </div>
      </label>

      {isDeepSeek ? (
        <div className="deepseek-settings">
          <div className="panel-title-row">
            <BrainCircuit size={15} className="panel-title-icon" />
            <p className="panel-title">{t("model.deepseekTitle")}</p>
          </div>
          <p className="panel-support-text">{t("model.deepseekBody")}</p>

          <label className="visual-qa-field deepseek-toggle-row">
            <span
              className={`visual-qa-control ${
                deepSeekSettings.thinking_enabled ? "visual-qa-control-active" : ""
              }`}
            >
              <input
                className="visual-qa-input"
                type="checkbox"
                checked={deepSeekSettings.thinking_enabled}
                onChange={(event) =>
                  onDeepSeekSettingsChange({
                    ...deepSeekSettings,
                    thinking_enabled: event.target.checked,
                  })
                }
              />
              <span className="visual-qa-icon" aria-hidden="true">
                <BrainCircuit size={16} />
              </span>
              <span className="visual-qa-copy">
                <span className="visual-qa-name">{t("model.deepseekThinking")}</span>
              </span>
              <span className="visual-qa-switch" aria-hidden="true">
                <span />
              </span>
            </span>
          </label>

          <label className="form-field">
            <span>{t("model.deepseekEffort")}</span>
            <div className="form-field-icon">
              <BrainCircuit size={14} className="field-icon" />
              <select
                value={deepSeekSettings.reasoning_effort}
                disabled={!deepSeekSettings.thinking_enabled}
                onChange={(event) =>
                  onDeepSeekSettingsChange({
                    ...deepSeekSettings,
                    reasoning_effort: event.target.value as DeepSeekSettings["reasoning_effort"],
                  })
                }
              >
                <option value="high">{t("model.deepseekEffortHigh")}</option>
                <option value="max">{t("model.deepseekEffortMax")}</option>
              </select>
            </div>
          </label>
        </div>
      ) : null}

      {showOpenAISettings ? (
        <div className="deepseek-settings">
          <div className="panel-title-row">
            <BrainCircuit size={15} className="panel-title-icon" />
            <p className="panel-title">{t("model.openaiTitle")}</p>
          </div>

          <label className="form-field">
            <span>{t("model.openaiReasoning")}</span>
            <div className="form-field-icon">
              <BrainCircuit size={14} className="field-icon" />
              <select
                value={openAISettings.reasoning_effort}
                onChange={(event) =>
                  onOpenAISettingsChange({
                    ...openAISettings,
                    reasoning_effort: event.target.value as OpenAISettings["reasoning_effort"],
                  })
                }
              >
                <option value="none">{t("model.openaiReasoningNone")}</option>
                <option value="low">{t("model.openaiReasoningLow")}</option>
                <option value="medium">{t("model.openaiReasoningMedium")}</option>
                <option value="high">{t("model.openaiReasoningHigh")}</option>
                <option value="xhigh">{t("model.openaiReasoningXhigh")}</option>
              </select>
            </div>
          </label>

          <label className="form-field">
            <span>{t("model.openaiVerbosity")}</span>
            <div className="form-field-icon">
              <Zap size={14} className="field-icon" />
              <select
                value={openAISettings.verbosity}
                onChange={(event) =>
                  onOpenAISettingsChange({
                    ...openAISettings,
                    verbosity: event.target.value as OpenAISettings["verbosity"],
                  })
                }
              >
                <option value="low">{t("model.openaiVerbosityLow")}</option>
                <option value="medium">{t("model.openaiVerbosityMedium")}</option>
                <option value="high">{t("model.openaiVerbosityHigh")}</option>
              </select>
            </div>
          </label>
        </div>
      ) : null}
    </section>
  );
}

function isGpt5OrNewer(model: string) {
  const normalized = model.trim().toLowerCase();
  if (!normalized.startsWith("gpt-")) {
    return false;
  }
  const version = normalized.slice(4).split("-", 1)[0];
  const parsed = Number.parseFloat(version);
  return Number.isFinite(parsed) ? parsed >= 5 : normalized.startsWith("gpt-5");
}
