import type { PreviewSlide } from "../../lib/types";
import { useLocale } from "../../i18n";

interface SlideViewerProps {
  slide?: PreviewSlide;
}

export function SlideViewer({ slide }: SlideViewerProps) {
  const { t } = useLocale();
  return (
    <section className="panel viewer-panel">
      <div className="panel-header-row">
        <div>
          <p className="panel-title">{t("viewer.title")}</p>
          <p className="muted-copy">{t("viewer.body")}</p>
          <p className="panel-support-text">
            {slide ? `${t("viewer.slide")} ${slide.index}` : t("viewer.waiting")}
          </p>
        </div>
      </div>
      {slide ? (
        <div className="viewer-frame" dangerouslySetInnerHTML={{ __html: slide.content }} />
      ) : (
        <div className="viewer-empty">
          <p>{t("viewer.empty")}</p>
        </div>
      )}
    </section>
  );
}
