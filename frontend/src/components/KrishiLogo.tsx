import React from 'react';
import { Sprout } from 'lucide-react';

interface KrishiLogoProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  variant?: 'default' | 'white' | 'minimal';
  className?: string;
}

const KrishiLogo: React.FC<KrishiLogoProps> = ({ 
  size = 'md', 
  variant = 'default',
  className = '' 
}) => {
  const sizeClasses = {
    sm: 'w-6 h-6',
    md: 'w-8 h-8', 
    lg: 'w-12 h-12',
    xl: 'w-16 h-16'
  };

  const iconSizes = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
    lg: 'w-6 h-6', 
    xl: 'w-8 h-8'
  };

  const variants = {
    default: {
      container: 'bg-gradient-to-br from-emerald-500 via-green-500 to-teal-600 shadow-lg',
      icon: 'text-white'
    },
    white: {
      container: 'bg-white shadow-md border border-emerald-200',
      icon: 'text-emerald-600'
    },
    minimal: {
      container: 'bg-emerald-50',
      icon: 'text-emerald-600'
    }
  };

  const variantStyles = variants[variant];

  return (
    <div className={`
      ${sizeClasses[size]} 
      ${variantStyles.container}
      rounded-full 
      flex items-center justify-center 
      transition-all duration-200
      ${className}
    `}>
      <Sprout className={`${iconSizes[size]} ${variantStyles.icon} drop-shadow-sm`} />
    </div>
  );
};

export default KrishiLogo;
