import CuelumeSounds from "../../components/CuelumeSounds";
import FooterGradient from "../../components/FooterGradient";
import OnboardingForm from "@/components/OnboardingForm";
import { currentUser } from "@/lib/auth";
import { redirect } from "next/navigation";
import Link from "next/link";

export const instant = false;
export default async function GetStarted() {
  if (!await currentUser()) redirect("/");
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-white px-6">
      <CuelumeSounds />
      <nav aria-label="Main navigation" className="absolute inset-x-0 top-0 z-10 flex items-center justify-between px-6 py-5">
        <span className="text-base font-medium tracking-tight text-[#171717]">Opencall</span>
        <Link href="/" className="home-pill home-pill-quiet nav-back" data-cuelume-tap="">Back</Link>
      </nav>
      <OnboardingForm />
      <FooterGradient />
    </main>
  );
}
