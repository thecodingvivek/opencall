import { TryCall } from "@/components/try/TryCall";
import { currentUser } from "@/lib/auth";
import { redirect } from "next/navigation";

export const instant = false;
export default async function TryPage() {
  const user = await currentUser();
  if (!user) redirect("/");
  return <TryCall />;
}
