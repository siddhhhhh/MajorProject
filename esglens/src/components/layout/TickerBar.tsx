const TICKER = [
  { t: "SHEL", r: "CCC", gw: 77.2, dir: "up" },
  { t: "BP", r: "CCC", gw: 68.1, dir: "flat" },
  { t: "ULVR", r: "BB", gw: 34.5, dir: "down" },
  { t: "TSCO", r: "B", gw: 41.2, dir: "flat" },
  { t: "BARC", r: "B", gw: 52.3, dir: "up" },
  { t: "SDR", r: "BBB", gw: 22.1, dir: "down" },
  { t: "TTE", r: "B-", gw: 64.0, dir: "up" },
  { t: "EQNR", r: "BB", gw: 51.0, dir: "down" },
];

export function TickerBar() {
  const items = [...TICKER, ...TICKER];
  return (
    <div
      className="fixed top-0 left-0 right-0 z-[60] h-8 overflow-hidden flex items-center"
      style={{ background: "hsl(215 60% 10%)" }}
    >
      <div className="flex gap-8 whitespace-nowrap font-mono text-[11px] animate-[ticker_60s_linear_infinite] pl-4">
        {items.map((i, idx) => {
          const arrow = i.dir === "up" ? "up" : i.dir === "down" ? "down" : "|";
          const arrowColor =
            i.dir === "up" ? "text-[#FF7B72]" : i.dir === "down" ? "text-[#6EE7A8]" : "text-white/40";
          const gwColor =
            i.gw > 60 ? "text-[#FF7B72]" : i.gw > 40 ? "text-[#FFB84D]" : "text-[#6EE7A8]";
          return (
            <span key={idx} className="flex items-center gap-2">
              <span className="text-white font-medium">{i.t}</span>
              <span className="text-white/30">|</span>
              <span className="text-[#FFB84D]">{i.r}</span>
              <span className="text-white/30">|</span>
              <span className="text-white/40">GW</span>
              <span className={gwColor}>{i.gw.toFixed(1)}%</span>
              <span className={arrowColor}>{arrow}</span>
              <span className="text-white/20">|</span>
            </span>
          );
        })}
      </div>
      <style>{`@keyframes ticker { from { transform: translateX(0); } to { transform: translateX(-50%); } }`}</style>
    </div>
  );
}