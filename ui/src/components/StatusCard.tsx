import { useLive } from "../store";

export function StatusCard() {
  const { lastPing } = useLive();
  return (
    <div role="status" className="card">
      <div className="dot" data-ok={!!lastPing} />
      <div>
        <div className="title">Live Connection</div>
        <div className="desc">{lastPing ? "connected (demo heartbeat)" : "waiting…"}</div>
      </div>
    </div>
  );
}
