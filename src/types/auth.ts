export type Role = 'customer' | 'agent';

export interface User {
  id: string;
  email: string;
  name: string;
  role: Role;
  phone?: string;
  dob?: string;
}
