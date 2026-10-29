import Glass from "../components/Glass";

export default function Home() {
  return (
    <main className="flex min-h-screen w-full items-center justify-center bg-white px-6 py-12">
      <div className="flex flex-col items-center justify-center gap-4 md:flex-row md:gap-8">
        <h1 className="font-sans text-4xl font-medium tracking-[-0.06em] md:text-5xl">
          OPENCALL
        </h1>
        <Glass size={240} audioEnabled={false} followCursor={false} />
        <p className="whitespace-nowrap text-4xl tracking-[-0.03em] md:text-5xl">
          <span className="font-instrument-serif">harness</span>{" "}
          <span className="font-sans text-[0.65em] tracking-normal">and</span>{" "}
          <span className="font-instrument-serif">harvest</span>
        </p>
      </div>
    </main>
  );
}
