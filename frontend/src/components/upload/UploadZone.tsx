import { useRef, useState } from "react";
import { UploadCloud } from "lucide-react";
import { useLocale } from "../../i18n";

interface UploadZoneProps {
  onFileSelect: (file: File) => void;
}

export function UploadZone({ onFileSelect }: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const { t } = useLocale();
  const [isDragging, setIsDragging] = useState(false);

  return (
    <section className="panel panel-emphasis">
      <div
        className={`upload-zone ${isDragging ? "upload-zone-dragging" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          const file = e.dataTransfer.files[0];
          if (file) onFileSelect(file);
        }}
        role="button"
        tabIndex={0}
      >
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.75rem", padding: "1rem 0" }}>
          <UploadCloud size={40} color="var(--accent)" strokeWidth={1.5} />
          <div className="upload-copy" style={{ textAlign: "center" }}>
            <p className="panel-title">{t("upload.title")}</p>
            <p className="muted-copy">{t("upload.body")}</p>
          </div>
        </div>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.tex,.zip,.tgz,.tar.gz"
        className="hidden-input"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFileSelect(file);
          e.currentTarget.value = "";
        }}
      />
    </section>
  );
}
