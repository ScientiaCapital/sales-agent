"""
Weekly Meeting Dashboard - CEO/CTO Meeting
Shows THIS WEEK's accomplishments and KPIs

Run on http://localhost:8000
"""

import http.server
import socketserver
from datetime import datetime

PORT = 8000

dashboard_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Week of Nov 18-19, 2025 - Pipeline Performance</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
            background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
            color: #fff;
            padding: 40px;
            min-height: 100vh;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .header {
            text-align: center;
            margin-bottom: 50px;
            padding-bottom: 30px;
            border-bottom: 3px solid #4CAF50;
        }
        h1 {
            font-size: 3em;
            font-weight: 700;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .date { font-size: 1.2em; color: #aaa; }
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 25px;
            margin-bottom: 50px;
        }
        .metric-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            padding: 30px;
            text-align: center;
            border: 2px solid rgba(76, 175, 80, 0.3);
            transition: all 0.3s;
        }
        .metric-card:hover {
            transform: translateY(-5px);
            border-color: #4CAF50;
            box-shadow: 0 10px 30px rgba(76, 175, 80, 0.3);
        }
        .metric-value {
            font-size: 3.5em;
            font-weight: 700;
            color: #4CAF50;
            margin: 15px 0;
        }
        .metric-label {
            font-size: 1.1em;
            color: #ccc;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .lists-section {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            padding: 40px;
            margin-bottom: 30px;
        }
        h2 {
            font-size: 2em;
            margin-bottom: 30px;
            color: #4CAF50;
        }
        .list-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .list-item {
            background: rgba(255, 255, 255, 0.03);
            padding: 25px;
            border-radius: 10px;
            border-left: 4px solid #4CAF50;
        }
        .list-title {
            font-size: 1.3em;
            font-weight: 600;
            margin-bottom: 10px;
            color: #fff;
        }
        .list-count {
            font-size: 2em;
            color: #4CAF50;
            font-weight: 700;
        }
        .list-desc {
            color: #aaa;
            margin-top: 10px;
            line-height: 1.6;
        }
        .tech-stack {
            background: rgba(255, 255, 255, 0.03);
            padding: 30px;
            border-radius: 10px;
            margin-top: 30px;
        }
        .tech-tag {
            display: inline-block;
            background: rgba(76, 175, 80, 0.2);
            padding: 8px 15px;
            border-radius: 20px;
            margin: 5px;
            font-size: 0.9em;
            border: 1px solid rgba(76, 175, 80, 0.3);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 This Week's Pipeline Performance</h1>
            <div class="date">November 18-19, 2025</div>
        </div>

        <div class="summary">
            <div class="metric-card">
                <div class="metric-label">Fresh Prospects</div>
                <div class="metric-value">809</div>
                <div class="metric-label">All Verified NEW</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Winback Pipeline</div>
                <div class="metric-value">225</div>
                <div class="metric-label">Churned + Lost</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Total Opportunities</div>
                <div class="metric-value">1,034</div>
                <div class="metric-label">Ready to Engage</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Deduplication Rate</div>
                <div class="metric-value">100%</div>
                <div class="metric-label">3,820 Cached Leads</div>
            </div>
        </div>

        <div class="lists-section">
            <h2>📋 Four Targeted Lists Delivered</h2>
            <div class="list-grid">
                <div class="list-item">
                    <div class="list-title">1. Multi-State MEP</div>
                    <div class="list-count">21 Companies</div>
                    <div class="list-desc">
                        ✅ Bicoastal operators (FL+TX+NY)<br>
                        ✅ Multi-trade capability<br>
                        ✅ 20 electrical, 19 HVAC, 10 solar
                    </div>
                </div>
                <div class="list-item">
                    <div class="list-title">2. License-OEM Overlap</div>
                    <div class="list-count">288 Companies</div>
                    <div class="list-desc">
                        ✅ Dual-verified contractors<br>
                        ✅ State license + OEM partnerships<br>
                        ✅ Established credibility
                    </div>
                </div>
                <div class="list-item">
                    <div class="list-title">3. Top 500 MEP Prospects</div>
                    <div class="list-count">500 Companies</div>
                    <div class="list-desc">
                        ✅ Highest composite scores<br>
                        ✅ Priority targets<br>
                        ✅ Coperniq scoring + tenure + licenses
                    </div>
                </div>
                <div class="list-item">
                    <div class="list-title">4. Winback Campaign</div>
                    <div class="list-count">225 Companies</div>
                    <div class="list-desc">
                        ✅ Churned leads + Lost opportunities<br>
                        ✅ Ready for re-engagement<br>
                        ✅ New decision-maker discovery
                    </div>
                </div>
            </div>
        </div>

        <div class="lists-section">
            <h2>🔧 Technical Accomplishments</h2>
            <div class="tech-stack">
                <div class="tech-tag">✅ Apollo API Integration</div>
                <div class="tech-tag">✅ Close CRM Deduplication</div>
                <div class="tech-tag">✅ SQLite Cache (3,820 leads)</div>
                <div class="tech-tag">✅ Fuzzy Matching (85% threshold)</div>
                <div class="tech-tag">✅ Rate Limit Handling</div>
                <div class="tech-tag">✅ CSV Import Pipeline</div>
                <div class="tech-tag">✅ Multi-Source Integration</div>
                <div class="tech-tag">✅ Automated Workflows</div>
            </div>
            <div style="margin-top: 30px; padding: 20px; background: rgba(76, 175, 80, 0.1); border-radius: 10px; border-left: 4px solid #4CAF50;">
                <strong style="color: #4CAF50;">Quality Assurance:</strong><br>
                • All 809 fresh prospects verified as NEW (no Close CRM duplicates)<br>
                • Safe import mode enabled (CSV-only, no accidental writes)<br>
                • Complete audit trail with timestamps<br>
                • Ready for immediate sales engagement
            </div>
        </div>

        <div class="lists-section">
            <h2>📂 Files Location</h2>
            <div style="background: rgba(0,0,0,0.3); padding: 20px; border-radius: 10px; font-family: monospace;">
                <div style="color: #4CAF50; margin-bottom: 10px;">backend/data/final_enrichment_output/</div>
                <div style="padding-left: 20px; line-height: 2;">
                    📄 1_multi_state_mep_21_companies.csv<br>
                    📄 2_license_oem_overlap_288_companies.csv<br>
                    📄 3_top_500_mep_prospects.csv<br>
                    📄 4_winback_campaign_225_companies.csv
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""

class MyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(dashboard_html.encode())

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"🚀 WEEKLY MEETING DASHBOARD")
    print(f"{'='*60}")
    print(f"\n📊 Dashboard running at: http://localhost:{PORT}")
    print(f"\n✅ This Week's Summary:")
    print(f"   • 809 Fresh MEP Prospects")
    print(f"   • 225 Winback Companies")
    print(f"   • 100% Deduplicated")
    print(f"   • 4 Targeted Lists Ready")
    print(f"\n👉 Open http://localhost:{PORT} in your browser")
    print(f"{'='*60}\n")

    with socketserver.TCPServer(("", PORT), MyHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n✅ Dashboard stopped")
