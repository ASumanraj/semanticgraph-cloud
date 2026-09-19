'use client';

import React, { useState } from 'react';

type Tab = 'Local Upload' | 'Amazon S3' | 'Google Drive' | 'Notion';
type Status = 'Processing' | 'Embedded' | 'Failed';

interface Ingestion {
  id: string;
  filename: string;
  source: string;
  status: Status;
  date: string;
}

const recentIngestions: Ingestion[] = [
  { id: '1', filename: 'Q3_Financial_Report.pdf', source: 'Local Upload', status: 'Embedded', date: '2023-10-25' },
  { id: '2', filename: 'employee_handbook_v2.docx', source: 'Google Drive', status: 'Processing', date: '2023-10-26' },
  { id: '3', filename: 'customer_feedback_dump.csv', source: 'Amazon S3', status: 'Failed', date: '2023-10-26' },
];

export default function ConnectorsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('Local Upload');

  const tabs: Tab[] = ['Local Upload', 'Amazon S3', 'Google Drive', 'Notion'];

  return (
    <div className="p-8 max-w-6xl mx-auto font-sans text-gray-900 dark:text-gray-100">
      <h1 className="text-3xl font-bold mb-6">Data Connectors Hub</h1>
      
      {/* Tabs */}
      <div className="flex space-x-4 border-b border-gray-300 dark:border-gray-700 mb-8 pb-2">
        {tabs.map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium rounded-t-md transition-colors ${
              activeTab === tab
                ? 'border-b-2 border-blue-600 text-blue-600 dark:text-blue-400'
                : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="mb-12">
        {activeTab === 'Local Upload' && (
          <div className="relative p-12 rounded-2xl border border-white/20 bg-white/10 dark:bg-black/10 backdrop-blur-xl shadow-[0_8px_32px_0_rgba(31,38,135,0.37)] flex flex-col items-center justify-center text-center">
            <div className="mb-4 text-gray-600 dark:text-gray-300">
              <svg className="w-16 h-16 mx-auto mb-4 opacity-70" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
              </svg>
              <h3 className="text-xl font-semibold mb-2">Drag & Drop Files Here</h3>
              <p className="text-sm">or click to browse from your computer</p>
            </div>
            <button className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors">
              Select Files
            </button>
          </div>
        )}
        {activeTab === 'Amazon S3' && <div className="p-8 border rounded-lg">Amazon S3 Configuration coming soon...</div>}
        {activeTab === 'Google Drive' && <div className="p-8 border rounded-lg">Google Drive Configuration coming soon...</div>}
        {activeTab === 'Notion' && <div className="p-8 border rounded-lg">Notion Configuration coming soon...</div>}
      </div>

      {/* Recent Ingestions Table */}
      <div>
        <h2 className="text-2xl font-semibold mb-4">Recent Ingestions</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
            <thead className="bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">File Name</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Source</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {recentIngestions.map((item) => (
                <tr key={item.id} className="hover:bg-gray-50 dark:hover:bg-gray-750">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">{item.filename}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">{item.source}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">{item.date}</td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full 
                      ${item.status === 'Embedded' ? 'bg-green-100 text-green-800' : 
                        item.status === 'Processing' ? 'bg-yellow-100 text-yellow-800' : 
                        'bg-red-100 text-red-800'}`}>
                      {item.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
