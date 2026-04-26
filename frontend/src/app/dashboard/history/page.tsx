"use client";

import { useState } from "react";
import { Clock3 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type HistoryItem = {
    company_name: string;
    claim: string;
    industry: string;
    risk_level: string;
    confidence: number;
    report_created_at: string;
    report_file_name: string;
};

export default function HistoryPage() {
    const [items] = useState<HistoryItem[]>(() => {
        if (typeof window === "undefined") return [];
        const raw = window.localStorage.getItem("esg-analysis-history");
        if (!raw) return [];
        try {
            const parsed = JSON.parse(raw) as HistoryItem[];
            return Array.isArray(parsed) ? parsed : [];
        } catch {
            return [];
        }
    });

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-2xl font-bold font-heading text-neutral-900 tracking-tight">Run History</h2>
                <p className="text-neutral-500 text-sm mt-1">Recent analyses triggered from this frontend session.</p>
            </div>

            <Card className="border-neutral-200 bg-white shadow-sm">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Clock3 className="w-5 h-5 text-primary-700" /> Recent Runs
                    </CardTitle>
                    <CardDescription>{items.length} items</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                    {items.length === 0 && <div className="text-sm text-neutral-500">No run history yet.</div>}

                    {items.map((item, idx) => (
                        <div key={`${item.company_name}-${idx}`} className="rounded-lg border border-neutral-200 p-4">
                            <div className="font-semibold text-neutral-900">{item.company_name}</div>
                            <div className="text-sm text-neutral-600 mt-1">{item.claim}</div>
                            <div className="text-xs text-neutral-500 mt-2">
                                {[
                                    item.industry,
                                    item.risk_level && !/^unknown$/i.test(item.risk_level) ? `Risk: ${item.risk_level}` : "",
                                    item.confidence > 0 ? `Confidence: ${Math.round(item.confidence * 100)}%` : "",
                                    new Date(item.report_created_at).toLocaleString(),
                                ]
                                    .filter(Boolean)
                                    .join(" | ")}
                            </div>
                        </div>
                    ))}
                </CardContent>
            </Card>
        </div>
    );
}
