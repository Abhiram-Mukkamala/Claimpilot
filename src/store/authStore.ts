import { useState, useEffect } from 'react';
import {  User, Role  } from '../types/auth';

const AGENT_EMAIL = 'agent@claimpilot.ai';

class AuthStore {
  private user: User | null = null;
  private listeners: Set<(user: User | null) => void> = new Set();

  constructor() {
    const stored = sessionStorage.getItem('auth_user');
    if (stored) {
      try {
        this.user = JSON.parse(stored);
      } catch (e) {
        // ignore
      }
    }
  }

  getUser(): User | null {
    return this.user;
  }

  login(email: string, name: string, phone?: string, dob?: string) {
    const role: Role = email.toLowerCase() === AGENT_EMAIL ? 'agent' : 'customer';
    this.user = {
      id: Math.random().toString(36).substring(7),
      email,
      name,
      phone,
      dob,
      role
    };
    sessionStorage.setItem('auth_user', JSON.stringify(this.user));
    this.notify();
  }

  logout() {
    this.user = null;
    sessionStorage.removeItem('auth_user');
    this.notify();
  }

  subscribe(listener: (user: User | null) => void) {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private notify() {
    this.listeners.forEach(l => l(this.user));
  }
}

export const authStore = new AuthStore();

export function useAuth() {
  const [user, setUser] = useState<User | null>(authStore.getUser());

  useEffect(() => {
    return authStore.subscribe(setUser);
  }, []);

  return {
    user,
    login: (email: string, name: string, phone?: string, dob?: string) => authStore.login(email, name, phone, dob),
    logout: () => authStore.logout()
  };
}
