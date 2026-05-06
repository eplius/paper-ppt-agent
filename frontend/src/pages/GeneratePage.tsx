import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Palette, Terminal, X } from "lucide-react";
import { Layout } from "../components/layout/Layout";
import { ModelSelector } from "../components/config/ModelSelector";
import { OptionsPanel } from "../components/config/OptionsPanel";
import { StylePicker, type StyleOverrides } from "../components/config/StylePicker";
import { SlidePreview } from "../components/preview/SlidePreview";
import { SlideViewer } from "../components/preview/SlideViewer";
import { AgentLog } from "../components/progress/AgentLog";
import { ProgressPanel } from "../components/progress/ProgressPanel";
import { FilePreview } from "../components/upload/FilePreview";
import { UploadZone } from "../components/upload/UploadZone";
import { useGeneration } from "../hooks/useGeneration";
import { useLocale } from "../i18n";
import type { DeepSeekSettings, OpenAISettings } from "../lib/types";

const ROUTING_PROFILE_STORAGE_KEY = "paper-ppt-agent-routing-profiles-v1";
type LanguageMode = "zh" | "en" | "custom";
type SecondaryPanel = "style" | "log";
const DEFAULT_DEEPSEEK_SETTINGS: DeepSeekSettings = {
  thinking_enabled: true,
  reasoning_effort: "max",
};
const DEFAULT_OPENAI_SETTINGS: OpenAISettings = {
  reasoning_effort: "medium",
  verbosity: "high",
};

interface RoutingProfile {
  model: string;
  baseUrl: string;
  apiKey: string;
  deepseekSettings?: DeepSeekSettings;
  openaiSettings?: OpenAISettings;
}

type RoutingProfileMap = Record<string, RoutingProfile>;

function readRoutingProfiles(): RoutingProfileMap {
  try {
    const raw = window.localStorage.getItem(ROUTING_PROFILE_STORAGE_KEY);
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw) as RoutingProfileMap;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function writeRoutingProfiles(profiles: RoutingProfileMap) {
  window.localStorage.setItem(ROUTING_PROFILE_STORAGE_KEY, JSON.stringify(profiles));
}

function getProviderDefaults(
  providers: { name: string; default_base_url?: string | null }[],
  providerName: string,
) {
  const selectedProvider = providers.find((item) => item.name === providerName);
  return {
    baseUrl: selectedProvider?.default_base_url ?? "",
  };
}

export function GeneratePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { t, locale } = useLocale();
  const {
    providers,
    uploadSession,
    jobId,
    job,
    slides,
    logs,
    criticEvents,
    selectedSlide,
    connectionStatus,
    error,
    currentRunConfig,
    history,
    loadProviders,
    uploadFile,
    startGeneration,
    cancelCurrentRun,
    connect,
    resumeCurrentRun,
    selectSlide,
    reset,
  } = useGeneration();

  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [deepSeekSettings, setDeepSeekSettings] = useState<DeepSeekSettings>(
    DEFAULT_DEEPSEEK_SETTINGS,
  );
  const [openAISettings, setOpenAISettings] = useState<OpenAISettings>(
    DEFAULT_OPENAI_SETTINGS,
  );
  const [style, setStyle] = useState("academic");
  const [styleOverrides, setStyleOverrides] = useState<StyleOverrides>({});
  const [canvasFormat, setCanvasFormat] = useState("ppt169");
  const [languageMode, setLanguageMode] = useState<LanguageMode>(locale === "zh" ? "zh" : "en");
  const [customLanguage, setCustomLanguage] = useState("");
  const [numPages, setNumPages] = useState("");
  const [detailLevel, setDetailLevel] = useState("normal");
  const [timeoutSeconds, setTimeoutSeconds] = useState("");
  const [instruction, setInstruction] = useState("");
  const GEMINI_KEY_STORAGE = "paper-ppt-agent-gemini-api-key";
  const [enableVisualCritic, setEnableVisualCritic] = useState(false);
  const [enableIcon, setEnableIcon] = useState(true);
  const [enableIconRag, setEnableIconRag] = useState(true);
  const [geminiApiKey, setGeminiApiKey] = useState(() => {
    try { return window.localStorage.getItem(GEMINI_KEY_STORAGE) ?? ""; } catch { return ""; }
  });
  const [cancelLoading, setCancelLoading] = useState(false);
  const [secondaryPanel, setSecondaryPanel] = useState<SecondaryPanel | null>(null);
  const freshRequested = searchParams.get("fresh") === "1";
  const targetJobId = searchParams.get("job") ?? undefined;
  const targetHistoryEntry = targetJobId
    ? history.find((entry) => entry.jobId === targetJobId)
    : undefined;
  const selectedRunConfig = useMemo(() => {
    if (currentRunConfig) {
      return currentRunConfig;
    }
    if (
      targetHistoryEntry?.provider &&
      targetHistoryEntry.model &&
      targetHistoryEntry.options
    ) {
      return {
        provider: targetHistoryEntry.provider,
        model: targetHistoryEntry.model,
        baseUrl: targetHistoryEntry.baseUrl ?? undefined,
        options: targetHistoryEntry.options,
        parentJobId: targetHistoryEntry.parentJobId ?? null,
      };
    }
    return undefined;
  }, [currentRunConfig, targetHistoryEntry]);
  const canCancelCurrentRun = Boolean(
    jobId &&
      job &&
      !["complete", "error", "cancelled"].includes(job.status),
  );

  useEffect(() => {
    void loadProviders();
  }, [loadProviders]);

  useEffect(() => {
    if (freshRequested) {
      reset();
      navigate("/generate", { replace: true });
      return;
    }

    void resumeCurrentRun(targetJobId);
  }, [freshRequested, navigate, reset, resumeCurrentRun, targetJobId]);

  useEffect(() => {
    if (!provider && providers.length > 0) {
      const defaultProvider = providers[0].name;
      const saved = readRoutingProfiles()[defaultProvider];
      const defaults = getProviderDefaults(providers, defaultProvider);
      setProvider(defaultProvider);
      setModel("");
      setBaseUrl(saved?.baseUrl || defaults.baseUrl);
      setApiKey(saved?.apiKey || "");
      setDeepSeekSettings(saved?.deepseekSettings ?? DEFAULT_DEEPSEEK_SETTINGS);
      setOpenAISettings(saved?.openaiSettings ?? DEFAULT_OPENAI_SETTINGS);
    }
  }, [provider, providers]);

  useEffect(() => {
    if (!provider) {
      return;
    }
    if (targetJobId) {
      return;
    }
    const profiles = readRoutingProfiles();
    const saved = profiles[provider];
    const defaults = getProviderDefaults(providers, provider);
    setModel(saved?.model || "");
    setBaseUrl(saved?.baseUrl || defaults.baseUrl);
    setApiKey(saved?.apiKey || "");
    setDeepSeekSettings(saved?.deepseekSettings ?? DEFAULT_DEEPSEEK_SETTINGS);
    setOpenAISettings(saved?.openaiSettings ?? DEFAULT_OPENAI_SETTINGS);
  }, [provider, providers]);

  useEffect(() => {
    if (!provider) {
      return;
    }
    if (targetJobId) {
      return;
    }
    const profiles = readRoutingProfiles();
    const existing = profiles[provider];
    profiles[provider] = {
      model: model.trim() || existing?.model || "",
      baseUrl,
      apiKey,
      deepseekSettings: provider === "deepseek" ? deepSeekSettings : existing?.deepseekSettings,
      openaiSettings: provider === "openai" ? openAISettings : existing?.openaiSettings,
    };
    writeRoutingProfiles(profiles);
  }, [apiKey, baseUrl, deepSeekSettings, model, openAISettings, provider, targetJobId]);

  useEffect(() => {
    if (!targetJobId || !selectedRunConfig) {
      return;
    }

    const options = selectedRunConfig.options;
    const savedProfile = readRoutingProfiles()[selectedRunConfig.provider];
    setProvider(selectedRunConfig.provider);
    setModel(selectedRunConfig.model);
    setBaseUrl(selectedRunConfig.baseUrl ?? "");
    setApiKey(savedProfile?.apiKey ?? "");
    setDeepSeekSettings(savedProfile?.deepseekSettings ?? DEFAULT_DEEPSEEK_SETTINGS);
    setOpenAISettings(savedProfile?.openaiSettings ?? DEFAULT_OPENAI_SETTINGS);
    setCanvasFormat(options.canvas_format || "ppt169");
    setStyle(options.style || "academic");
    setStyleOverrides(options.style_overrides ?? {});
    if (options.language === "zh" || options.language === "en") {
      setLanguageMode(options.language);
      setCustomLanguage("");
    } else {
      setLanguageMode("custom");
      setCustomLanguage(options.language || "");
    }
    setNumPages(options.num_pages ? String(options.num_pages) : "");
    setDetailLevel(options.detail_level || "normal");
    setTimeoutSeconds(options.timeout_seconds ? String(options.timeout_seconds) : "");
    setEnableVisualCritic(Boolean(options.enable_visual_critic));
    setEnableIcon(options.enable_icon !== false);
    setEnableIconRag(options.enable_icon_rag !== false);
    setGeminiApiKey(options.gemini_api_key ?? "");
  }, [selectedRunConfig, targetJobId]);

  useEffect(() => {
    setLanguageMode((current) => (current === "custom" ? current : locale === "zh" ? "zh" : "en"));
  }, [locale]);

  useEffect(() => {
    try { window.localStorage.setItem(GEMINI_KEY_STORAGE, geminiApiKey); } catch { /* noop */ }
  }, [geminiApiKey]);

  useEffect(() => {
    if (job?.status === "complete" && jobId) {
      navigate(`/result?job=${jobId}`);
    }
  }, [job?.status, jobId, navigate]);

  return (
    <Layout contentClassName="studio-page">
      <section className="studio-layout">
        <div className="studio-column studio-column-left">
          <UploadZone onFileSelect={(file) => void uploadFile(file)} />
          <FilePreview session={uploadSession} />
          <ProgressPanel job={job} connectionStatus={connectionStatus} />
        </div>

        <div className="studio-column studio-column-preview">
          <SlideViewer slide={selectedSlide} />
          <SlidePreview slides={slides} selectedSlide={selectedSlide} onSelect={selectSlide} />
        </div>

        <div className="studio-config-rail studio-column-right">
          <ModelSelector
            providers={providers}
            provider={provider}
            model={model}
            baseUrl={baseUrl}
            apiKey={apiKey}
            deepSeekSettings={deepSeekSettings}
            openAISettings={openAISettings}
            onProviderChange={(nextProvider) => {
              setProvider(nextProvider);
            }}
            onModelChange={setModel}
            onBaseUrlChange={setBaseUrl}
            onApiKeyChange={setApiKey}
            onDeepSeekSettingsChange={setDeepSeekSettings}
            onOpenAISettingsChange={setOpenAISettings}
          />
          <OptionsPanel
            canvasFormat={canvasFormat}
            languageMode={languageMode}
            customLanguage={customLanguage}
            numPages={numPages}
            detailLevel={detailLevel}
            timeoutSeconds={timeoutSeconds}
            instruction={instruction}
            enableVisualCritic={enableVisualCritic}
            enableIcon={enableIcon}
            enableIconRag={enableIconRag}
            geminiApiKey={geminiApiKey}
            onCanvasFormatChange={setCanvasFormat}
            onLanguageModeChange={setLanguageMode}
            onCustomLanguageChange={setCustomLanguage}
            onNumPagesChange={setNumPages}
            onDetailLevelChange={setDetailLevel}
            onTimeoutSecondsChange={setTimeoutSeconds}
            onInstructionChange={setInstruction}
            onEnableVisualCriticChange={setEnableVisualCritic}
            onEnableIconChange={setEnableIcon}
            onEnableIconRagChange={setEnableIconRag}
            onGeminiApiKeyChange={setGeminiApiKey}
          />
          <div className="studio-secondary-actions">
            <button
              type="button"
              className={`secondary-action ${secondaryPanel === "style" ? "secondary-action-active" : ""}`}
              onClick={() => setSecondaryPanel((current) => (current === "style" ? null : "style"))}
            >
              <Palette size={16} />
              <span>{t("style.title")}</span>
            </button>
            <button
              type="button"
              className={`secondary-action ${secondaryPanel === "log" ? "secondary-action-active" : ""}`}
              onClick={() => setSecondaryPanel((current) => (current === "log" ? null : "log"))}
            >
              <Terminal size={16} />
              <span>{t("log.title")}</span>
            </button>
          </div>
          <button
            type="button"
            className="primary-button full-width launch-button"
            disabled={
              !uploadSession ||
              !provider ||
              !model.trim() ||
              !apiKey ||
              (languageMode === "custom" && !customLanguage.trim()) ||
              canCancelCurrentRun
            }
            onClick={async () => {
              if (!uploadSession) {
                return;
              }
              const normalizedModel = model.trim();
              const profiles = readRoutingProfiles();
              profiles[provider] = {
                model: normalizedModel,
                baseUrl,
                apiKey,
                deepseekSettings: provider === "deepseek" ? deepSeekSettings : undefined,
                openaiSettings: provider === "openai" ? openAISettings : undefined,
              };
              writeRoutingProfiles(profiles);
              const jobId = await startGeneration({
                session_id: uploadSession.session_id,
                instruction,
                model_config: {
                  provider,
                  model: normalizedModel,
                  api_key: apiKey,
                  base_url: baseUrl || undefined,
                  deepseek_settings: provider === "deepseek" ? deepSeekSettings : undefined,
                  openai_settings: provider === "openai" ? openAISettings : undefined,
                },
                options: {
                  canvas_format: canvasFormat,
                  style,
                  language: resolveRequestedLanguage(languageMode, customLanguage),
                  num_pages: numPages ? Number(numPages) : undefined,
                  detail_level: detailLevel,
                  timeout_seconds: parseOptionalPositiveInt(timeoutSeconds),
                  style_overrides:
                    styleOverrides.palette || styleOverrides.font || styleOverrides.density
                      ? styleOverrides
                      : undefined,
                  enable_visual_critic: enableVisualCritic,
                  enable_icon: enableIcon,
                  enable_icon_rag: enableIconRag,
                  gemini_api_key: geminiApiKey || undefined,
                },
              });
              connect(jobId);
            }}
          >
            {t("studio.launch")}
          </button>
          {canCancelCurrentRun ? (
            <button
              type="button"
              className="secondary-button danger-button full-width cancel-generation-button"
              disabled={cancelLoading || job?.status === "cancelling"}
              onClick={async () => {
                setCancelLoading(true);
                try {
                  await cancelCurrentRun();
                } finally {
                  setCancelLoading(false);
                }
              }}
            >
              {cancelLoading || job?.status === "cancelling"
                ? t("studio.canceling")
                : t("studio.cancel")}
            </button>
          ) : null}
          {error ? <p className="error-text">{error}</p> : null}
        </div>
      </section>
      <aside
        className={`studio-secondary-panel ${secondaryPanel ? "studio-secondary-panel-open" : ""}`}
        aria-hidden={!secondaryPanel}
      >
        <div className="studio-secondary-header">
          <div className="panel-title-row">
            {secondaryPanel === "style" ? (
              <Palette size={15} className="panel-title-icon" />
            ) : (
              <Terminal size={15} className="panel-title-icon" />
            )}
            <p className="panel-title">
              {secondaryPanel === "style" ? t("style.title") : t("log.title")}
            </p>
          </div>
          <button
            type="button"
            className="icon-btn"
            aria-label={t("common.close")}
            onClick={() => setSecondaryPanel(null)}
          >
            <X size={17} />
          </button>
        </div>
        <div className="studio-secondary-body">
          {secondaryPanel === "style" ? (
            <StylePicker
              value={style}
              onChange={setStyle}
              overrides={styleOverrides}
              onOverridesChange={setStyleOverrides}
            />
          ) : null}
          {secondaryPanel === "log" ? <AgentLog logs={logs} criticEvents={criticEvents} jobId={jobId} /> : null}
        </div>
      </aside>
    </Layout>
  );
}

function parseOptionalPositiveInt(value: string): number | undefined {
  const normalized = value.trim();
  if (!normalized) {
    return undefined;
  }
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return undefined;
  }
  return Math.floor(parsed);
}

function resolveRequestedLanguage(languageMode: LanguageMode, customLanguage: string): string {
  if (languageMode === "custom") {
    return customLanguage.trim();
  }
  return languageMode;
}
