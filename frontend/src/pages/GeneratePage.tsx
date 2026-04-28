import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
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

const ROUTING_PROFILE_STORAGE_KEY = "paper-ppt-agent-routing-profiles-v1";
type LanguageMode = "zh" | "en" | "custom";

interface RoutingProfile {
  model: string;
  baseUrl: string;
  apiKey: string;
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
  providers: { name: string; models: { id: string }[]; default_base_url?: string | null }[],
  providerName: string,
) {
  const selectedProvider = providers.find((item) => item.name === providerName);
  return {
    model: selectedProvider?.models[0]?.id ?? "",
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
    selectedSlide,
    connectionStatus,
    error,
    loadProviders,
    uploadFile,
    startGeneration,
    connect,
    resumeCurrentRun,
    selectSlide,
    reset,
  } = useGeneration();

  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [style, setStyle] = useState("academic");
  const [styleOverrides, setStyleOverrides] = useState<StyleOverrides>({});
  const [canvasFormat, setCanvasFormat] = useState("ppt169");
  const [languageMode, setLanguageMode] = useState<LanguageMode>(locale === "zh" ? "zh" : "en");
  const [customLanguage, setCustomLanguage] = useState("");
  const [numPages, setNumPages] = useState("");
  const [detailLevel, setDetailLevel] = useState("normal");
  const [timeoutSeconds, setTimeoutSeconds] = useState("");
  const [instruction, setInstruction] = useState("");
  const freshRequested = searchParams.get("fresh") === "1";
  const targetJobId = searchParams.get("job") ?? undefined;

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
      setModel(saved?.model || defaults.model);
      setBaseUrl(saved?.baseUrl || defaults.baseUrl);
      setApiKey(saved?.apiKey || "");
    }
  }, [provider, providers]);

  useEffect(() => {
    if (!provider) {
      return;
    }
    const profiles = readRoutingProfiles();
    const saved = profiles[provider];
    const defaults = getProviderDefaults(providers, provider);
    setModel(saved?.model || defaults.model);
    setBaseUrl(saved?.baseUrl || defaults.baseUrl);
    setApiKey(saved?.apiKey || "");
  }, [provider, providers]);

  useEffect(() => {
    if (!provider) {
      return;
    }
    const profiles = readRoutingProfiles();
    profiles[provider] = {
      model,
      baseUrl,
      apiKey,
    };
    writeRoutingProfiles(profiles);
  }, [apiKey, baseUrl, model, provider]);

  useEffect(() => {
    setLanguageMode((current) => (current === "custom" ? current : locale === "zh" ? "zh" : "en"));
  }, [locale]);

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
          <AgentLog logs={logs} />
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
            onProviderChange={(nextProvider) => {
              setProvider(nextProvider);
            }}
            onModelChange={setModel}
            onBaseUrlChange={setBaseUrl}
            onApiKeyChange={setApiKey}
          />
          <StylePicker
            value={style}
            onChange={setStyle}
            overrides={styleOverrides}
            onOverridesChange={setStyleOverrides}
          />
          <OptionsPanel
            canvasFormat={canvasFormat}
            languageMode={languageMode}
            customLanguage={customLanguage}
            numPages={numPages}
            detailLevel={detailLevel}
            timeoutSeconds={timeoutSeconds}
            instruction={instruction}
            onCanvasFormatChange={setCanvasFormat}
            onLanguageModeChange={setLanguageMode}
            onCustomLanguageChange={setCustomLanguage}
            onNumPagesChange={setNumPages}
            onDetailLevelChange={setDetailLevel}
            onTimeoutSecondsChange={setTimeoutSeconds}
            onInstructionChange={setInstruction}
          />
          <button
            type="button"
            className="primary-button full-width launch-button"
            disabled={
              !uploadSession ||
              !provider ||
              !model ||
              !apiKey ||
              (languageMode === "custom" && !customLanguage.trim())
            }
            onClick={async () => {
              if (!uploadSession) {
                return;
              }
              const jobId = await startGeneration({
                session_id: uploadSession.session_id,
                instruction,
                model_config: {
                  provider,
                  model,
                  api_key: apiKey,
                  base_url: baseUrl || undefined,
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
                },
              });
              connect(jobId);
            }}
          >
            {t("studio.launch")}
          </button>
          {error ? <p className="error-text">{error}</p> : null}
        </div>
      </section>
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
