"use client";

import { useState } from "react";
import { Save } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function SettingsPage() {
    const [defaultIndustry, setDefaultIndustry] = useState(() => {
        if (typeof window === "undefined") return "Consumer Goods";
        return window.localStorage.getItem("esg-default-industry") || "Consumer Goods";
    });
    const [workflowTimeout, setWorkflowTimeout] = useState(() => {
        if (typeof window === "undefined") return "600";
        return window.localStorage.getItem("esg-workflow-timeout") || "600";
    });
    const [saved, setSaved] = useState(false);

    const save = () => {
        window.localStorage.setItem("esg-default-industry", defaultIndustry);
        window.localStorage.setItem("esg-workflow-timeout", workflowTimeout);
        setSaved(true);
        setTimeout(() => setSaved(false), 1800);
    };

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-2xl font-bold font-heading text-neutral-900 tracking-tight">Settings</h2>
                <p className="text-neutral-500 text-sm mt-1">Demo-level preferences for analysis input defaults.</p>
            </div>

            <Card className="border-neutral-200 bg-white shadow-sm max-w-2xl">
                <CardHeader>
                    <CardTitle>Analysis Defaults</CardTitle>
                    <CardDescription>These values are stored in browser local storage.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="space-y-2">
                        <Label htmlFor="defaultIndustry">Default Industry</Label>
                        <Input id="defaultIndustry" value={defaultIndustry} onChange={(e) => setDefaultIndustry(e.target.value)} />
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="workflowTimeout">Workflow Timeout (seconds)</Label>
                        <Input id="workflowTimeout" value={workflowTimeout} onChange={(e) => setWorkflowTimeout(e.target.value)} />
                    </div>

                    <Button onClick={save}>
                        <Save className="w-4 h-4 mr-2" /> Save Preferences
                    </Button>

                    {saved && <div className="text-sm text-emerald-700">Settings saved.</div>}
                </CardContent>
            </Card>
        </div>
    );
}
