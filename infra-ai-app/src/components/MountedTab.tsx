import { cn } from "@/lib/utils";

interface MountedTabProps {
  active: boolean;
  children: React.ReactNode;
}

export function MountedTab({ active, children }: MountedTabProps) {
  return <div className={cn("h-full", !active && "hidden")}>{children}</div>;
}
