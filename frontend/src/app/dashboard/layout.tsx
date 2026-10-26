import { redirect } from "next/navigation";
import { currentUser } from "@/lib/auth";
import Logout from "./logout";

// Validate the session before rendering this local workspace.
export const instant = false;

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const user = await currentUser();
  if (!user) redirect("/login");
  return <>
    <header className="flex items-center justify-between border-b border-[#dfe5d9] bg-[#f6f8f3] px-6 py-3 text-[#29382e]">
      <p className="text-sm">{user.display_name}</p>
      <Logout />
    </header>
    {children}
  </>;
}
