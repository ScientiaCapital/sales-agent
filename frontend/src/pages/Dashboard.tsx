import { Link } from 'react-router-dom';
import {
  TrendingUp,
  Users,
  MessageSquare,
  FileText,
  Zap,
  ArrowRight,
  Target,
  Brain,
  Phone
} from 'lucide-react';

export function Dashboard() {
  return (
    <div className="space-y-8">
      {/* Hero Section */}
      <div className="relative bg-gradient-to-br from-indigo-600 via-purple-600 to-pink-600 rounded-2xl shadow-xl overflow-hidden">
        <div className="absolute inset-0 bg-black opacity-10"></div>
        <div className="relative px-8 py-12">
          <h1 className="text-4xl font-bold text-white mb-3">
            Welcome to Sales Agent
          </h1>
          <p className="text-indigo-100 text-lg max-w-2xl">
            AI-powered sales automation platform with Cerebras ultra-fast inference,
            multi-agent intelligence, and real-time conversation analytics.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              to="/leads"
              className="inline-flex items-center px-6 py-3 bg-white text-indigo-600 rounded-lg font-semibold hover:bg-indigo-50 transition-all shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
            >
              <Users className="w-5 h-5 mr-2" />
              Manage Leads
              <ArrowRight className="w-4 h-4 ml-2" />
            </Link>
            <Link
              to="/campaigns"
              className="inline-flex items-center px-6 py-3 bg-indigo-500 text-white rounded-lg font-semibold hover:bg-indigo-400 transition-all shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
            >
              <MessageSquare className="w-5 h-5 mr-2" />
              Create Campaign
              <ArrowRight className="w-4 h-4 ml-2" />
            </Link>
          </div>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Lead Qualification */}
        <div className="bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow border border-gray-100 overflow-hidden">
          <div className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="p-3 bg-blue-50 rounded-lg">
                <Target className="w-6 h-6 text-blue-600" />
              </div>
              <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-700">
                <Zap className="w-3 h-3 mr-1" />
                633ms avg
              </span>
            </div>
            <h3 className="text-sm font-medium text-gray-500 mb-1">Lead Qualification</h3>
            <div className="flex items-baseline">
              <span className="text-3xl font-bold text-gray-900">0</span>
              <span className="text-sm text-gray-500 ml-2">leads qualified</span>
            </div>
            <p className="text-sm text-gray-600 mt-2">
              Cerebras AI scoring with &lt;1s inference
            </p>
          </div>
          <div className="bg-gradient-to-r from-blue-50 to-blue-100 px-6 py-3">
            <Link to="/leads" className="text-sm font-medium text-blue-700 hover:text-blue-800 flex items-center">
              View all leads
              <ArrowRight className="w-4 h-4 ml-1" />
            </Link>
          </div>
        </div>

        {/* Research Reports */}
        <div className="bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow border border-gray-100 overflow-hidden">
          <div className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="p-3 bg-green-50 rounded-lg">
                <Brain className="w-6 h-6 text-green-600" />
              </div>
              <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-green-100 text-green-700">
                5 agents
              </span>
            </div>
            <h3 className="text-sm font-medium text-gray-500 mb-1">Research Reports</h3>
            <div className="flex items-baseline">
              <span className="text-3xl font-bold text-gray-900">0</span>
              <span className="text-sm text-gray-500 ml-2">reports generated</span>
            </div>
            <p className="text-sm text-gray-600 mt-2">
              Automated multi-agent research in &lt;10s
            </p>
          </div>
          <div className="bg-gradient-to-r from-green-50 to-green-100 px-6 py-3">
            <Link to="/research" className="text-sm font-medium text-green-700 hover:text-green-800 flex items-center">
              Start research
              <ArrowRight className="w-4 h-4 ml-1" />
            </Link>
          </div>
        </div>

        {/* Outreach Messages */}
        <div className="bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow border border-gray-100 overflow-hidden">
          <div className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="p-3 bg-purple-50 rounded-lg">
                <MessageSquare className="w-6 h-6 text-purple-600" />
              </div>
              <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-purple-100 text-purple-700">
                3 variants
              </span>
            </div>
            <h3 className="text-sm font-medium text-gray-500 mb-1">Outreach Messages</h3>
            <div className="flex items-baseline">
              <span className="text-3xl font-bold text-gray-900">0</span>
              <span className="text-sm text-gray-500 ml-2">messages sent</span>
            </div>
            <p className="text-sm text-gray-600 mt-2">
              AI-generated with A/B testing
            </p>
          </div>
          <div className="bg-gradient-to-r from-purple-50 to-purple-100 px-6 py-3">
            <Link to="/campaigns" className="text-sm font-medium text-purple-700 hover:text-purple-800 flex items-center">
              Manage campaigns
              <ArrowRight className="w-4 h-4 ml-1" />
            </Link>
          </div>
        </div>

        {/* Conversations */}
        <div className="bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow border border-gray-100 overflow-hidden">
          <div className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="p-3 bg-orange-50 rounded-lg">
                <Phone className="w-6 h-6 text-orange-600" />
              </div>
              <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-orange-100 text-orange-700">
                Live
              </span>
            </div>
            <h3 className="text-sm font-medium text-gray-500 mb-1">Conversations</h3>
            <div className="flex items-baseline">
              <span className="text-3xl font-bold text-gray-900">0</span>
              <span className="text-sm text-gray-500 ml-2">calls tracked</span>
            </div>
            <p className="text-sm text-gray-600 mt-2">
              Real-time intelligence & transcripts
            </p>
          </div>
          <div className="bg-gradient-to-r from-orange-50 to-orange-100 px-6 py-3">
            <Link to="/conversations" className="text-sm font-medium text-orange-700 hover:text-orange-800 flex items-center">
              View conversations
              <ArrowRight className="w-4 h-4 ml-1" />
            </Link>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">Quick Actions</h2>
        </div>
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Link
              to="/leads"
              className="group flex items-center p-4 bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg hover:from-blue-100 hover:to-indigo-100 transition-all border border-blue-100"
            >
              <div className="p-3 bg-blue-600 rounded-lg mr-4 group-hover:scale-110 transition-transform">
                <Target className="w-5 h-5 text-white" />
              </div>
              <div>
                <p className="font-semibold text-gray-900">Qualify Lead</p>
                <p className="text-sm text-gray-600">AI-powered scoring</p>
              </div>
              <ArrowRight className="w-5 h-5 text-gray-400 ml-auto group-hover:text-blue-600 group-hover:translate-x-1 transition-all" />
            </Link>

            <Link
              to="/research"
              className="group flex items-center p-4 bg-gradient-to-br from-green-50 to-emerald-50 rounded-lg hover:from-green-100 hover:to-emerald-100 transition-all border border-green-100"
            >
              <div className="p-3 bg-green-600 rounded-lg mr-4 group-hover:scale-110 transition-transform">
                <Brain className="w-5 h-5 text-white" />
              </div>
              <div>
                <p className="font-semibold text-gray-900">Research Company</p>
                <p className="text-sm text-gray-600">5-agent pipeline</p>
              </div>
              <ArrowRight className="w-5 h-5 text-gray-400 ml-auto group-hover:text-green-600 group-hover:translate-x-1 transition-all" />
            </Link>

            <Link
              to="/campaigns"
              className="group flex items-center p-4 bg-gradient-to-br from-purple-50 to-pink-50 rounded-lg hover:from-purple-100 hover:to-pink-100 transition-all border border-purple-100"
            >
              <div className="p-3 bg-purple-600 rounded-lg mr-4 group-hover:scale-110 transition-transform">
                <MessageSquare className="w-5 h-5 text-white" />
              </div>
              <div>
                <p className="font-semibold text-gray-900">Create Campaign</p>
                <p className="text-sm text-gray-600">Multi-channel outreach</p>
              </div>
              <ArrowRight className="w-5 h-5 text-gray-400 ml-auto group-hover:text-purple-600 group-hover:translate-x-1 transition-all" />
            </Link>
          </div>
        </div>
      </div>

      {/* Platform Features */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* AI-Powered Features */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="px-6 py-4 bg-gradient-to-r from-indigo-50 to-purple-50 border-b border-gray-100">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center">
              <Zap className="w-5 h-5 text-indigo-600 mr-2" />
              AI-Powered Features
            </h2>
          </div>
          <div className="p-6 space-y-4">
            <div className="flex items-start">
              <div className="p-2 bg-blue-100 rounded-lg mr-3">
                <Target className="w-4 h-4 text-blue-600" />
              </div>
              <div>
                <h3 className="font-medium text-gray-900">Lead Qualification</h3>
                <p className="text-sm text-gray-600">
                  Cerebras AI scoring with 633ms average latency
                </p>
              </div>
            </div>

            <div className="flex items-start">
              <div className="p-2 bg-green-100 rounded-lg mr-3">
                <Brain className="w-4 h-4 text-green-600" />
              </div>
              <div>
                <h3 className="font-medium text-gray-900">Multi-Agent Research</h3>
                <p className="text-sm text-gray-600">
                  5-agent pipeline for deep prospect intelligence
                </p>
              </div>
            </div>

            <div className="flex items-start">
              <div className="p-2 bg-purple-100 rounded-lg mr-3">
                <MessageSquare className="w-4 h-4 text-purple-600" />
              </div>
              <div>
                <h3 className="font-medium text-gray-900">Message Generation</h3>
                <p className="text-sm text-gray-600">
                  3 variants per message with A/B testing analytics
                </p>
              </div>
            </div>

            <div className="flex items-start">
              <div className="p-2 bg-orange-100 rounded-lg mr-3">
                <Phone className="w-4 h-4 text-orange-600" />
              </div>
              <div>
                <h3 className="font-medium text-gray-900">Voice Intelligence</h3>
                <p className="text-sm text-gray-600">
                  Real-time transcription with sentiment analysis
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Recent Activity */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="px-6 py-4 bg-gradient-to-r from-gray-50 to-slate-50 border-b border-gray-100">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center">
              <TrendingUp className="w-5 h-5 text-gray-600 mr-2" />
              Getting Started
            </h2>
          </div>
          <div className="p-6 space-y-3">
            <div className="flex items-center p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
              <div className="flex-shrink-0 w-8 h-8 bg-indigo-600 rounded-full flex items-center justify-center text-white font-semibold text-sm">
                1
              </div>
              <div className="ml-3 flex-1">
                <p className="text-sm font-medium text-gray-900">Add your first lead</p>
                <p className="text-xs text-gray-500">Navigate to Leads page or import CSV</p>
              </div>
            </div>

            <div className="flex items-center p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
              <div className="flex-shrink-0 w-8 h-8 bg-indigo-600 rounded-full flex items-center justify-center text-white font-semibold text-sm">
                2
              </div>
              <div className="ml-3 flex-1">
                <p className="text-sm font-medium text-gray-900">Run research on a prospect</p>
                <p className="text-xs text-gray-500">Use the 5-agent research pipeline</p>
              </div>
            </div>

            <div className="flex items-center p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
              <div className="flex-shrink-0 w-8 h-8 bg-indigo-600 rounded-full flex items-center justify-center text-white font-semibold text-sm">
                3
              </div>
              <div className="ml-3 flex-1">
                <p className="text-sm font-medium text-gray-900">Create your first campaign</p>
                <p className="text-xs text-gray-500">Generate personalized outreach messages</p>
              </div>
            </div>

            <div className="flex items-center p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
              <div className="flex-shrink-0 w-8 h-8 bg-indigo-600 rounded-full flex items-center justify-center text-white font-semibold text-sm">
                4
              </div>
              <div className="ml-3 flex-1">
                <p className="text-sm font-medium text-gray-900">Monitor conversations</p>
                <p className="text-xs text-gray-500">Track calls with real-time intelligence</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Platform Stats */}
      <div className="bg-gradient-to-br from-slate-50 to-gray-50 rounded-xl border border-gray-200 p-8">
        <h2 className="text-xl font-bold text-gray-900 mb-6">Platform Capabilities</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div className="text-center">
            <div className="text-3xl font-bold text-indigo-600 mb-1">633ms</div>
            <div className="text-sm text-gray-600">Avg Qualification Time</div>
            <div className="text-xs text-gray-500 mt-1">Cerebras AI</div>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold text-green-600 mb-1">&lt;10s</div>
            <div className="text-sm text-gray-600">Research Pipeline</div>
            <div className="text-xs text-gray-500 mt-1">5 AI Agents</div>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold text-purple-600 mb-1">100%</div>
            <div className="text-sm text-gray-600">A/B Test Coverage</div>
            <div className="text-xs text-gray-500 mt-1">All Campaigns</div>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold text-orange-600 mb-1">&lt;100ms</div>
            <div className="text-sm text-gray-600">Voice Latency</div>
            <div className="text-xs text-gray-500 mt-1">Real-time WebSocket</div>
          </div>
        </div>
      </div>

      {/* CTA Banner */}
      <div className="bg-gradient-to-r from-indigo-600 to-purple-600 rounded-xl shadow-lg overflow-hidden">
        <div className="px-8 py-6 flex items-center justify-between">
          <div>
            <h3 className="text-xl font-bold text-white mb-2">
              Ready to automate your sales process?
            </h3>
            <p className="text-indigo-100">
              Start with importing leads or creating your first campaign
            </p>
          </div>
          <div className="flex gap-3">
            <Link
              to="/csv-import"
              className="px-6 py-3 bg-white text-indigo-600 rounded-lg font-semibold hover:bg-indigo-50 transition-all shadow-lg hover:shadow-xl"
            >
              Import Leads
            </Link>
            <Link
              to="/campaigns"
              className="px-6 py-3 bg-indigo-500 text-white rounded-lg font-semibold hover:bg-indigo-400 transition-all shadow-lg hover:shadow-xl border-2 border-white border-opacity-20"
            >
              New Campaign
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
