/**
 * RBAC Guard components.
 *
 * These components render their children ONLY when the current user has
 * the required permission or role. When the condition is NOT met, nothing
 * is added to the DOM — no disabled state, no hidden element, nothing.
 *
 * Usage:
 *   <PermissionGuard permission="normes.write">
 *     <button>Create Standard</button>
 *   </PermissionGuard>
 *
 *   <RoleGuard roles={['ADMIN']}>
 *     <AdminPanel />
 *   </RoleGuard>
 */
import React from 'react';
import { usePermissions } from '../../hooks/usePermissions';

/**
 * Renders children only when the user has the given permission.
 *
 * @param {string}      permission - Permission key from PERMISSIONS map
 * @param {ReactNode}   fallback   - Optional element to render when denied (default: null)
 * @param {ReactNode}   children   - Content to render when allowed
 */
export function PermissionGuard({ permission, fallback = null, children }) {
  const { can } = usePermissions();
  if (!can(permission)) return fallback;
  return <>{children}</>;
}

/**
 * Renders children only when the user has one of the given roles.
 *
 * @param {string[]}  roles    - Array of allowed role strings
 * @param {ReactNode} fallback - Optional element to render when denied (default: null)
 * @param {ReactNode} children - Content to render when allowed
 */
export function RoleGuard({ roles, fallback = null, children }) {
  const { hasRole } = usePermissions();
  if (!hasRole(...roles)) return fallback;
  return <>{children}</>;
}

export default PermissionGuard;
