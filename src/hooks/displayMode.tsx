import { useEffect, useState } from "react";
import { call } from "@decky/api";

export function DisplayMode(): string | null {
  const [mode, setMode] = useState<string | null>(null);

  useEffect(() => {
    const fetch = async () => {
      const result = await call<[], string>("get_display_mode");
      setMode(result);
    };
    fetch();
  }, []);

  return mode;
}
