import { CalendarDays, ScrollText, UserPlus, Users } from "lucide-react";
import { Link, Outlet, useLocation } from "react-router";

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";

/** Each section owns its paths; "Patients" covers the list and charts, not registration. */
const NAV = [
  { to: "/", label: "My day", icon: CalendarDays, owns: (path: string) => path === "/" },
  {
    to: "/patients",
    label: "Patients",
    icon: Users,
    owns: (path: string) => path === "/patients" || /^\/patients\/(?!new$)[^/]+/.test(path),
  },
  {
    to: "/patients/new",
    label: "New patient",
    icon: UserPlus,
    owns: (path: string) => path === "/patients/new",
  },
  {
    to: "/admin/audit",
    label: "Admin",
    icon: ScrollText,
    owns: (path: string) => path.startsWith("/admin"),
  },
];

export function Shell() {
  const { pathname } = useLocation();
  const path = pathname.replace(/(.)\/+$/, "$1");
  return (
    <TooltipProvider>
      <SidebarProvider>
        <Sidebar collapsible="icon">
          <SidebarHeader className="px-4 py-4 text-[15px] font-semibold group-data-[collapsible=icon]:px-2">
            <span className="truncate group-data-[collapsible=icon]:hidden">Acertener</span>
          </SidebarHeader>
          <SidebarContent>
            <SidebarGroup>
              <nav aria-label="Main">
                <SidebarMenu>
                  {NAV.map(({ to, label, icon: Icon, owns }) => {
                    const active = owns(path);
                    return (
                      <SidebarMenuItem key={to}>
                        <SidebarMenuButton asChild isActive={active} tooltip={label}>
                          <Link to={to} aria-current={active ? "page" : undefined}>
                            <Icon />
                            <span>{label}</span>
                          </Link>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    );
                  })}
                </SidebarMenu>
              </nav>
            </SidebarGroup>
          </SidebarContent>
          <SidebarRail />
        </Sidebar>
        <SidebarInset>
          <header className="flex h-12 items-center border-b border-border px-4">
            <SidebarTrigger />
          </header>
          <div className="mx-auto w-full max-w-7xl px-8 py-6">
            <Outlet />
          </div>
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  );
}
