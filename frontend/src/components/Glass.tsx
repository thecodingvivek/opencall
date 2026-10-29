"use client";


import { useEffect, useRef } from "react";

export type GlassPalette = { name: string; top: string; bottom: string; accent: string };

export const defaultGlassPalettes: GlassPalette[] = [
  { name: "Lagoon", top: "#48ddbe", bottom: "#1744a0", accent: "#e5ef9d" },
  { name: "Sunset", top: "#ffad55", bottom: "#c92968", accent: "#f6dbbc" },
  { name: "Aurora", top: "#8ee6c5", bottom: "#5420ad", accent: "#bdacf5" },
  { name: "Candy", top: "#f7a3cd", bottom: "#6850ca", accent: "#ffdab6" },
  { name: "Ember", top: "#ffc369", bottom: "#b73223", accent: "#eb8da2" },
  { name: "Arctic", top: "#91dfe8", bottom: "#3158b3", accent: "#e4e6fa" },
];

type GlassProps = {
  palettes?: GlassPalette[];
  initialPalette?: string;
  /** Custom liquid colors, as six-digit hex values. */
  colors?: Pick<GlassPalette, "top" | "bottom" | "accent">;
  /** Set to false to remove the microphone controls and audio processing. */
  audioEnabled?: boolean;
  /** Set to false to keep the camera fixed when the cursor moves. */
  followCursor?: boolean;
  /** Orb and canvas diameter in CSS pixels. */
  size?: number;
};

export default function Glass({ palettes = defaultGlassPalettes, initialPalette, colors, audioEnabled = false, followCursor = true, size = 320 }: GlassProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const errorRef = useRef<HTMLParagraphElement>(null);
  const microphoneRef = useRef<HTMLButtonElement>(null);
  const statusRef = useRef<HTMLParagraphElement>(null);
  const palettesRef = useRef(palettes);
  palettesRef.current = palettes.length ? palettes : defaultGlassPalettes;
  useEffect(() => {

    let dispose = () => {};
    const events = new AbortController();
    const canvas = canvasRef.current!;
    const error = errorRef.current!;
    if (!canvas || !error) return;
    const gl = canvas.getContext('webgl', { alpha: true, antialias: false, depth: false });

    function fail(message: string) {
      error.textContent = message;
      error.hidden = false;
    }

    function start(gl: WebGLRenderingContext) {
      // Trace rays through an actual 3D sphere: entry refraction, exit
      // refraction, Fresnel reflections, and absorption through the glass.
      const vertexSource = `
        attribute vec2 position;
        void main() { gl_Position = vec4(position, 0.0, 1.0); }
      `;
      const fragmentSource = `
        precision highp float;
        uniform vec2 resolution;
        uniform vec2 pointer;
        uniform float time;
        uniform vec3 bands;
        uniform vec3 gradientTop;
        uniform vec3 gradientBottom;
        uniform vec3 gradientAccent;
        const float radius = 1.0;
        const float ior = 1.46;
        const float innerRadius = 0.95;
        // Equilibrium under inward radial gravity: a concentric liquid sphere.
        // Rest volume: (liquidRadius / innerRadius)^3 = 0.60.
        const float liquidRadius = 0.8434326653 * innerRadius;
        const float liquidIor = 1.333;

        float liquidField(vec3 point) {
          float distance = length(point);
          vec3 n = point / max(distance, 0.0001);
          // Odd spherical waves have zero mean. Modulating radius cubed
          // preserves the 60% volume as the surface moves around the center.
          float wave = bands.x * sin(n.y * 7.0) * cos(time * 2.4)
            + bands.y * sin(dot(n, normalize(vec3(1.0, 0.4, 0.2))) * 13.0) * sin(time * 3.1)
            + bands.z * sin(dot(n, normalize(vec3(0.2, 0.4, 1.0))) * 21.0) * cos(time * 4.3);
          float r = liquidRadius * pow(1.0 + 0.105 * wave, 1.0 / 3.0);
          return distance - r;
        }

        vec3 liquidNormal(vec3 point) {
          vec2 e = vec2(0.001, 0.0);
          return normalize(vec3(
            liquidField(point + e.xyy) - liquidField(point - e.xyy),
            liquidField(point + e.yxy) - liquidField(point - e.yxy),
            liquidField(point + e.yyx) - liquidField(point - e.yyx)));
        }

        float liquidIntersection(vec3 origin, vec3 direction, float side) {
          float travel = 0.003;
          for (int step = 0; step < 80; step++) {
            float distance = liquidField(origin + direction * travel) * side;
            if (distance < 0.0006) return travel;
            // Conservative steps accommodate the high-frequency surface waves.
            travel += max(distance * 0.38, 0.0003);
            if (travel > 2.0) break;
          }
          return -1.0;
        }

        float farIntersection(vec3 origin, vec3 direction, float r) {
          float b = dot(origin, direction);
          return -b + sqrt(max(0.0, b * b - dot(origin, origin) + r * r));
        }

        // Original procedural noise: no texture downloads or shader SDK.
        float hash3(vec3 p) {
          p = fract(p * 0.1031);
          p += dot(p, p.yzx + 33.33);
          return fract((p.x + p.y) * p.z);
        }

        float noise3(vec3 p) {
          vec3 cell = floor(p);
          vec3 f = fract(p);
          f = f * f * (3.0 - 2.0 * f);
          return mix(
            mix(mix(hash3(cell), hash3(cell + vec3(1,0,0)), f.x),
                mix(hash3(cell + vec3(0,1,0)), hash3(cell + vec3(1,1,0)), f.x), f.y),
            mix(mix(hash3(cell + vec3(0,0,1)), hash3(cell + vec3(1,0,1)), f.x),
                mix(hash3(cell + vec3(0,1,1)), hash3(cell + vec3(1,1,1)), f.x), f.y), f.z);
        }

        float cloud(vec3 p) {
          return noise3(p) * 0.57 + noise3(p * 2.03 + 7.1) * 0.29
            + noise3(p * 4.07 + 19.3) * 0.14;
        }

        vec3 absorbLiquid(vec3 color, float distance, vec3 surface) {
          // Slow domain warping creates broad, soft pools of three colors.
          vec3 p = surface * 1.8 + vec3(time * 0.075, -time * 0.045, time * 0.035);
          vec3 warp = vec3(cloud(p + 4.7), cloud(p + 12.9), cloud(p - 8.3));
          float field = cloud(p + (warp - 0.5) * 2.6);
          float blend = smoothstep(0.22, 0.76, field + surface.y * 0.16);
          vec3 tint = mix(gradientBottom, gradientTop, blend);
          float accent = smoothstep(0.47, 0.76, cloud(p * 0.8 + warp * 1.7 + 22.0) + surface.x * 0.14);
          tint = mix(tint, gradientAccent, accent * 0.85);
          // Fine, stable film grain is restricted to the liquid volume.
          float grain = hash3(vec3(gl_FragCoord.xy, 17.0)) - 0.5;
          tint = clamp(tint + grain * 0.12, 0.02, 1.0);
          vec3 absorption = -log(max(tint, vec3(0.025))) * 1.8;
          vec3 attenuation = exp(-absorption * distance);
          return color * attenuation + tint * (1.0 - attenuation) * 0.16;
        }

        float sphere(vec3 origin, vec3 direction) {
          float b = dot(origin, direction);
          float c = dot(origin, origin) - radius * radius;
          float h = b * b - c;
          if (h < 0.0) return -1.0;
          return -b - sqrt(h);
        }

        vec3 environment(vec3 origin, vec3 direction) {
          vec3 color = mix(vec3(0.65, 0.73, 0.72), vec3(0.96, 0.96, 0.92),
            smoothstep(-0.6, 0.8, direction.y));
          // Large studio softboxes are reflected by the curved surface.
          float light = pow(max(dot(direction, normalize(vec3(-0.65, 0.9, 1.2))), 0.0), 50.0);
          float rim = pow(max(dot(direction, normalize(vec3(1.0, 0.3, -0.6))), 0.0), 28.0);
          color += vec3(1.8) * light + vec3(0.55, 0.67, 0.7) * rim;
          if (direction.y < -0.0001) {
            float t = (-1.3 - origin.y) / direction.y;
            if (t > 0.0) {
              vec3 point = origin + t * direction;
              float shade = exp(-dot(point.xz, point.xz) * 1.15);
              vec3 floorColor = mix(vec3(0.83, 0.86, 0.83), vec3(0.69, 0.77, 0.75),
                smoothstep(-4.0, 6.0, point.x));
              floorColor *= 1.0 - 0.22 * shade;
              float caustic = exp(-dot(point.xz - vec2(0.35, -0.25), point.xz - vec2(0.35, -0.25)) * 7.0);
              floorColor += vec3(0.10, 0.12, 0.11) * caustic;
              color = mix(floorColor, color, 1.0 - exp(-t * 0.025));
            }
          }
          return color;
        }

        vec4 trace(vec2 pixel) {
          // Fit the sphere closely inside its own square canvas.
          vec2 uv = (pixel * 2.0 - resolution) / min(resolution.x, resolution.y) * 0.35;
          vec3 camera = vec3(pointer.x * 0.32, 0.72 + pointer.y * 0.2, 4.8);
          vec3 forward = normalize(-camera);
          vec3 right = normalize(cross(forward, vec3(0.0, 1.0, 0.0)));
          vec3 up = cross(right, forward);
          vec3 direction = normalize(forward * 1.6 + uv.x * right + uv.y * up);
          float distance = sphere(camera, direction);
          if (distance < 0.0) return vec4(0.0);

          vec3 entry = camera + direction * distance;
          vec3 normal = normalize(entry);
          vec3 reflection = environment(entry, reflect(direction, normal));
          vec3 glassRay = refract(direction, normal, 1.0 / ior);
          float b = dot(entry, glassRay);
          float discriminant = b * b - dot(entry, entry) + innerRadius * innerRadius;
          float f0 = pow((1.0 - ior) / (1.0 + ior), 2.0);
          float fresnel = f0 + (1.0 - f0) * pow(1.0 - max(dot(-direction, normal), 0.0), 5.0);
          float glassAlpha = 0.025 + fresnel * 0.38;
          if (discriminant <= 0.0) return vec4(reflection, glassAlpha);

          // Enter the hollow cavity through a thin glass wall.
          vec3 origin = entry + glassRay * (-b - sqrt(discriminant));
          vec3 ray = refract(glassRay, normalize(origin), ior);
          if (dot(ray, ray) < 0.01) return vec4(reflection, glassAlpha);
          float liquidDistance = 0.0;
          vec3 liquidSurface = vec3(0.0);
          float surfaceReflection = 0.0;
          vec3 surfaceColor = vec3(0.0);

          // Ray march the displaced liquid surface, including its silhouette.
          float surfaceDistance = liquidIntersection(origin, ray, 1.0);
          if (surfaceDistance > 0.0) {
              vec3 surface = origin + ray * surfaceDistance;
              liquidSurface = surface;
              vec3 surfaceNormal = liquidNormal(surface);
              float sf0 = pow((1.0 - liquidIor) / (1.0 + liquidIor), 2.0);
              surfaceReflection = sf0 + (1.0 - sf0)
                * pow(1.0 - max(dot(-ray, surfaceNormal), 0.0), 5.0);
              surfaceColor = environment(surface, reflect(ray, surfaceNormal));

              // Bend the ray into the liquid and back out through its far side.
              vec3 liquidRay = refract(ray, surfaceNormal, 1.0 / liquidIor);
              liquidDistance = liquidIntersection(surface, liquidRay, -1.0);
              if (liquidDistance < 0.0) liquidDistance = farIntersection(surface, liquidRay, liquidRadius);
              vec3 liquidExit = surface + liquidRay * liquidDistance;
              vec3 liquidExitNormal = liquidNormal(liquidExit);
              ray = refract(liquidRay, -liquidExitNormal, liquidIor);
              // Avoid a zero ray when a steep ripple produces total reflection.
              if (dot(ray, ray) < 0.01) ray = refract(liquidRay, -normalize(liquidExit), liquidIor);
              if (dot(ray, ray) < 0.01) ray = liquidRay;
              float exitFresnel = sf0 + (1.0 - sf0)
                * pow(1.0 - max(dot(liquidRay, liquidExitNormal), 0.0), 5.0);
              surfaceReflection = 1.0 - (1.0 - surfaceReflection) * (1.0 - exitFresnel);
              origin = liquidExit;
          }
          float wallDistance = farIntersection(origin, ray, innerRadius);
          vec3 innerExit = origin + ray * wallDistance;
          vec3 wallRay = refract(ray, -normalize(innerExit), 1.0 / ior);
          vec3 exitPoint = innerExit + wallRay * farIntersection(innerExit, wallRay, radius);
          vec3 outgoing = refract(wallRay, -normalize(exitPoint), ior);
          if (dot(outgoing, outgoing) < 0.01) outgoing = reflect(wallRay, -normalize(exitPoint));
          vec3 transmission = environment(exitPoint, outgoing);
          transmission = absorbLiquid(transmission, liquidDistance, liquidSurface);
          transmission = mix(transmission, surfaceColor, surfaceReflection);
          // Empty glass lets the actual page background show through.
          return vec4(mix(transmission, reflection, fresnel),
            liquidDistance > 0.0 ? 1.0 : glassAlpha);
        }

        vec4 samplePixel(vec2 pixel) {
          vec4 sampleColor = trace(pixel);
          vec3 mapped = sampleColor.rgb / (sampleColor.rgb + vec3(0.28));
          // The WebGL canvas composites premultiplied color onto the page.
          return vec4(pow(mapped, vec3(1.0 / 2.2)) * sampleColor.a, sampleColor.a);
        }

        void main() {
          gl_FragColor = 0.5 * (samplePixel(gl_FragCoord.xy + vec2(-0.25))
            + samplePixel(gl_FragCoord.xy + vec2(0.25)));
        }
      `;
      function compile(type: number, source: string) {
        const shader = gl.createShader(type);
        if (!shader) throw new Error("Cannot create shader");
        gl.shaderSource(shader, source);
        gl.compileShader(shader);
        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
          throw new Error(gl.getShaderInfoLog(shader) ?? "Shader compilation failed");
        }
        return shader;
      }
      const program = gl.createProgram();
      if (!program) throw new Error("Cannot create program");
      gl.attachShader(program, compile(gl.VERTEX_SHADER, vertexSource));
      gl.attachShader(program, compile(gl.FRAGMENT_SHADER, fragmentSource));
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program) ?? "Program link failed");
      gl.useProgram(program);
      const buffer = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
      const position = gl.getAttribLocation(program, 'position');
      gl.enableVertexAttribArray(position);
      gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
      const resolution = gl.getUniformLocation(program, 'resolution');
      const pointer = gl.getUniformLocation(program, 'pointer');
      const timeUniform = gl.getUniformLocation(program, 'time');
      const bandsUniform = gl.getUniformLocation(program, 'bands');
      const gradientTop = gl.getUniformLocation(program, 'gradientTop');
      const gradientBottom = gl.getUniformLocation(program, 'gradientBottom');
      const gradientAccent = gl.getUniformLocation(program, 'gradientAccent');
      const palettes = palettesRef.current;
      const rgb = (hex: string) => [1, 3, 5].map(offset => parseInt(hex.slice(offset, offset + 2), 16) / 255);
      const initial = colors ?? palettes.find(p => p.name === initialPalette) ?? palettes[0];
      gl.uniform3fv(gradientTop, rgb(initial.top));
      gl.uniform3fv(gradientBottom, rgb(initial.bottom));
      gl.uniform3fv(gradientAccent, rgb(initial.accent));
      const microphone = microphoneRef.current!;
      const status = statusRef.current!;
      let audioContext: AudioContext | null = null;
      let stream: MediaStream | null = null;
      let analyser: AnalyserNode | null = null;
      let frequencies: Uint8Array<ArrayBuffer> | null = null;
      let contextLost = false;
      const levels = [0.45, 0.3, 0.2];
      let previousTime = performance.now();
      let animationTime = 0;

      function stopMicrophone() {
        if (stream) stream.getTracks().forEach(track => track.stop());
        stream = null;
        analyser = null;
        if (audioContext) audioContext.close().catch(console.error);
        audioContext = null;
        microphone.textContent = 'Use microphone';
        microphone.setAttribute('aria-pressed', 'false');
        status.textContent = 'Sound wave preview';
      }
      microphone.addEventListener('click', async () => {
        if (stream) { stopMicrophone(); return; }
        microphone.disabled = true;
        status.textContent = 'Waiting for microphone permission…';
        try {
          if (!navigator.mediaDevices?.getUserMedia) throw new Error('unavailable');
          if (!audioEnabled) return;
          stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          audioContext = new AudioContext();
          await audioContext.resume();
          analyser = audioContext.createAnalyser();
          analyser.fftSize = 1024;
          analyser.smoothingTimeConstant = 0.75;
          audioContext.createMediaStreamSource(stream).connect(analyser);
          frequencies = new Uint8Array(analyser.frequencyBinCount);
          stream.getAudioTracks()[0].addEventListener('ended', stopMicrophone);
          microphone.textContent = 'Stop microphone';
          microphone.setAttribute('aria-pressed', 'true');
          status.textContent = 'Listening · audio stays on this device';
        } catch (cause) {
          stopMicrophone();
          status.textContent = cause instanceof Error && cause.name === 'NotAllowedError'
            ? 'Microphone permission denied · preview continues'
            : 'Microphone unavailable · use localhost or HTTPS';
        } finally { microphone.disabled = false; }
      });
      window.addEventListener('pagehide', stopMicrophone);
      const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
      let frame = 0;
      let pointerX = 0;
      let pointerY = 0;
      function draw(now = performance.now()) {
        frame = 0;
        if (contextLost || document.hidden) return;
        const delta = Math.min((now - previousTime) / 1000, 0.05);
        previousTime = now;
        if (!reducedMotion.matches) animationTime += delta;
        // With no excitation, every wave relaxes toward a perfectly round surface.
        const targets = [0, 0, 0];
        if (analyser && frequencies && audioContext) {
          analyser.getByteFrequencyData(frequencies);
          const ranges = [[40, 250], [250, 2000], [2000, 8000]];
          ranges.forEach(([low, high], band) => {
            const binHz = audioContext!.sampleRate / analyser!.fftSize;
            const first = Math.max(1, Math.floor(low / binHz));
            const last = Math.min(frequencies!.length - 1, Math.ceil(high / binHz));
            let energy = 0;
            for (let i = first; i <= last; i++) energy += (frequencies![i] / 255) ** 2;
            const amplitude = Math.sqrt(energy / Math.max(1, last - first + 1));
            // Gate low-level microphone noise rather than maintaining a ripple floor.
            targets[band] = Math.min(1.5, Math.max(0, amplitude - 0.045) * 3.1);
          });
        }
        levels.forEach((value, i) => {
          // Quick response to sound; slower, frame-rate-independent release.
          // Fine ripples dissipate before the larger, heavier waves.
          const rate = targets[i] > value ? 14 : [1.4, 1.9, 2.5][i];
          levels[i] += (targets[i] - value) * (1 - Math.exp(-delta * rate));
          if (targets[i] === 0 && levels[i] < 0.0005) levels[i] = 0;
        });
        const ratio = Math.min(devicePixelRatio || 1, 1.5);
        const width = Math.round(canvas.clientWidth * ratio);
        const height = Math.round(canvas.clientHeight * ratio);
        if (canvas.width !== width || canvas.height !== height) {
          canvas.width = width;
          canvas.height = height;
        }
        gl.viewport(0, 0, width, height);
        gl.clearColor(0, 0, 0, 0);
        gl.clear(gl.COLOR_BUFFER_BIT);
        gl.uniform2f(resolution, width, height);
        gl.uniform2f(pointer, reducedMotion.matches || !followCursor ? 0 : pointerX, reducedMotion.matches || !followCursor ? 0 : pointerY);
        gl.uniform1f(timeUniform, animationTime);
        gl.uniform3fv(bandsUniform, reducedMotion.matches ? [0, 0, 0] : levels);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
        if (!reducedMotion.matches) schedule();
      }
      function schedule() { if (!frame) frame = requestAnimationFrame(draw); }
      window.addEventListener('resize', schedule);
      document.addEventListener('visibilitychange', () => {
        if (document.hidden) { cancelAnimationFrame(frame); frame = 0; }
        else { previousTime = performance.now(); schedule(); }
      });
      canvas.addEventListener('pointermove', event => {
        if (!followCursor) return;
        pointerX = event.clientX / canvas.clientWidth * 2 - 1;
        pointerY = 1 - event.clientY / canvas.clientHeight * 2;
        schedule();
      });
      canvas.addEventListener('pointerleave', () => { pointerX = pointerY = 0; schedule(); });
      reducedMotion.addEventListener('change', schedule);
      canvas.addEventListener('webglcontextlost', event => {
        event.preventDefault();
        contextLost = true;
        cancelAnimationFrame(frame);
        stopMicrophone();
        fail('The 3D canvas was interrupted. Reload this page to restore it.');
      });
      dispose = () => { contextLost = true; cancelAnimationFrame(frame); stopMicrophone(); events.abort(); gl.deleteBuffer(buffer); gl.deleteProgram(program); };
      draw();
    }
    if (!gl) fail('This browser does not support WebGL. Open this page in a browser with hardware acceleration enabled.');
    else {
      try { start(gl); }
      catch (cause) { console.error(cause); fail('The 3D canvas could not start. Please try another browser.'); }
    }
  
    return () => { dispose(); };
  }, [audioEnabled, initialPalette, palettes, colors, followCursor, size]);
  return <div className="glass-scene" style={{ width: Number.isFinite(size) ? Math.max(1, size) : 320 }}>
    <canvas ref={canvasRef} id="glass" role="img" aria-label="A glass sphere containing animated liquid with sound waves" />
    <div className="glass-controls" hidden={!audioEnabled} style={{ display: audioEnabled ? undefined : "none" }}><button ref={microphoneRef} id="microphone" type="button" aria-pressed="false">Use microphone</button><p ref={statusRef} id="status" role="status">Sound wave preview</p></div>
    <p ref={errorRef} id="error" hidden />
    <style jsx>{`
      .glass-scene{position:relative;max-width:100%;aspect-ratio:1;flex-shrink:0;background:transparent;color:#506864;font:12px system-ui}
      canvas{display:block;width:100%;height:100%;aspect-ratio:1;background:transparent}
      .glass-controls{position:absolute;bottom:max(28px,env(safe-area-inset-bottom));left:50%;transform:translateX(-50%);display:grid;justify-items:center;gap:10px;width:min(90vw,420px)}
      button{font:13px system-ui;color:#35544f;background:#ffffff80;border:1px solid #ffffffb0;border-radius:30px;padding:12px 22px;cursor:pointer;backdrop-filter:blur(12px)}
      button:hover{background:#ffffffc0} button:focus-visible{outline:2px solid #408f85;outline-offset:4px} button:disabled{opacity:.6;cursor:wait}
      #error:not([hidden]){position:absolute;inset:0;margin:0;display:grid;place-content:center;text-align:center;padding:24px;font-size:16px;color:#425250}
    `}</style>
  </div>;
}
