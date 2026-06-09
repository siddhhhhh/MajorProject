import { useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { UploadCloud, FileText, X, CheckCircle2, Loader2 } from "lucide-react";

type Status = "queued" | "parsing" | "ready";
type UFile = { id: string; name: string; size: number; status: Status };

function fmt(n: number) {
  if (n < 1024) return n + " B";
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
  return (n / 1024 / 1024).toFixed(1) + " MB";
}

export function FileDropZone() {
  const [files, setFiles] = useState<UFile[]>([]);
  const [drag, setDrag] = useState(false);
  const ref = useRef<HTMLInputElement>(null);

  const add = (list: FileList | null) => {
    if (!list) return;
    const next: UFile[] = Array.from(list).map((f) => ({
      id: crypto.randomUUID(),
      name: f.name,
      size: f.size,
      status: "queued",
    }));
    setFiles((p) => [...p, ...next]);
    next.forEach((f, i) => {
      setTimeout(() => setFiles((p) => p.map((x) => (x.id === f.id ? { ...x, status: "parsing" } : x))), 400 + i * 200);
      setTimeout(() => setFiles((p) => p.map((x) => (x.id === f.id ? { ...x, status: "ready" } : x))), 1800 + i * 200);
    });
  };

  return (
    <div>
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); add(e.dataTransfer.files); }}
        onClick={() => ref.current?.click()}
        className={`relative cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition grid-bg ${
          drag
            ? "border-teal-bright bg-teal-bright/10 scale-[1.01] glow-teal"
            : "border-teal-dim/50 bg-bg-elevated hover:border-teal-dim"
        }`}
      >
        <input ref={ref} type="file" multiple accept=".pdf,.txt,.csv,.docx" hidden onChange={(e) => add(e.target.files)} />
        <motion.div animate={{ y: [0, -4, 0] }} transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}>
          <UploadCloud className={`h-10 w-10 mx-auto ${drag ? "text-teal-bright scale-110" : "text-teal-mid"} transition`} />
        </motion.div>
        <div className="mt-3 font-medium text-text-primary">Drop ESG reports, filings, or evidence here</div>
        <div className="font-mono text-[11px] text-text-secondary mt-1">
          PDF | TXT | CSV | DOCX | up to 25MB each | multiple files supported
        </div>
      </div>

      <AnimatePresence>
        {files.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {files.map((f) => (
              <motion.div
                key={f.id}
                layout
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-bg-surface border border-bg-border text-xs"
              >
                <FileText className="h-3.5 w-3.5 text-teal-bright" />
                <span className="text-text-primary truncate max-w-[180px]">{f.name}</span>
                <span className="font-mono text-[10px] text-text-muted">{fmt(f.size)}</span>
                {f.status === "queued" && <span className="text-[10px] font-mono text-text-muted">QUEUED</span>}
                {f.status === "parsing" && <Loader2 className="h-3 w-3 text-amber-bright animate-spin" />}
                {f.status === "ready" && <CheckCircle2 className="h-3.5 w-3.5 text-teal-bright" />}
                <button
                  onClick={(e) => { e.stopPropagation(); setFiles((p) => p.filter((x) => x.id !== f.id)); }}
                  className="ml-1 text-risk-high hover:scale-110 transition"
                >
                  <X className="h-3 w-3" />
                </button>
              </motion.div>
            ))}
          </div>
        )}
      </AnimatePresence>

      <p className="mt-3 text-[11px] text-text-muted italic">
        Uploaded documents are prioritised as primary evidence over web-scraped sources.
      </p>
    </div>
  );
}