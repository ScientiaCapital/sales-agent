export function Dashboard() {
  return (
    <div className="space-y-6">
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Welcome to Sales Agent</h2>
        <p className="text-gray-600">
          AI-powered sales automation platform using Cerebras ultra-fast inference.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white shadow rounded-lg p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-2">Lead Qualification</h3>
          <p className="text-sm text-gray-600">
            Intelligent lead scoring with &lt;100ms inference time
          </p>
          <div className="mt-4">
            <span className="text-3xl font-bold text-blue-600">0</span>
            <span className="text-sm text-gray-500 ml-2">leads processed</span>
          </div>
        </div>

        <div className="bg-white shadow rounded-lg p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-2">Research Reports</h3>
          <p className="text-sm text-gray-600">Automated prospect research in &lt;2 minutes</p>
          <div className="mt-4">
            <span className="text-3xl font-bold text-green-600">0</span>
            <span className="text-sm text-gray-500 ml-2">reports generated</span>
          </div>
        </div>

        <div className="bg-white shadow rounded-lg p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-2">Outreach Messages</h3>
          <p className="text-sm text-gray-600">Personalized messages across all channels</p>
          <div className="mt-4">
            <span className="text-3xl font-bold text-purple-600">0</span>
            <span className="text-sm text-gray-500 ml-2">messages sent</span>
          </div>
        </div>
      </div>
    </div>
  );
}
