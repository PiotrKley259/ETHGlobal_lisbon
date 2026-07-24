import "./App.css";

// Three regions per the spec: chat (left, primary), pricing panel (right top),
// chain activity strip (right bottom). Filled in by tracks B2.1–B2.4.
function App() {
  return (
    <div className="app">
      <section className="region chat-region">
        <header className="region-title">OptoPuts · desk chat</header>
      </section>
      <section className="region panel-region">
        <header className="region-title">pricing panel</header>
      </section>
      <section className="region chain-region">
        <header className="region-title">chain activity</header>
      </section>
    </div>
  );
}

export default App;
