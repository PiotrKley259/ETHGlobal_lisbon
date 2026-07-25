import { Octopus } from "./Octopus";
import "../landing.css";

interface LandingProps {
  onEnter: () => void;
}

// Above-the-fold landing (hero → how-it-works → CTA strip). The desk app is
// untouched — this is a front door, entered state lives in App. Copy mirrors
// docs/architecture.svg ("life of a trade") and the README's trust story.
export function Landing({ onEnter }: LandingProps) {
  return (
    <div className="landing">
      <header className="hero">
        <div className="crt px-card">
          <div className="crt-titlebar">
            <span className="lights" aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
            OPTOPUTS.EXE — desk terminal
          </div>
          <Octopus />
          <p className="wordmark iridescent-text">OptoPuts</p>
        </div>
        <h1>Insurance for your wallet.</h1>
        <p className="hero-body">
          Price and mint on-chain options from live market data in seconds.
        </p>
        <button className="cta cta-main" onClick={onEnter}>
          <span className="iridescent-text">Try live demo</span>
        </button>
        <p className="trust-row">
          live vols from The Graph · deterministic pricing · on-chain settlement
        </p>
        <p className="asset-row" aria-label="supported assets">
          <span>ETH</span>
          <span>WBTC</span>
          <span>LINK</span>
          <span>UNI</span>
          <span>AAVE</span>
        </p>
        <a className="scroll-cue" href="#how">
          How it works ↓
        </a>
      </header>

      <main>
        <section id="how" className="how" aria-labelledby="how-title">
          <h2 id="how-title">How it works</h2>
          <p className="how-intro">
            From plain-English request to on-chain settlement, every step is
            verifiable. The agent computes nothing — it explains; tested code
            does the math.
          </p>
          <ol className="steps">
            <li className="step">
              <span className="step-num" aria-hidden="true">01</span>
              <h3>Ask in English</h3>
              <p>
                “Protect my ETH below $1,800 this week.” The chat streams back
                tool calls, prices, and chain events as they happen.
              </p>
              <p className="step-stack">React · FastAPI · Claude</p>
            </li>
            <li className="step">
              <span className="step-num" aria-hidden="true">02</span>
              <h3>Measure the market</h3>
              <p>
                Uniswap v3 trade history becomes a realized-vol curve; Aave sets
                the rate; the regime reads calm, elevated, or stressed — your
                thresholds, not ours.
              </p>
              <p className="step-stack">The Graph gateway</p>
            </li>
            <li className="step">
              <span className="step-num" aria-hidden="true">03</span>
              <h3>Price it in code</h3>
              <p>
                Black–Scholes with full Greeks, single legs or eight strategies,
                payoff curves and breakevens. No vibes-based pricing — the AI
                never touches the arithmetic.
              </p>
              <p className="step-stack">pure math · MCP</p>
            </li>
            <li className="step">
              <span className="step-num" aria-hidden="true">04</span>
              <h3>Mint on confirm</h3>
              <p>
                Coverage-gated: the desk never sells what it can’t pay. Each
                series is an HTS token, every quote and trade lands in an HCS
                audit log, and settlement is armed on-chain.
              </p>
              <p className="step-stack">Hedera HTS · HCS</p>
            </li>
            <li className="step">
              <span className="step-num" aria-hidden="true">05</span>
              <h3>Settle automatically</h3>
              <p>
                At expiry a worker pays max(0, K−S) in demo stablecoin —
                idempotent. The whole trail sits on Hashscan for anyone to
                audit.
              </p>
              <p className="step-stack">Hedera scheduled tx</p>
            </li>
          </ol>
          <p className="stack-badges" aria-label="powered by">
            <span>The Graph</span>
            <span>Claude</span>
            <span>Hedera</span>
          </p>
        </section>

        <section className="cta-strip" aria-labelledby="cta-title">
          <h2 id="cta-title">Ready to protect your wallet?</h2>
          <button className="cta" onClick={onEnter}>
            Open the desk
          </button>
        </section>
      </main>
    </div>
  );
}
