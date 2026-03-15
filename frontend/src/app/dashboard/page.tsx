"use client";

import { motion } from "framer-motion";
import { 
  Building2, 
  AlertTriangle, 
  Activity, 
  FileCheck2,
  TrendingDown,
  TrendingUp
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line
} from "recharts";

const riskData = [
  { name: 'Low Risk', value: 45, fill: '#4ade80' },
  { name: 'Moderate Risk', value: 35, fill: '#fbbf24' },
  { name: 'High Risk', value: 20, fill: '#ef4444' },
];

const trendData = [
  { month: 'Jan', score: 65, avg: 55 },
  { month: 'Feb', score: 68, avg: 56 },
  { month: 'Mar', score: 62, avg: 57 },
  { month: 'Apr', score: 71, avg: 58 },
  { month: 'May', score: 74, avg: 58 },
  { month: 'Jun', score: 78, avg: 59 },
];

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold font-heading text-neutral-900 tracking-tight">Dashboard Overview</h2>
        <p className="text-neutral-500 text-sm mt-1">Monitor ESG intelligence metrics and recent analyses.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { 
            title: "Total Analyses Run", 
            value: "2,405", 
            change: "+12.5%", 
            positive: true,
            icon: <Activity className="w-4 h-4 text-primary-600" />
          },
          { 
            title: "Average ESG Score", 
            value: "71.4", 
            change: "+2.1 points", 
            positive: true,
            icon: <FileCheck2 className="w-4 h-4 text-primary-600" />
          },
          { 
            title: "Greenwashing Alerts", 
            value: "142", 
            change: "-5.4%", 
            positive: true,
            icon: <AlertTriangle className="w-4 h-4 text-red-500" />
          },
          { 
            title: "Companies Monitored", 
            value: "840", 
            change: "+34 new", 
            positive: true,
            icon: <Building2 className="w-4 h-4 text-primary-600" />
          }
        ].map((widget, idx) => (
          <motion.div
            key={idx}
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: idx * 0.1 }}
          >
            <Card className="border-neutral-200/60 shadow-sm bg-white">
              <CardContent className="p-5">
                <div className="flex justify-between items-start mb-4">
                  <div className="w-8 h-8 rounded-md bg-neutral-100 flex items-center justify-center">
                    {widget.icon}
                  </div>
                  <div className={`flex items-center text-xs font-semibold ${widget.positive ? 'text-green-600' : 'text-red-600'}`}>
                    {widget.positive ? <TrendingUp className="w-3 h-3 mr-1" /> : <TrendingDown className="w-3 h-3 mr-1" />}
                    {widget.change}
                  </div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-neutral-900 mb-1">{widget.value}</div>
                  <div className="text-sm font-medium text-neutral-500">{widget.title}</div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5, delay: 0.4 }}
        >
          <Card className="border-neutral-200/60 shadow-sm bg-white h-full">
            <CardHeader className="pb-2">
              <CardTitle className="text-neutral-800 text-lg">Industry Comparison Score</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[300px] w-full mt-4">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trendData} margin={{ top: 5, right: 20, bottom: 5, left: -20 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e5e5" />
                    <XAxis 
                      dataKey="month" 
                      axisLine={false} 
                      tickLine={false} 
                      tick={{ fill: '#737373', fontSize: 12 }} 
                      dy={10}
                    />
                    <YAxis 
                      axisLine={false} 
                      tickLine={false} 
                      tick={{ fill: '#737373', fontSize: 12 }}
                    />
                    <Tooltip 
                      contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                    />
                    <Line type="monotone" dataKey="score" name="Your Portfolio" stroke="#16a34a" strokeWidth={3} dot={{ r: 4, fill: '#16a34a' }} activeDot={{ r: 6 }} />
                    <Line type="monotone" dataKey="avg" name="Industry Avg" stroke="#94a3b8" strokeWidth={2} strokeDasharray="5 5" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5, delay: 0.5 }}
        >
          <Card className="border-neutral-200/60 shadow-sm bg-white h-full">
            <CardHeader className="pb-2">
              <CardTitle className="text-neutral-800 text-lg">ESG Risk Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[300px] w-full mt-4">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={riskData} margin={{ top: 5, right: 5, bottom: 5, left: -20 }} barSize={40}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e5e5" />
                    <XAxis 
                      dataKey="name" 
                      axisLine={false} 
                      tickLine={false} 
                      tick={{ fill: '#737373', fontSize: 12 }}
                      dy={10}
                    />
                    <YAxis 
                      axisLine={false} 
                      tickLine={false} 
                      tick={{ fill: '#737373', fontSize: 12 }}
                    />
                    <Tooltip
                      cursor={{ fill: '#f5f5f5' }}
                      contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                    />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
