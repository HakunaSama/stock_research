import { useEffect, useMemo, useState } from "react";
import { App as AntApp, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { skinList, skins, type SkinId } from "./skins";
import { SkinContext } from "./SkinContext";

const STORAGE_KEY = "cheese:skin";

function getInitialSkin(): SkinId {
  const saved = window.localStorage.getItem(STORAGE_KEY);
  if (saved && saved in skins) return saved as SkinId;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "midnight" : "flow";
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [skinId, setSkinId] = useState<SkinId>(getInitialSkin);
  const skin = skins[skinId];

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.skin = skin.id;
    root.style.colorScheme = skin.colorScheme;
    Object.entries(skin.tokens).forEach(([name, value]) => root.style.setProperty(name, value));
    window.localStorage.setItem(STORAGE_KEY, skin.id);
  }, [skin]);

  const value = useMemo(() => ({ skinId, setSkin: setSkinId, skins: skinList }), [skinId]);

  return (
    <SkinContext.Provider value={value}>
      <ConfigProvider locale={zhCN} theme={skin.antd}>
        <AntApp>{children}</AntApp>
      </ConfigProvider>
    </SkinContext.Provider>
  );
}
