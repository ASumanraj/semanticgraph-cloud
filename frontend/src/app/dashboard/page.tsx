"use client";

import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const extractionData = [
  { time: '08:00', volume: 400 },
  { time: '09:00', volume: 300 },
  { time: '10:00', volume: 550 },
  { time: '11:00', volume: 450 },
  { time: '12:00', volume: 700 },
  { time: '13:00', volume: 600 },
];

const activityFeed = [
  { id: 1, message: "Gemini LLM extracted 15 entities from doc_42", time: "2 mins ago", status: "success" },
  { id: 2, message: "Gemini LLM extraction failed for doc_43: Rate limit", time: "15 mins ago", status: "error" },
  { id: 3, message: "Gemini LLM extracted 8 entities from doc_44", time: "1 hour ago", status: "success" },
];

export default function MetricsDashboard() {
  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <h1 className="text-3xl font-bold mb-6">Metrics & Observability Dashboard</h1>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-white p-6 rounded-lg shadow border">
          <h3 className="text-gray-500 text-sm font-medium">Total Entities Extracted</h3>
          <p className="text-3xl font-bold mt-2">24,592</p>
        </div>
        <div className="bg-white p-6 rounded-lg shadow border">
          <h3 className="text-gray-500 text-sm font-medium">Tokens Used</h3>
          <p className="text-3xl font-bold mt-2">1.2M</p>
        </div>
        <div className="bg-white p-6 rounded-lg shadow border">
          <h3 className="text-gray-500 text-sm font-medium">Average Latency</h3>
          <p className="text-3xl font-bold mt-2">450ms</p>
        </div>
      </div>

      {/* Chart and Feed Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chart */}
        <div className="lg:col-span-2 bg-white p-6 rounded-lg shadow border">
          <h2 className="text-xl font-semibold mb-4">Extraction Volume over Time</h2>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={extractionData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorVolume" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#8884d8" stopOpacity={0.8}/>
                    <stop offset="95%" stopColor="#8884d8" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" />
                <YAxis />
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <Tooltip />
                <Area type="monotone" dataKey="volume" stroke="#8884d8" fillOpacity={1} fill="url(#colorVolume)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Activity Feed */}
        <div className="bg-white p-6 rounded-lg shadow border">
          <h2 className="text-xl font-semibold mb-4">Recent Activity Feed</h2>
          <div className="space-y-4">
            {activityFeed.map((activity) => (
              <div key={activity.id} className="border-b pb-3 last:border-0 last:pb-0">
                <p className={`text-sm ${activity.status === 'error' ? 'text-red-600' : 'text-gray-800'}`}>
                  {activity.message}
                </p>
                <p className="text-xs text-gray-400 mt-1">{activity.time}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
