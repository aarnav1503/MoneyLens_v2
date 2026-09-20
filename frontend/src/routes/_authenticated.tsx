import { createFileRoute, Outlet, redirect } from "@tanstack/react-router";
import { supabase } from "@/integrations/supabase/client";

export const Route = createFileRoute("/_authenticated")({
  ssr: false,
  beforeLoad: async ({ location }) => {
    // 1. Try Supabase session (preferred - provides real user.id)
    try {
      const { data } = await supabase.auth.getUser();
      if (data?.user) return; // ✅ Real authenticated session
    } catch {
      // Supabase unreachable (network issue, local dev, etc.) — allow localStorage fallback
    }

    // 2. Fallback: check for localStorage session (set by auth-fields.tsx on login)
    const localUser = typeof window !== "undefined"
      ? localStorage.getItem("moneylens_user")
      : null;

    if (localUser) {
      return; // ✅ Local session exists
    }

    // 3. No session at all — redirect to login
    throw redirect({ to: "/login", search: { next: location.href } });
  },
  component: () => <Outlet />,
});