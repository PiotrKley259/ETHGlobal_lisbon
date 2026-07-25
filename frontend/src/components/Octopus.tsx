// The OptoPuts mascot (same sprite as the header logo and favicon), shown in
// the landing CRT card. Rendered size comes from CSS (.octopus width/height);
// mobile 64px, ≥768px 128px. The old hand-drawn idle/alert SVG frames live in
// git history if the hover frame-swap ever comes back.
export function Octopus() {
  return (
    <span className="octopus" aria-hidden="true">
      <img src="/octopus-logo.png" alt="" className="octo-frame" />
    </span>
  );
}
