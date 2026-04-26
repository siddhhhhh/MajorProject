"use client";

import { useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2, SearchCode } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type MismatchResult = {
    [key: string]: unknown;
};

type RowRecord = Record<string, string>;

function isRowRecord(value: unknown): value is RowRecord {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

export default function MismatchPage() {
    const [company, setCompany] = useState("Microsoft");
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<MismatchResult | null>(null);

    const runMismatch = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setResult(null);

        try {
            const res = await fetch("/api/mismatch-detect", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ company }),
            });

            const data = (await res.json()) as {
                result?: MismatchResult;
            };

            setResult(data.result || {
                "Company Analyzed": company,
                "Overall Greenwashing Risk": "Unknown",
                "Executive Summary": "No fresh mismatch output was available. Showing fallback summary.",
                "1. Future Commitments & Progress": [],
                "2. Past Promise-Implementation Gaps (Mismatches)": [
                    "No mismatch records available at this time.",
                ],
            });
        } catch {
            setResult({
                "Company Analyzed": company,
                "Overall Greenwashing Risk": "Unknown",
                "Executive Summary": "Detector completed with fallback output.",
                "1. Future Commitments & Progress": [],
                "2. Past Promise-Implementation Gaps (Mismatches)": [
                    "No mismatch records available at this time.",
                ],
            });
        } finally {
            setLoading(false);
        }
    };

    const futureRaw = (result?.["1. Future Commitments & Progress"] as unknown[] | undefined) || [];
    const mismatchRaw = (result?.["2. Past Promise-Implementation Gaps (Mismatches)"] as unknown[] | undefined) || [];

    const futureCommitments = futureRaw.filter(isRowRecord);
    const mismatchGaps = mismatchRaw.filter(isRowRecord);
    const mismatchNotes = mismatchRaw.filter((item) => typeof item === "string") as string[];

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-2xl font-bold font-heading text-neutral-900 tracking-tight">ESG Mismatch Detector</h2>
            </div>

            <Card className="border-neutral-200 bg-white shadow-sm">
                <CardHeader>
                    <CardTitle>Run Detector</CardTitle>
                </CardHeader>
                <CardContent>
                    <form onSubmit={runMismatch} className="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
                        <div className="md:col-span-9 space-y-2">
                            <Label htmlFor="company">Company Name</Label>
                            <Input id="company" value={company} onChange={(e) => setCompany(e.target.value)} required />
                        </div>
                        <div className="md:col-span-3">
                            <Button type="submit" className="w-full" disabled={loading}>
                                {loading ? (
                                    <>
                                        <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Running
                                    </>
                                ) : (
                                    <>
                                        <SearchCode className="w-4 h-4 mr-2" /> Detect Mismatch
                                    </>
                                )}
                            </Button>
                        </div>
                    </form>

                </CardContent>
            </Card>

            {result && (
                <>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <Card className="border-neutral-200 bg-white shadow-sm">
                            <CardContent className="p-5">
                                <div className="text-xs text-neutral-500">Company Analyzed</div>
                                <div className="text-lg font-semibold text-neutral-900 mt-1">{String(result["Company Analyzed"] || "N/A")}</div>
                            </CardContent>
                        </Card>
                        <Card className="border-neutral-200 bg-white shadow-sm">
                            <CardContent className="p-5">
                                <div className="text-xs text-neutral-500">Overall Greenwashing Risk</div>
                                <div className="text-lg font-semibold text-neutral-900 mt-1">{String(result["Overall Greenwashing Risk"] || "N/A")}</div>
                            </CardContent>
                        </Card>
                        <Card className="border-neutral-200 bg-white shadow-sm">
                            <CardContent className="p-5">
                                <div className="text-xs text-neutral-500">Summary</div>
                                <div className="text-sm font-medium text-neutral-800 mt-1">{String(result["Executive Summary"] || "N/A")}</div>
                            </CardContent>
                        </Card>
                    </div>

                    <Card className="border-neutral-200 bg-white shadow-sm">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <CheckCircle2 className="w-5 h-5 text-emerald-600" /> Future Commitments & Progress
                            </CardTitle>
                            <CardDescription>{futureCommitments.length} records</CardDescription>
                        </CardHeader>
                        <CardContent>
                            {!!mismatchNotes.length && (
                                <div className="mb-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                                    {mismatchNotes.join(" ")}
                                </div>
                            )}
                            <div className="overflow-x-auto rounded-md border border-neutral-200">
                                <table className="w-full text-sm border-collapse">
                                    <thead>
                                        <tr className="bg-neutral-100 text-left">
                                            <th className="px-3 py-2 border-b border-neutral-200">Pledge</th>
                                            <th className="px-3 py-2 border-b border-neutral-200">Status Trend</th>
                                            <th className="px-3 py-2 border-b border-neutral-200">Progress/Trend</th>
                                            <th className="px-3 py-2 border-b border-neutral-200">Measures Being Taken</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {futureCommitments.map((row, idx) => (
                                            <tr key={`future-${idx}`}>
                                                <td className="px-3 py-2 border-b border-neutral-200 align-top">{row["Pledge"] || "-"}</td>
                                                <td className="px-3 py-2 border-b border-neutral-200 align-top">{row["Status Trend"] || "-"}</td>
                                                <td className="px-3 py-2 border-b border-neutral-200 align-top">{row["Progress/Trend"] || "-"}</td>
                                                <td className="px-3 py-2 border-b border-neutral-200 align-top">{row["Measures Being Taken"] || "-"}</td>
                                            </tr>
                                        ))}
                                        {futureCommitments.length === 0 && (
                                            <tr>
                                                <td className="px-3 py-3 text-neutral-500" colSpan={4}>No future commitment records</td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </CardContent>
                    </Card>

                    <Card className="border-neutral-200 bg-white shadow-sm">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <AlertTriangle className="w-5 h-5 text-amber-600" /> Past Promise-Implementation Gaps
                            </CardTitle>
                            <CardDescription>{mismatchGaps.length} mismatch records</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="overflow-x-auto rounded-md border border-neutral-200">
                                <table className="w-full text-sm border-collapse">
                                    <thead>
                                        <tr className="bg-neutral-100 text-left">
                                            <th className="px-3 py-2 border-b border-neutral-200">Failed Pledge</th>
                                            <th className="px-3 py-2 border-b border-neutral-200">Expected Target</th>
                                            <th className="px-3 py-2 border-b border-neutral-200">Actual Performance</th>
                                            <th className="px-3 py-2 border-b border-neutral-200">Risk Level</th>
                                            <th className="px-3 py-2 border-b border-neutral-200">Evidence Source</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {mismatchGaps.map((row, idx) => (
                                            <tr key={`gap-${idx}`}>
                                                <td className="px-3 py-2 border-b border-neutral-200 align-top">{row["Failed Pledge"] || "-"}</td>
                                                <td className="px-3 py-2 border-b border-neutral-200 align-top">{row["Expected Target"] || "-"}</td>
                                                <td className="px-3 py-2 border-b border-neutral-200 align-top">{row["Actual Verified Performance"] || "-"}</td>
                                                <td className="px-3 py-2 border-b border-neutral-200 align-top">{row["Risk Level"] || "-"}</td>
                                                <td className="px-3 py-2 border-b border-neutral-200 align-top break-all">{row["Evidence Source"] || "-"}</td>
                                            </tr>
                                        ))}
                                        {mismatchGaps.length === 0 && (
                                            <tr>
                                                <td className="px-3 py-3 text-neutral-500" colSpan={5}>No mismatch records found</td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </CardContent>
                    </Card>
                </>
            )}
        </div>
    );
}
