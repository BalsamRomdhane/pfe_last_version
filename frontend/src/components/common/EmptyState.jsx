import React from 'react';
import { FileX, Search, Database } from 'lucide-react';

const ICONS = {
  default:  FileX,
  search:   Search,
  data:     Database,
};

const EmptyState = ({
  icon = 'default',
  title = 'No data found',
  description = '',
  action = null,
  className = '',
}) => {
  const Icon = (typeof icon === 'string' ? ICONS[icon] : icon) || ICONS.default;

  return (
    <div className={`empty-state ${className}`}>
      <div className="empty-state-icon">
        <Icon size={22} />
      </div>
      <div>
        <p className="empty-state-title">{title}</p>
        {description && <p className="empty-state-body mt-1">{description}</p>}
      </div>
      {action}
    </div>
  );
};

export default EmptyState;
