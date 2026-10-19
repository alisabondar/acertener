import { ChevronDown } from "lucide-react";

import { useCurrentUser } from "@/auth/context";
import { describeRole, initials } from "@/auth/roles";
import { Avatar, AvatarBadge, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

/** Who you're acting as, and the "View as" list to change it: one control. */
export function UserMenu() {
  const { me, personas, switchingTo, switchPersona } = useCurrentUser();
  const role = describeRole(me);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="ml-auto flex items-center gap-2.5 rounded-lg px-2 py-1 text-left hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring">
        <Avatar aria-hidden>
          <AvatarFallback>{initials(me.name)}</AvatarFallback>
          <AvatarBadge className="bg-status-active" />
        </Avatar>
        <span className="leading-tight">
          <span className="block text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
            {switchingTo ? "Switching to" : "Viewing as"}
          </span>{" "}
          <span className="block text-[14px] font-semibold">
            {switchingTo ? `${switchingTo.name}…` : `${me.name} (${role})`}
          </span>
        </span>
        <ChevronDown className="size-4 text-muted-foreground" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel>View as</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={me.id} onValueChange={(id) => void switchPersona(id)}>
          {personas.map((persona) => (
            <DropdownMenuRadioItem key={persona.id} value={persona.id}>
              <span className="leading-tight">
                <span className="block">{persona.name}</span>
                <span className="block text-[12px] text-muted-foreground">
                  {describeRole(persona)}
                </span>
              </span>
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
