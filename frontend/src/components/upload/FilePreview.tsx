import { CheckCircle, FileQuestion, File } from "lucide-react";
import type { UploadResponse } from "../../lib/types";
import { useLocale } from "../../i18n";

interface FilePreviewProps {
  session?: UploadResponse;
}

export function FilePreview({ session }: FilePreviewProps) {
  const { t } = useLocale();
  return (
    <section className="panel">
      <div className="panel-header-row">
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {session ? (
            <CheckCircle size={16} color="var(--success)" />
          ) : (
            <FileQuestion size={16} color="var(--muted)" />
          )}
          <div>
            <p className="panel-title">{t("file.title")}</p>
            <p className="panel-support-text">{session ? t("file.loaded") : t("file.empty")}</p>
          </div>
        </div>
      </div>
      {session ? (
        <div className="file-card">
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <File size={15} color="var(--accent)" />
            <strong>{session.file_info.name}</strong>
          </div>
          <div className="info-pair">
            <span>{t("file.size")}</span>
            <span>{(session.file_info.size / 1024).toFixed(1)} KB</span>
          </div>
          <div className="info-pair">
            <span>{t("file.type")}</span>
            <span>{session.file_info.source_type.toUpperCase()}</span>
          </div>
          <div className="session-chip">{session.session_id}</div>
        </div>
      ) : (
        <p className="muted-copy">{t("file.none")}</p>
      )}
    </section>
  );
}
