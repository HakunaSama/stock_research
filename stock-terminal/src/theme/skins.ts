import { theme, type ThemeConfig } from "antd";

export type SkinId = "flow" | "midnight";

export interface SkinDefinition {
  id: SkinId;
  label: string;
  colorScheme: "light" | "dark";
  tokens: Record<`--${string}`, string>;
  antd: ThemeConfig;
}

const components: ThemeConfig["components"] = {
  Button: {
    primaryShadow: "inset 0 -6px 20px color-mix(in srgb, var(--accent) 32%, transparent)",
  },
  Card: { paddingLG: 14, headerHeight: 40 },
  Tabs: { horizontalMargin: "0" },
  Table: { cellPaddingBlockSM: 6, cellPaddingInlineSM: 8 },
};

export const skins: Record<SkinId, SkinDefinition> = {
  flow: {
    id: "flow",
    label: "流光紫",
    colorScheme: "light",
    tokens: {
      "--bg-space": "#f5f4fb",
      "--bg-panel": "#ffffff",
      "--bg-panel-2": "#fbfbfe",
      "--bg-elevated": "#f3f2fa",
      "--bg-inset": "#f1f0f9",
      "--border-subtle": "#eae8f4",
      "--border-strong": "#d9d6ec",
      "--text-primary": "#11023b",
      "--text-secondary": "#45446b",
      "--text-muted": "#8b89a6",
      "--accent": "#8247ff",
      "--accent-hover": "#6f32ee",
      "--accent-dim": "rgba(130, 71, 255, 0.1)",
      "--up": "#e5484d",
      "--up-dim": "rgba(229, 72, 77, 0.1)",
      "--down": "#00a05a",
      "--down-dim": "rgba(0, 160, 90, 0.1)",
      "--blue": "#3e63dd",
      "--blue-dim": "rgba(62, 99, 221, 0.1)",
      "--amber": "#d97706",
      "--amber-dim": "rgba(217, 119, 6, 0.12)",
      "--favorite": "#d4a017",
      "--violet": "#8247ff",
      "--chart-grid": "#eae8f4",
      "--chart-axis": "#8b89a6",
      "--chart-cross": "#45446b",
      "--chart-ma5": "#8247ff",
      "--chart-ma20": "#3e63dd",
      "--chart-ma60": "#d97706",
      "--chart-label-bg": "#11023b",
      "--chart-label-text": "#ffffff",
      "--surface-glow-a": "rgba(130, 71, 255, 0.07)",
      "--surface-glow-b": "rgba(130, 71, 255, 0.06)",
      "--surface-dot": "rgba(17, 2, 59, 0.06)",
      "--shadow-card": "0 1px 2px rgba(34, 6, 109, 0.05), 0 8px 24px -8px rgba(34, 6, 109, 0.08)",
      "--shadow-pop": "0 8px 20px rgba(34, 6, 109, 0.08), 0 24px 56px -16px rgba(34, 6, 109, 0.22)",
    },
    antd: {
      algorithm: theme.defaultAlgorithm,
      token: {
        colorPrimary: "#8247ff", colorInfo: "#3e63dd", colorSuccess: "#00a05a",
        colorError: "#e5484d", colorWarning: "#d97706", colorBgBase: "#ffffff",
        colorBgContainer: "#ffffff", colorBgElevated: "#ffffff", colorBgLayout: "#f5f4fb",
        colorBorder: "#d9d6ec", colorBorderSecondary: "#eae8f4", colorText: "#11023b",
        colorTextSecondary: "#45446b", colorTextTertiary: "#8b89a6", borderRadius: 10,
        fontSize: 13, fontFamily: "'Inter', 'Noto Sans SC', sans-serif",
      },
      components: { ...components, Segmented: { trackBg: "#f1f0f9" } },
    },
  },
  midnight: {
    id: "midnight",
    label: "深海夜盘",
    colorScheme: "dark",
    tokens: {
      "--bg-space": "#080d18",
      "--bg-panel": "#101827",
      "--bg-panel-2": "#0d1421",
      "--bg-elevated": "#172235",
      "--bg-inset": "#0a111d",
      "--border-subtle": "#202d42",
      "--border-strong": "#34445d",
      "--text-primary": "#eef4ff",
      "--text-secondary": "#b6c2d7",
      "--text-muted": "#74839c",
      "--accent": "#8b7cff",
      "--accent-hover": "#a196ff",
      "--accent-dim": "rgba(139, 124, 255, 0.15)",
      "--up": "#ff6570",
      "--up-dim": "rgba(255, 101, 112, 0.13)",
      "--down": "#22c77a",
      "--down-dim": "rgba(34, 199, 122, 0.13)",
      "--blue": "#6ea8ff",
      "--blue-dim": "rgba(110, 168, 255, 0.13)",
      "--amber": "#f0ad4e",
      "--amber-dim": "rgba(240, 173, 78, 0.14)",
      "--favorite": "#ffd166",
      "--violet": "#8b7cff",
      "--chart-grid": "#202d42",
      "--chart-axis": "#74839c",
      "--chart-cross": "#b6c2d7",
      "--chart-ma5": "#9d91ff",
      "--chart-ma20": "#6ea8ff",
      "--chart-ma60": "#f0ad4e",
      "--chart-label-bg": "#eef4ff",
      "--chart-label-text": "#080d18",
      "--surface-glow-a": "rgba(139, 124, 255, 0.08)",
      "--surface-glow-b": "rgba(50, 125, 255, 0.06)",
      "--surface-dot": "rgba(182, 194, 215, 0.05)",
      "--shadow-card": "0 1px 2px rgba(0, 0, 0, 0.2), 0 14px 30px -14px rgba(0, 0, 0, 0.55)",
      "--shadow-pop": "0 18px 50px rgba(0, 0, 0, 0.55)",
    },
    antd: {
      algorithm: theme.darkAlgorithm,
      token: {
        colorPrimary: "#8b7cff", colorInfo: "#6ea8ff", colorSuccess: "#22c77a",
        colorError: "#ff6570", colorWarning: "#f0ad4e", colorBgBase: "#080d18",
        colorBgContainer: "#101827", colorBgElevated: "#172235", colorBgLayout: "#080d18",
        colorBorder: "#34445d", colorBorderSecondary: "#202d42", colorText: "#eef4ff",
        colorTextSecondary: "#b6c2d7", colorTextTertiary: "#74839c", borderRadius: 10,
        fontSize: 13, fontFamily: "'Inter', 'Noto Sans SC', sans-serif",
      },
      components: { ...components, Segmented: { trackBg: "#0a111d" } },
    },
  },
};

export const skinList = Object.values(skins);
