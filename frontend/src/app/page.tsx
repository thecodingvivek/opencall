import Glass from "../components/Glass";

export default function Home() {
  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-white">
      <Glass size={320} audioEnabled={false} followCursor={false} />
    </div>
  );
}
