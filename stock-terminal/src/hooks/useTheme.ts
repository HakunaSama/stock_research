import { useSkin } from "@/theme/SkinContext";

// 兼容旧调用方；主题状态的唯一数据源已经收敛到 ThemeProvider。
export function useTheme() {
  const { skinId, setSkin } = useSkin();
  const isDark = skinId === "midnight";

  return {
    theme: isDark ? "dark" as const : "light" as const,
    toggleTheme: () => setSkin(isDark ? "flow" : "midnight"),
    isDark,
  };
}
