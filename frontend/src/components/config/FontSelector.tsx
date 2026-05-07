import { ChevronDown, Plus, Type, X } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { useLocale } from "../../i18n";

interface FontSelectorProps {
  value: string; // CSS font-family string, e.g. "Microsoft YaHei, Arial, sans-serif"
  onChange: (value: string) => void;
}

interface FontCategory {
  label: string;
  labelKey: string;
  fonts: string[];
}

const FONT_CATEGORIES: FontCategory[] = [
  {
    label: "中文无衬线",
    labelKey: "font.catZhSans",
    fonts: ["Microsoft YaHei", "Noto Sans SC", "PingFang SC", "Source Han Sans SC", "DengXian", "STHeiti"],
  },
  {
    label: "中文衬线",
    labelKey: "font.catZhSerif",
    fonts: ["SimSun", "KaiTi", "Noto Serif SC", "Source Han Serif SC", "STSong", "STKaiti", "FangSong"],
  },
  {
    label: "英文无衬线",
    labelKey: "font.catEnSans",
    fonts: ["Arial", "Calibri", "Segoe UI", "Helvetica", "Helvetica Neue", "Inter", "Roboto", "SF Pro"],
  },
  {
    label: "英文衬线",
    labelKey: "font.catEnSerif",
    fonts: ["Times New Roman", "Georgia", "Cambria", "Garamond", "Palatino"],
  },
  {
    label: "代码",
    labelKey: "font.catMono",
    fonts: ["Consolas", "SF Mono", "Monaco", "Menlo", "Courier New", "Cascadia Code"],
  },
  {
    label: "CSS Generic",
    labelKey: "font.catGeneric",
    fonts: ["sans-serif", "serif", "monospace"],
  },
];

function splitFontStack(stack: string): string[] {
  if (!stack.trim()) return [];
  return stack
    .split(",")
    .map((f) => f.trim().replace(/^['"]|['"]$/g, ""))
    .filter(Boolean);
}

function joinFontStack(fonts: string[]): string {
  return fonts
    .map((f) => (f.includes(" ") ? `"${f}"` : f))
    .join(", ");
}

export function FontSelector({ value, onChange }: FontSelectorProps) {
  const { t } = useLocale();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [expandedCats, setExpandedCats] = useState<Set<number>>(new Set());
  const [manualInput, setManualInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const selectedFonts = splitFontStack(value);

  const addFont = useCallback(
    (font: string) => {
      const trimmed = font.trim().replace(/^['"]|['"]$/g, "");
      if (!trimmed) return;
      // Deduplicate (case-insensitive)
      const lower = trimmed.toLowerCase();
      if (selectedFonts.some((f) => f.toLowerCase() === lower)) return;
      onChange(joinFontStack([...selectedFonts, trimmed]));
    },
    [selectedFonts, onChange],
  );

  const removeFont = useCallback(
    (index: number) => {
      const next = selectedFonts.filter((_, i) => i !== index);
      onChange(joinFontStack(next));
    },
    [selectedFonts, onChange],
  );

  const toggleCat = (idx: number) => {
    setExpandedCats((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const handleManualAdd = () => {
    addFont(manualInput);
    setManualInput("");
    inputRef.current?.focus();
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
      {/* Selected font tags */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "0.35rem",
          minHeight: "34px",
          padding: selectedFonts.length ? "0.35rem" : 0,
          borderRadius: "12px",
          background: selectedFonts.length ? "rgba(255,255,255,0.03)" : "transparent",
          border: selectedFonts.length ? "1px solid var(--line)" : "1px solid transparent",
        }}
      >
        {selectedFonts.length === 0 && (
          <span
            style={{
              fontSize: "0.82rem",
              color: "var(--muted)",
              padding: "0.35rem 0",
              opacity: 0.6,
            }}
          >
            {t("font.noSelection")}
          </span>
        )}
        {selectedFonts.map((font, i) => (
          <span
            key={`${font}-${i}`}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.3rem",
              padding: "0.25rem 0.55rem",
              borderRadius: "999px",
              border: "1px solid rgba(255,139,71,0.24)",
              background: "rgba(255,139,71,0.08)",
              fontSize: "0.78rem",
              fontWeight: 600,
              color: "var(--text)",
              whiteSpace: "nowrap",
            }}
          >
            {font}
            <button
              type="button"
              onClick={() => removeFont(i)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 16,
                height: 16,
                borderRadius: "999px",
                border: "none",
                background: "rgba(255,255,255,0.08)",
                color: "var(--muted)",
                cursor: "pointer",
                padding: 0,
                lineHeight: 1,
              }}
              aria-label={`Remove ${font}`}
            >
              <X size={10} />
            </button>
          </span>
        ))}
      </div>

      {/* Add font button + dropdown */}
      <div style={{ position: "relative" }}>
        <button
          type="button"
          onClick={() => setDropdownOpen(!dropdownOpen)}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.4rem",
            padding: "0.45rem 0.75rem",
            borderRadius: "12px",
            border: "1px solid var(--line)",
            background: "rgba(255,255,255,0.03)",
            color: "var(--muted)",
            fontSize: "0.82rem",
            cursor: "pointer",
            width: "100%",
            justifyContent: "space-between",
          }}
        >
          <span style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem" }}>
            <Plus size={14} />
            {t("font.addFont")}
          </span>
          <ChevronDown
            size={14}
            style={{
              transform: dropdownOpen ? "rotate(180deg)" : "none",
              transition: "transform 150ms ease",
            }}
          />
        </button>

        {dropdownOpen && (
          <div
            style={{
              position: "absolute",
              top: "calc(100% + 4px)",
              left: 0,
              right: 0,
              zIndex: 20,
              maxHeight: 280,
              overflowY: "auto",
              borderRadius: "14px",
              border: "1px solid var(--line)",
              background: "var(--surface-strong)",
              boxShadow: "0 16px 40px rgba(0,0,0,0.28)",
              padding: "0.4rem",
            }}
          >
            {FONT_CATEGORIES.map((cat, catIdx) => {
              const expanded = expandedCats.has(catIdx);
              return (
                <div key={catIdx}>
                  <button
                    type="button"
                    onClick={() => toggleCat(catIdx)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.4rem",
                      width: "100%",
                      padding: "0.5rem 0.6rem",
                      border: "none",
                      borderRadius: "8px",
                      background: "transparent",
                      color: "var(--text)",
                      fontSize: "0.82rem",
                      fontWeight: 600,
                      cursor: "pointer",
                      textAlign: "left",
                    }}
                  >
                    <ChevronDown
                      size={12}
                      style={{
                        transform: expanded ? "rotate(0deg)" : "rotate(-90deg)",
                        transition: "transform 120ms ease",
                        flexShrink: 0,
                      }}
                    />
                    {t(cat.labelKey) || cat.label}
                    <span
                      style={{
                        marginLeft: "auto",
                        fontSize: "0.7rem",
                        color: "var(--muted)",
                        fontWeight: 400,
                      }}
                    >
                      {cat.fonts.length}
                    </span>
                  </button>
                  {expanded && (
                    <div
                      style={{
                        display: "flex",
                        flexWrap: "wrap",
                        gap: "0.3rem",
                        padding: "0.3rem 0.4rem 0.5rem 1.6rem",
                      }}
                    >
                      {cat.fonts.map((font) => {
                        const alreadySelected = selectedFonts.some(
                          (f) => f.toLowerCase() === font.toLowerCase(),
                        );
                        return (
                          <button
                            key={font}
                            type="button"
                            disabled={alreadySelected}
                            onClick={() => {
                              addFont(font);
                            }}
                            style={{
                              padding: "0.3rem 0.6rem",
                              borderRadius: "8px",
                              border: alreadySelected
                                ? "1px solid rgba(255,139,71,0.12)"
                                : "1px solid var(--line)",
                              background: alreadySelected
                                ? "rgba(255,139,71,0.06)"
                                : "rgba(255,255,255,0.02)",
                              color: alreadySelected ? "var(--muted)" : "var(--text)",
                              fontSize: "0.78rem",
                              cursor: alreadySelected ? "default" : "pointer",
                              opacity: alreadySelected ? 0.5 : 1,
                              whiteSpace: "nowrap",
                            }}
                          >
                            {font}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}

            {/* Manual input */}
            <div
              style={{
                display: "flex",
                gap: "0.35rem",
                padding: "0.4rem 0.4rem 0.2rem",
                borderTop: "1px solid var(--line)",
                marginTop: "0.3rem",
              }}
            >
              <input
                ref={inputRef}
                type="text"
                value={manualInput}
                onChange={(e) => setManualInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleManualAdd();
                  }
                }}
                placeholder={t("font.manualPlaceholder")}
                style={{
                  flex: 1,
                  padding: "0.4rem 0.6rem",
                  borderRadius: "8px",
                  border: "1px solid var(--line)",
                  background: "rgba(255,255,255,0.03)",
                  color: "var(--text)",
                  fontSize: "0.78rem",
                  outline: "none",
                }}
              />
              <button
                type="button"
                onClick={handleManualAdd}
                disabled={!manualInput.trim()}
                style={{
                  padding: "0.4rem 0.65rem",
                  borderRadius: "8px",
                  border: "1px solid rgba(255,139,71,0.24)",
                  background: "rgba(255,139,71,0.1)",
                  color: "var(--accent)",
                  fontSize: "0.78rem",
                  fontWeight: 600,
                  cursor: manualInput.trim() ? "pointer" : "not-allowed",
                  opacity: manualInput.trim() ? 1 : 0.4,
                  whiteSpace: "nowrap",
                }}
              >
                {t("font.add")}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Preview of output */}
      {selectedFonts.length > 0 && (
        <span
          style={{
            fontSize: "0.72rem",
            color: "var(--muted)",
            fontFamily: "var(--mono)",
            wordBreak: "break-all",
            opacity: 0.7,
          }}
        >
          font-family: {joinFontStack(selectedFonts)}
        </span>
      )}
    </div>
  );
}
