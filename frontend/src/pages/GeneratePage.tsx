import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Layout } from "../components/layout/Layout";
import { ModelSelector } from "../components/config/ModelSelector";
import { OptionsPanel } from "../components/config/OptionsPanel";
import { StylePicker } from "../components/config/StylePicker";
import { SlidePreview } from "../components/preview/SlidePreview";
import { SlideViewer } from "../components/preview/SlideViewer";
import { AgentLog } from "../components/progress/AgentLog";
import { ProgressPanel } from "../components/progress/ProgressPanel";
import { FilePreview } from "../components/upload/FilePreview";
import { UploadZone } from "../components/upload/UploadZone";
import { useGeneration } from "../hooks/useGeneration";
import { useLocale } from "../i18n";

const ROUTING_PROFILE_STORAGE_KEY = "paper-ppt-agent-routing-profiles-v1";

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
  const [canvasFormat, setCanvasFormat] = useState("ppt169");
  const [language, setLanguage] = useState<string>(locale);
  const [numPages, setNumPages] = useState("");
  const [detailLevel, setDetailLevel] = useState("normal");
  const [instruction, setInstruction] = useState("");

  useEffect(() => {
    void loadProviders();
  }, [loadProviders]);

  useEffect(() => {
    if (searchParams.get("fresh") === "1") {
      reset();
      return;
    }

    const targetJobId = searchParams.get("job") ?? undefined;
    void resumeCurrentRun(targetJobId);
  }, [navigate, reset, resumeCurrentRun, searchParams]);

  useEffect(() => {
    if (!provider && providers.length > 0) {
      const defaultProvider = providers[0].name;
      const saved = readRoutingProfiles()[defaultProvider];
      setProvider(defaultProvider);
      setModel(saved?.model || providers[0].models[0]?.id || "");
      setBaseUrl(saved?.baseUrl || "");
      setApiKey(saved?.apiKey || "");
    }
  }, [provider, providers]);

  useEffect(() => {
    if (!provider) {
      return;
    }
    const profiles = readRoutingProfiles();
    const saved = profiles[provider];
    const suggestedModel = providers.find((item) => item.name === provider)?.models[0]?.id ?? "";
    setModel(saved?.model || suggestedModel);
    setBaseUrl(saved?.baseUrl || "");
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
    setLanguage((current) => (current === "en" || current === "zh" ? locale : current));
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
          <StylePicker value={style} onChange={setStyle} />
          <OptionsPanel
            canvasFormat={canvasFormat}
            language={language}
            numPages={numPages}
            detailLevel={detailLevel}
            instruction={instruction}
            onCanvasFormatChange={setCanvasFormat}
            onLanguageChange={setLanguage}
            onNumPagesChange={setNumPages}
            onDetailLevelChange={setDetailLevel}
            onInstructionChange={setInstruction}
          />
          <button
            type="button"
            className="primary-button full-width launch-button"
            disabled={!uploadSession || !provider || !model || !apiKey}
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
                  language,
                  num_pages: numPages ? Number(numPages) : undefined,
                  detail_level: detailLevel,
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
