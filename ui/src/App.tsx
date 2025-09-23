import { useEffect } from "react";
import { useLive } from "./store";
import { StatusCard } from "./components/StatusCard";

export default function App() {
  const { lastPing, setLastPing } = useLive();
  useEffect(() => {
    // demo heartbeat to prove the app actually runs
    const id = setInterval(() => setLastPing(Date.now()), 2000);
    return () => clearInterval(id);
  }, [setLastPing]);
  return (
    <div className="page">
      <header className="row">
        <h1>Entropy Portfolio Lab — Demo UI</h1>
      </header>
      <main>
        <StatusCard />
        <p className="meta">Last heartbeat: {lastPing ? new Date(lastPing).toLocaleTimeString() : "—"}</p>
      </main>
    </div>
  );
}
