import { useState } from "react";

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

/**
 * The demo banner and the avatar menu. Both open the same "View as" list, so the banner's
 * "Switch" is a shortcut to the menu rather than a second picker.
 */
export function UserMenu() {
  const { me, personas, switchingTo, switchPersona } = useCurrentUser();
  const [open, setOpen] = useState(false);
  const role = describeRole(me);

  return (
    <>
      <p
        role="status"
        aria-label="Demo identity"
        className="flex-1 truncate text-[13px] text-muted-foreground"
      >
        {switchingTo ? "Switching to" : "Viewing as"}{" "}
        <span className="font-medium text-foreground">
          {switchingTo ? `${switchingTo.name}…` : `${me.name} (${role})`}
        </span>{" "}
        · demo mode ·{" "}
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="font-medium text-primary underline underline-offset-4"
        >
          Switch
        </button>
      </p>
      <DropdownMenu open={open} onOpenChange={setOpen}>
        <DropdownMenuTrigger
          aria-label={`Account: ${me.name}`}
          className="flex items-center gap-2.5 rounded-md px-1.5 py-1 text-left hover:bg-muted"
        >
          <Avatar>
            <AvatarFallback>{initials(me.name)}</AvatarFallback>
            <AvatarBadge className="bg-status-active" />
          </Avatar>
          <span className="hidden leading-tight md:block">
            <span className="block text-[13px] font-medium">{me.name}</span>
            <span className="block text-[12px] text-muted-foreground">{role}</span>
          </span>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-60">
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
    </>
  );
}
