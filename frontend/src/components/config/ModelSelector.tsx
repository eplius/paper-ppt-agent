import { useState } from "react";
import type { ProviderListItem } from "../../lib/types";
import { useLocale } from "../../i18n";
import { Bot, Cpu, Zap, Globe, Key, Eye, EyeOff } from "lucide-react";

interface ModelSelectorProps {
  providers: ProviderListItem[];
  provider: string;
  model: string;
  baseUrl: string;
  apiKey: string;
  onProviderChange: (provider: string) => void;
  onModelChange: (model: string) => void;
  onBaseUrlChange: (baseUrl: string) => void;
  onApiKeyChange: (apiKey: string) => void;
}

export function ModelSelector({
  providers,
  provider,
  model,
  baseUrl,
  apiKey,
  onProviderChange,
  onModelChange,
  onBaseUrlChange,
  onApiKeyChange,
}: ModelSelectorProps) {
  const selectedProvider = providers.find((item) => item.name === provider);
  const { t } = useLocale();
  const datalistId = `model-options-${provider || "default"}`;
  const [showKey, setShowKey] = useState(false);

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
    </section>
  );
}
