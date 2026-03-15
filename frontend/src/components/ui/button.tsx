import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cn } from "@/lib/utils"

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  asChild?: boolean
  variant?: 'default' | 'outline' | 'ghost' | 'link' | 'secondary'
  size?: 'default' | 'sm' | 'lg' | 'icon'
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'default', asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    
    // Simplistic cva implementation for tailwindcss styling
    let variantStyles = "bg-primary-700 text-white hover:bg-primary-800 shadow-sm"
    if (variant === 'outline') {
      variantStyles = "border border-neutral-300 bg-transparent hover:bg-neutral-100 text-neutral-900"
    } else if (variant === 'ghost') {
      variantStyles = "hover:bg-neutral-100 hover:text-neutral-900 text-neutral-700 bg-transparent"
    } else if (variant === 'secondary') {
      variantStyles = "bg-primary-100 text-primary-900 hover:bg-primary-200"
    } else if (variant === 'link') {
      variantStyles = "text-primary-700 underline-offset-4 hover:underline bg-transparent"
    }

    let sizeStyles = "h-10 px-4 py-2"
    if (size === 'sm') sizeStyles = "h-8 rounded-md px-3 text-xs"
    else if (size === 'lg') sizeStyles = "h-12 rounded-md px-8"
    else if (size === 'icon') sizeStyles = "h-9 w-9"

    return (
      <Comp
        className={cn(
          "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary-700 disabled:pointer-events-none disabled:opacity-50",
          variantStyles,
          sizeStyles,
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button }
