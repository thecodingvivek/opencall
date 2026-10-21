/** Convert the browser's recording container to mono 16 kHz PCM WAV for Gnani. */
export async function recordingToWav(recording: Blob): Promise<Blob> {
  const context = new AudioContext();
  let decoded: AudioBuffer;
  try {
    decoded = await context.decodeAudioData(await recording.arrayBuffer());
  } finally {
    await context.close();
  }
  if (decoded.duration <= 0 || decoded.duration > 60) {
    throw new Error("Please record up to 55 seconds of speech and try again.");
  }
  const renderer = new OfflineAudioContext(1, Math.ceil(decoded.duration * 16000), 16000);
  const source = renderer.createBufferSource();
  source.buffer = decoded;
  source.connect(renderer.destination);
  source.start();
  const rendered = await renderer.startRendering();
  const samples = rendered.getChannelData(0);
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const text = (offset: number, value: string) => {
    for (let i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i));
  };
  text(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  text(8, "WAVE");
  text(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, 16000, true);
  view.setUint32(28, 32000, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  text(36, "data");
  view.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    const sample = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(44 + i * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}
