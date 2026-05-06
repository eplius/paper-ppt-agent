# SVG Technical Standards (Essential)

Core technical constraints for SVG generation. For advanced techniques (shadows, gradients, arc paths, polygon arrows), refer to `shared-standards.md` §6–§7.

---

## 1. SVG Banned Features Blacklist

The following features are **absolutely forbidden** — PPT export will break if any are used:

| Banned Feature | Description |
|----------------|-------------|
| `mask` | Masks |
| `<style>` | Embedded stylesheets |
| `class` | CSS selector attributes (`id` inside `<defs>` is legitimate) |
| External CSS | External stylesheet links |
| `<foreignObject>` | Embedded external content |
| `<symbol>` + `<use>` | Symbol reference reuse (except icon placeholders) |
| `textPath` | Text along a path |
| `@font-face` | Custom font declarations |
| `<animate*>` / `<set>` | SVG animations |
| `<script>` / event attributes | Scripts and interactivity |
| `<iframe>` | Embedded frames |

> **`marker-start` / `marker-end`** and **`clipPath` on `<image>`** are conditionally allowed — see below.

---

### 1.1 Line-end Markers (Conditionally Allowed)

`marker-start` / `marker-end` on `<line>` and `<path>` are allowed **only** when the referenced `<marker>` satisfies **all** of:

| Requirement | Reason |
|-------------|--------|
| Defined inside `<defs>` | Converter looks up marker defs via id index |
| `orient="auto"` | DrawingML arrow auto-rotates along the line tangent |
| Shape is triangle / diamond / oval | Other shapes are silently dropped |
| Child `fill` matches parent line `stroke` | Inherited in DrawingML — mismatch looks wrong |
| `markerWidth` / `markerHeight` in `3–15` range | Mapped to sm/med/lg size buckets |

**Template**:
```xml
<defs>
  <marker id="arrowHead" markerWidth="10" markerHeight="10" refX="9" refY="5"
          orient="auto" markerUnits="strokeWidth">
    <path d="M0,0 L10,5 L0,10 Z" fill="#1976D2"/>
  </marker>
</defs>
<line x1="100" y1="200" x2="400" y2="200" stroke="#1976D2" stroke-width="3"
      marker-end="url(#arrowHead)"/>
```

For block/chunky arrows, use standalone `<polygon>` instead of `marker`.

---

### 1.2 Image Clipping (Conditionally Allowed)

`clip-path` on `<image>` is allowed when the `<clipPath>` contains a **single** shape child (`<circle>`, `<rect rx>`, `<path>`, `<polygon>`). **Only on `<image>` elements** — never on shapes or groups.

---

## 2. PPT Compatibility Alternatives

| Banned | Correct Alternative |
|--------|---------------------|
| `fill="rgba(255,255,255,0.1)"` | `fill="#FFFFFF" fill-opacity="0.1"` |
| `<g opacity="0.2">...</g>` | Set `fill-opacity` / `stroke-opacity` on each child |
| `<image opacity="0.3"/>` | Overlay `<rect fill="bg-color" opacity="0.7"/>` after the image |

**Mnemonic**: PPT does not recognize rgba, group opacity, or image opacity.

---

## 3. Canvas Format Quick Reference

| Format | viewBox | Dimensions |
|--------|---------|------------|
| PPT 16:9 | `0 0 1280 720` | 1280x720 |
| PPT 4:3 | `0 0 1024 768` | 1024x768 |

---

## 4. Basic SVG Rules

- **viewBox** must match canvas dimensions
- **Background**: Use `<rect>` for page background
- **Line breaks**: Use `<tspan>`; `<foreignObject>` is FORBIDDEN
- **Fonts**: System fonts only (Microsoft YaHei, Arial, Calibri); `@font-face` is FORBIDDEN
- **Styles**: Inline only (`fill="..."` `font-size="..."`); `<style>` / `class` are FORBIDDEN
- **Colors**: HEX values; transparency via `fill-opacity` / `stroke-opacity`
- **Images**: `<image href="../images/xxx.png" preserveAspectRatio="xMidYMid slice"/>`
- **Icons**: `<use data-icon="library/name" x="" y="" width="48" height="48" fill="#HEX"/>`. **One presentation = one library — never mix.**

### Element Grouping (Mandatory)

Logically related elements **MUST** be wrapped in `<g>` tags for PowerPoint grouping.

> ⚠️ **Only `<g opacity="...">` is banned.** Plain `<g>` for structure is required.

| Group | Contains |
|-------|----------|
| Card / panel | Background rect + shadow + icon + title + body |
| Process step | Number circle + icon + label + description |
| List item | Bullet + icon + title + description |
| Page header | Title + subtitle + accent decoration |
| Page footer | Page number + branding |

Use descriptive `id` attributes (e.g. `card-1`, `step-discover`, `header`, `footer`).

---

## 5. Post-processing Pipeline (3 Steps)

Must be executed in order:

```bash
# 1. Split speaker notes into per-page files
python3 scripts/total_md_split.py <project_path>

# 2. SVG post-processing (icon embed, image crop, text flatten, rounded rect → path)
python3 scripts/finalize_svg.py <project_path>

# 3. Export PPTX (from svg_final/)
python3 scripts/svg_to_pptx.py <project_path> -s final
```

**Prohibited**: NEVER use `cp` as substitute for `finalize_svg.py`. NEVER export from `svg_output/` — MUST use `svg_final/`.

**Re-run rule**: Any modification to `svg_output/` after post-processing requires re-running Steps 2 and 3.

---

## 6. Project Directory Structure

```
project/
├── svg_output/    # Raw SVGs (Executor output)
├── svg_final/     # Post-processed SVGs (finalize_svg.py output)
├── images/        # Image assets
├── notes/         # Speaker notes (.md files matching SVG names)
│   └── total.md   # Complete speaker notes (before splitting)
├── templates/     # Project templates
└── *.pptx         # Exported PPT file
```
