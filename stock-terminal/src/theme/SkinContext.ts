import { createContext, useContext } from "react";
import { skinList, type SkinId } from "./skins";

export interface SkinContextValue {
  skinId: SkinId;
  setSkin: (skin: SkinId) => void;
  skins: typeof skinList;
}

export const SkinContext = createContext<SkinContextValue | null>(null);

export function useSkin() {
  const value = useContext(SkinContext);
  if (!value) throw new Error("useSkin must be used inside ThemeProvider");
  return value;
}
