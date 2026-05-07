import { useState } from "react";
import { useLocale } from "../../i18n";
import { updateSvgFonts, reexportPresentation } from "../../lib/api";
import type { UpdateFontsRequest } from "../../lib/types";

interface FontOption { label: string; value: string }

const WH_OPTIONS: FontOption[] = [
  { label: "-- keep default --", value: "" },
  { label: "Arial Black", value: "Arial Black" },
  { label: "Impact", value: "Impact" },
  { label: "Helvetica", value: "Helvetica" },
  { label: "Calibri", value: "Calibri" },
  { label: "Georgia", value: "Georgia" },
  { label: "Cambria", value: "Cambria" },
  { label: "Times New Roman", value: "Times New Roman" },
  { label: "Verdana", value: "Verdana" },
];
const WB_OPTIONS: FontOption[] = [
  { label: "-- keep default --", value: "" },
  { label: "Arial", value: "Arial" },
  { label: "Calibri", value: "Calibri" },
  { label: "Helvetica", value: "Helvetica" },
  { label: "Times New Roman", value: "Times New Roman" },
  { label: "Verdana", value: "Verdana" },
  { label: "Georgia", value: "Georgia" },
  { label: "Cambria", value: "Cambria" },
  { label: "Palatino", value: "Palatino" },
];
const CH_OPTIONS: FontOption[] = [
  { label: "-- 保持默认 --", value: "" },
  { label: "微软雅黑", value: "Microsoft YaHei" },
  { label: "黑体", value: "SimHei" },
  { label: "思源黑体", value: "Source Han Sans SC" },
  { label: "楷体", value: "KaiTi" },
  { label: "等线", value: "DengXian" },
  { label: "华文黑体", value: "STHeiti" },
];
const CB_OPTIONS: FontOption[] = [
  { label: "-- 保持默认 --", value: "" },
  { label: "宋体", value: "SimSun" },
  { label: "仿宋", value: "FangSong" },
  { label: "楷体", value: "KaiTi" },
  { label: "微软雅黑", value: "Microsoft YaHei" },
  { label: "等线", value: "DengXian" },
  { label: "华文宋体", value: "STSong" },
  { label: "华文楷体", value: "STKaiti" },
  { label: "思源宋体", value: "Source Han Serif SC" },
];

interface Props {
  jobId: string;
  onReexported: (outputPath: string) => void;
}

export function FontCustomizer({ jobId, onReexported }: Props) {
  const { t } = useLocale();
  const [wh, setWh] = useState("");
  const [wb, setWb] = useState("");
  const [ch, setCh] = useState("");
  const [cb, setCb] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ replaced: number } | null>(null);

  const anySet = wh || wb || ch || cb;

  const handleApply = async () => {
    if (!anySet) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const config: UpdateFontsRequest = {};
      if (wh) config.western_heading = wh;
      if (wb) config.western_body = wb;
      if (ch) config.cjk_heading = ch;
      if (cb) config.cjk_body = cb;

      const resp = await updateSvgFonts(jobId, config);
      setResult({ replaced: resp.svg_fonts_replaced });

      // Auto re-export
      const reexportResp = await reexportPresentation(jobId);
      onReexported(reexportResp.output_path);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Font update failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section style={{
      display: "flex", flexWrap: "wrap", alignItems: "flex-end",
      gap: "0.75rem", padding: "0.9rem 1.1rem",
      borderRadius: 10, border: "1px solid var(--line)",
      background: "var(--surface-soft)",
      marginTop: "1.5rem",
    }}>
      <div style={{ flex: "1 1 100%", marginBottom: "0.15rem" }}>
        <h3 style={{ fontSize: "1rem", fontWeight: 600, margin: "0 0 0.15rem" }}>
          {t("result.fontsTitle")}
        </h3>
        <p style={{ fontSize: "0.78rem", color: "var(--muted)", margin: 0 }}>
          {t("result.fontsBody")}
        </p>
      </div>

      {[
        { key: "wh", label: t("result.fontsWesternHeading"), value: wh, setter: setWh, options: WH_OPTIONS },
        { key: "wb", label: t("result.fontsWesternBody"), value: wb, setter: setWb, options: WB_OPTIONS },
        { key: "ch", label: t("result.fontsCJKHeading"), value: ch, setter: setCh, options: CH_OPTIONS },
        { key: "cb", label: t("result.fontsCJKBody"), value: cb, setter: setCb, options: CB_OPTIONS },
      ].map((item) => (
        <div key={item.key} style={{ display: "flex", flexDirection: "column", gap: "0.35rem", flex: "1 1 120px", minWidth: 0 }}>
          <label style={{ fontWeight: 500, fontSize: "0.8rem", color: "var(--muted)" }}>{item.label}</label>
          <select
            value={item.value}
            onChange={(e) => item.setter(e.target.value)}
            disabled={loading}
            style={{
              padding: "0.45rem 0.55rem", borderRadius: 10,
              border: "1px solid var(--line)", background: "var(--surface-strong)",
              color: "var(--text)", fontSize: "0.82rem", cursor: "pointer",
              fontFamily: item.value || undefined,
            }}
          >
            {item.options.map((opt) => (
              <option key={opt.value} value={opt.value} style={{ fontFamily: opt.value || undefined }}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      ))}

      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "0.35rem" }}>
        {error && <p style={{ color: "#ff938f", fontSize: "0.8rem", margin: 0 }}>{error}</p>}
        {result && (
          <p style={{ color: "var(--success)", fontSize: "0.8rem", margin: 0 }}>
            {t("result.fontsApplied").replace("{n}", String(result.replaced))}
          </p>
        )}
        <button
          type="button"
          className="primary-button"
          onClick={handleApply}
          disabled={loading || !anySet}
          style={{ minHeight: 40, padding: "0.5rem 1rem", fontSize: "0.85rem" }}
        >
          {loading ? t("result.fontsLoading") : t("result.fontsApply")}
        </button>
      </div>
    </section>
  );
}
