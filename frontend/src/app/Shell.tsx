import { CalendarDays, LoaderCircle, ScrollText, UserPlus, Users } from "lucide-react";
import { Suspense } from "react";
import { Link, Outlet, useLocation } from "react-router";

import { type Permission, useCurrentUser } from "@/auth/context";
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

import { UserMenu } from "./UserMenu";

/**
 * Each section owns its paths ("Patients" covers the list and charts, not registration) and is
 * shown only to roles with its permission.
 */
const NAV: {
  to: string;
  label: string;
  /** Shown while a persona switch loads this section. */
  loading: string;
  icon: typeof Users;
  permission: Permission;
  owns: (path: string) => boolean;
}[] = [
  {
    to: "/",
    label: "My day",
    loading: "Loading your day",
    icon: CalendarDays,
    permission: "SCHEDULE_VISITS",
    owns: (path: string) => path === "/",
  },
  {
    to: "/patients",
    label: "Patients",
    loading: "Loading your patients",
    icon: Users,
    permission: "VIEW_DEMOGRAPHICS",
    owns: (path: string) => path === "/patients" || /^\/patients\/(?!new$)[^/]+/.test(path),
  },
  {
    to: "/patients/new",
    label: "New patient",
    loading: "Loading registration",
    icon: UserPlus,
    permission: "CREATE_PATIENT",
    owns: (path: string) => path === "/patients/new",
  },
  {
    to: "/admin/audit",
    label: "Admin",
    loading: "Loading the audit log",
    icon: ScrollText,
    permission: "VIEW_AUDIT_LOG",
    owns: (path: string) => path.startsWith("/admin"),
  },
];

export function Shell() {
  const { pathname } = useLocation();
  const path = pathname.replace(/(.)\/+$/, "$1");
  const { me, switchingTo } = useCurrentUser();
  const sections = NAV.filter((item) => me.permissions.includes(item.permission));
  return (
    <TooltipProvider>
      <SidebarProvider>
        <Sidebar collapsible="icon">
          <SidebarHeader className="flex-row items-center justify-between px-3 py-3 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-2">
            <span className="truncate px-1 text-[15px] font-semibold group-data-[collapsible=icon]:hidden">
              Acertener
            </span>
            <SidebarTrigger className="text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground" />
          </SidebarHeader>
          <SidebarContent>
            <SidebarGroup>
              <nav aria-label="Main">
                <SidebarMenu>
                  {sections.map(({ to, label, icon: Icon, owns }) => {
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
          <header className="flex h-14 items-center gap-3 border-b border-border px-4">
            <UserMenu />
          </header>
          <div className="mx-auto w-full max-w-7xl px-8 py-6">
            {switchingTo ? (
              <SwitchingPersona
                message={NAV.find((item) => item.owns(path))?.loading ?? "Loading"}
                personaName={switchingTo.name}
              />
            ) : (
              <Suspense fallback={<PageLoading />}>
                <Outlet />
              </Suspense>
            )}
          </div>
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  );
}

/** Stands in for the page while a persona switch loads, so nothing from the last one shows. */
function SwitchingPersona({ message, personaName }: { message: string; personaName: string }) {
  return (
    <div
      role="status"
      aria-label="Loading"
      className="flex flex-col items-center justify-center gap-3 py-24 text-center duration-300 animate-in fade-in"
    >
      <LoaderCircle className="size-6 animate-spin text-muted-foreground" aria-hidden />
      <p className="text-[15px] font-medium">
        {message} <span className="text-muted-foreground">as {personaName}</span>
      </p>
    </div>
  );
}

/** While a page's code downloads on first visit. */
function PageLoading() {
  return (
    <div role="status" aria-label="Loading page" className="flex justify-center py-24">
      <LoaderCircle className="size-6 animate-spin text-muted-foreground" aria-hidden />
    </div>
  );
}
