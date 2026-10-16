// src/store/authStore.ts

import { useState, useEffect } from 'react';
import { User, Role } from '../types/auth';
import { API_BASE_URL } from '../services/claimsApi';

const AGENT_EMAIL = 'agent@claimpilot.ai';

class AuthStore {
  private user: User | null = null;
  private listeners: Set<(user: User | null) => void> = new Set();

  constructor() {
    const stored = localStorage.getItem('auth_user');
    if (stored) {
      try {
        this.user = JSON.parse(stored);
      } catch (e) {
        // ignore invalid JSON
      }
    }
  }

  getUser(): User | null {
    return this.user;
  }

  getToken(): string | null {
    return localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
  }

  /**
   * Step 1: Authenticate with Email & Password.
   */
  async authenticateWithBackend(
    email: string,
    pass: string
  ): Promise<{ requires_otp?: boolean; email?: string; otp_details?: any; user?: User; access_token?: string }> {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        email: email,
        password: pass,
      }),
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(
        data.detail?.message || data.detail || data.message || 'Invalid email or password'
      );
    }

    if (data.requires_otp) {
      return {
        requires_otp: true,
        email: data.email || email,
        otp_details: data.otp_details
      };
    }

    if (!data.access_token || !data.user) {
      throw new Error('Invalid authentication response from server');
    }

    const userObj: User = {
      ...data.user,
      role: data.user.role,
    };

    this.setUserSession(userObj, data.access_token);
    return { user: userObj, access_token: data.access_token };
  }

  login(email: string, name: string, phone?: string, dob?: string, token?: string) {
    if (!token) {
      console.warn('[AUTH STORE] Live auth requires valid backend access token');
      return;
    }
    const role: Role = email.toLowerCase() === AGENT_EMAIL ? 'agent' : 'customer';
    this.user = {
      id: Math.random().toString(36).substring(7),
      email,
      name,
      phone,
      dob,
      role
    };
    localStorage.setItem('auth_user', JSON.stringify(this.user));
    localStorage.setItem('access_token', token);
    sessionStorage.setItem('access_token', token);
    this.notify();
  }

  setUserSession(user: User, token?: string) {
    this.user = user;
    localStorage.setItem('auth_user', JSON.stringify(this.user));
    if (token) {
      localStorage.setItem('access_token', token);
      sessionStorage.setItem('access_token', token);
    }
    this.notify();
  }

  logout() {
    this.user = null;
    localStorage.removeItem('auth_user');
    localStorage.removeItem('access_token');
    sessionStorage.removeItem('access_token');
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

// EXPORT THE MISSING useAuth HOOK FOR COMPONENTS (CustomerLayout, Navbar, etc.)
export function useAuth() {
  const [user, setUser] = useState<User | null>(authStore.getUser());

  useEffect(() => {
    return authStore.subscribe(setUser);
  }, []);

  return {
    user,
    token: authStore.getToken(),
    login: (email: string, name: string, phone?: string, dob?: string, token?: string) =>
      authStore.login(email, name, phone, dob, token),
    logout: () => authStore.logout()
  };
}