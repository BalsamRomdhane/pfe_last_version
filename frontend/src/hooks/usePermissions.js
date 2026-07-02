/**
 * usePermissions — centralized RBAC hook.
 *
 * Single source of truth for all role-based checks in the frontend.
 * Import this hook anywhere instead of writing `user?.role === 'ADMIN'` inline.
 */
import { useContext } from 'react';
import { UserContext } from '../context/UserContext';

// ── Role constants ────────────────────────────────────────────────────────────
export const ROLES = {
  ADMIN:    'ADMIN',
  TEAMLEAD: 'TEAMLEAD',
  EMPLOYEE: 'EMPLOYEE',
};

// ── Permission → roles mapping ────────────────────────────────────────────────
const PERMISSIONS = {
  ADMIN: [
    'users.manage',
    'departments.manage',
    'normes.write',
    'normes.read',
    'validations.submit',
    'documents.review',
    'documents.all',
    'evidence.view',
    'evidence.rebuild',
    'compliance.view',
    'compliance.refresh',
    'ai.view',
    'ai.mlops',
    'security.view',
    'system.view',
    'ml.train',
    'ml.manage',
    'dataset.manage',
    'mlops.manage',
    'settings.manage',
  ],
  TEAMLEAD: [
    'normes.read',
    'validations.submit',
    'documents.review',
    'documents.all',
    'evidence.view',
    'compliance.view',
    'ai.view',
    'ai.mlops',
    'security.view',
    // Note: 'system.view' intentionally REMOVED — System page is ADMIN only
    // Note: 'compliance.refresh' intentionally REMOVED — POST /compliance-os/refresh/ is ADMIN only
  ],
  EMPLOYEE: [
    'documents.upload',
    'documents.own',
    'profile.view',
    'notifications.own',
  ],
};

// ── Hook ──────────────────────────────────────────────────────────────────────
export function usePermissions() {
  const { user } = useContext(UserContext);
  const role = user?.role || '';

  /**
   * Returns true if the current role has the given permission.
   * @param {string} permission
   */
  const can = (permission) =>
    Boolean((PERMISSIONS[role] || []).includes(permission));

  /**
   * Returns true if the current role is one of the provided roles.
   * @param {...string} roles
   */
  const hasRole = (...roles) => roles.includes(role);

  return {
    role,
    isAdmin:           role === ROLES.ADMIN,
    isTeamLead:        role === ROLES.TEAMLEAD,
    isEmployee:        role === ROLES.EMPLOYEE,
    isAdminOrTeamLead: role === ROLES.ADMIN || role === ROLES.TEAMLEAD,
    can,
    hasRole,
  };
}

export default usePermissions;
