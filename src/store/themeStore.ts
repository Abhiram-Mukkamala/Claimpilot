import { useState, useEffect } from 'react';

type Theme = 'dark';

class ThemeStore {
  private theme: Theme = 'dark';
  private listeners: Set<(theme: Theme) => void> = new Set();

  constructor() {
    this.apply(this.theme);
  }

  get(): Theme {
    return this.theme;
  }

  toggle() {
    // Light mode removed
  }

  private apply(theme: Theme) {
    document.documentElement.setAttribute('data-theme', theme);
  }

  subscribe(listener: (theme: Theme) => void): () => void {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  }


}

export const themeStore = new ThemeStore();

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(themeStore.get());

  useEffect(() => {
    return themeStore.subscribe(setTheme);
  }, []);

  return { theme, toggleTheme: () => themeStore.toggle() };
}
