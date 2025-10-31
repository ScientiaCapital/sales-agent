import { Card, CardContent, CardHeader } from "./card"
import { Badge } from "./badge"
import { cn } from "../../lib/utils"
import type { LucideIcon } from "lucide-react"

interface MetricsCardProps {
  title: string
  value: string | number
  description?: string
  icon?: LucideIcon
  trend?: {
    value: string
    isPositive: boolean
  }
  iconColor?: string
  className?: string
}

export function MetricsCard({
  title,
  value,
  description,
  icon: Icon,
  trend,
  iconColor = "bg-blue-50 text-blue-600",
  className,
}: MetricsCardProps) {
  return (
    <Card className={cn("", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          {Icon && (
            <div className={cn("p-2 rounded-md", iconColor)}>
              <Icon className="h-5 w-5" />
            </div>
          )}
          {trend && (
            <Badge 
              variant={trend.isPositive ? "success" : "destructive"}
              className="text-xs"
            >
              {trend.value}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-1">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{title}</p>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          {description && (
            <p className="text-sm text-gray-500">{description}</p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
