import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import { ensureBackendEnvLoaded, getPythonExecutable, getRepoRoot } from "@/lib/server/report-utils";

export const runtime = "nodejs";

function extractJsonPayload(stdout: string): Record<string, unknown> | null {
    const trimmed = stdout.trim();

    try {
        return JSON.parse(trimmed) as Record<string, unknown>;
    } catch {
        // Continue to fallback extraction.
    }

    const first = trimmed.indexOf("{");
    const last = trimmed.lastIndexOf("}");
    if (first >= 0 && last > first) {
        const candidate = trimmed.slice(first, last + 1);
        try {
            return JSON.parse(candidate) as Record<string, unknown>;
        } catch {
            return null;
        }
    }

    return null;
}

function cacheCandidates(repoRoot: string, company: string): string[] {
    const normalized = company.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
    return [
        path.join(repoRoot, "cache", "esg_analysis", `${normalized}.json`),
        path.join(repoRoot, "cache", "esg_analysis", `${company.toLowerCase()}.json`),
    ];
}

export async function POST(req: Request) {
    ensureBackendEnvLoaded();
    const { company } = (await req.json()) as { company?: string };

    if (!company || !company.trim()) {
        return Response.json({ status: "invalid_input", result: {} }, { status: 400 });
    }

    const repoRoot = getRepoRoot();
    const python = getPythonExecutable();
    const args = ["-m", "features.esg_mismatch_detector.pipeline", company.trim()];
    const fallbackResult = {
        "Company Analyzed": company.trim(),
        "Overall Greenwashing Risk": "Unknown",
        "Executive Summary": "Mismatch detector returned fallback output.",
        "1. Future Commitments & Progress": [],
        "2. Past Promise-Implementation Gaps (Mismatches)": [
            "No mismatch records available at this time.",
        ],
    };

    const runResult = await new Promise<{ code: number; stdout: string; stderr: string }>((resolve) => {
        const child = spawn(python, args, {
            cwd: repoRoot,
            env: {
                ...process.env,
                PYTHONIOENCODING: "utf-8",
            },
        });

        let stdout = "";
        let stderr = "";

        child.stdout.on("data", (chunk: Buffer) => {
            stdout += chunk.toString("utf-8");
        });

        child.stderr.on("data", (chunk: Buffer) => {
            stderr += chunk.toString("utf-8");
        });

        child.on("close", (code) => {
            resolve({ code: code ?? 1, stdout, stderr });
        });
    });

    if (runResult.code !== 0) {
        for (const candidate of cacheCandidates(repoRoot, company.trim())) {
            try {
                const raw = await fs.readFile(candidate, "utf-8");
                const cached = JSON.parse(raw) as Record<string, unknown>;
                return Response.json({
                    status: "fallback",
                    company: company.trim(),
                    command: `python -m features.esg_mismatch_detector.pipeline \"${company.trim()}\"`,
                    result: cached,
                });
            } catch {
                // Try next candidate.
            }
        }

        return Response.json({
            status: "fallback",
            company: company.trim(),
            command: `python -m features.esg_mismatch_detector.pipeline \"${company.trim()}\"`,
            result: fallbackResult,
        });
    }

    let parsed = extractJsonPayload(runResult.stdout);

    if (!parsed) {
        for (const candidate of cacheCandidates(repoRoot, company.trim())) {
            try {
                const raw = await fs.readFile(candidate, "utf-8");
                parsed = JSON.parse(raw) as Record<string, unknown>;
                break;
            } catch {
                // Try next candidate.
            }
        }
    }

    if (!parsed) {
        return Response.json({
            status: "fallback",
            company: company.trim(),
            command: `python -m features.esg_mismatch_detector.pipeline \"${company.trim()}\"`,
            result: fallbackResult,
        });
    }

    return Response.json({
        status: "success",
        company: company.trim(),
        command: `python -m features.esg_mismatch_detector.pipeline \"${company.trim()}\"`,
        result: parsed,
    });
}
