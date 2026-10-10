import os, datetime
from flask import Flask, request, jsonify, render_template_string
from google import genai

app = Flask(__name__)
readings_db = []

def compute_analytics():
    if not readings_db:
        return {"avg": 0, "min": 0, "max": 0, "counts": {"Normal": 0, "Alert": 0, "Danger": 0}, "trend": "steady"}
    levels = [r["waterLevelCm"] for r in readings_db]
    avg_val = round(sum(levels) / len(levels), 1)
    counts = {"Normal": 0, "Alert": 0, "Danger": 0}
    for lvl in levels:
        if lvl < 100: counts["Normal"] += 1
        elif lvl < 150: counts["Alert"] += 1
        else: counts["Danger"] += 1
    if len(levels) >= 10:
        diff = (sum(levels[:5]) / 5) - (sum(levels[5:10]) / 5)
        trend = "rising" if diff > 1.5 else ("falling" if diff < -1.5 else "steady")
    else: trend = "steady"
    return {"avg": avg_val, "min": min(levels), "max": max(levels), "counts": counts, "trend": trend}

@app.route("/api/readings", methods=["POST"])
def add_reading():
    data = request.get_json() or {}
    sensor_id = data.get("sensorId")
    water_level = data.get("waterLevelCm")
    timestamp = data.get("timestamp") or datetime.datetime.now(datetime.timezone.utc).isoformat()
    if not sensor_id or water_level is None: return jsonify({"error": "Missing field"}), 400
    try: water_level = float(water_level)
    except: return jsonify({"error": "Invalid waterLevelCm"}), 400
    if not (0 <= water_level <= 500): return jsonify({"error": "Out of range"}), 400
    reading = {"sensorId": sensor_id, "waterLevelCm": round(water_level, 1), "timestamp": timestamp}
    readings_db.insert(0, reading)
    if len(readings_db) > 100: readings_db.pop()
    return jsonify({"message": "Reading added", "reading": reading}), 201

@app.route("/api/readings", methods=["GET"])
def get_readings(): return jsonify(readings_db[:50])

@app.route("/api/summary", methods=["GET"])
def get_summary(): return jsonify(compute_analytics())

@app.route("/api/advisory", methods=["POST"])
def generate_advisory():
    summary = compute_analytics()
    latest = readings_db[0]["waterLevelCm"] if readings_db else 0
    fallback = "Water level normal." if latest < 100 else ("ALERT: Elevated water level." if latest < 150 else "DANGER: Critical water level! Evacuate.")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return jsonify({"advisory": fallback, "source": "rule-based"})
    try:
        client = genai.Client(api_key=api_key)
        prompt = f"Generate 3-sentence advisory in English and Filipino for level: {latest}cm, avg: {summary['avg']}cm, trend: {summary['trend']}."
        res = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        return jsonify({"advisory": res.text, "source": "gemini-ai"})
    except: return jsonify({"advisory": fallback, "source": "rule-based-fallback"})

@app.route("/")
def home():
    return render_template_string('''<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width"><title>Bantay Baha</title><script src="https://cdn.jsdelivr.net/npm/chart.js"></script><style>body{font-family:sans-serif;padding:15px;max-width:600px;margin:0 auto;background:#f4f6f8}.card{background:#fff;padding:15px;border-radius:8px;margin-bottom:15px}.status-box{text-align:center;padding:20px;border-radius:8px;color:#fff;font-weight:bold}.status-normal{background:#28a745}.status-alert{background:#fd7e14}.status-danger{background:#dc3545}.water-val{font-size:36px}.btn-adv{width:100%;padding:10px;background:#007bff;color:#fff;border:none;border-radius:5px;cursor:pointer}</style></head><body><h2>🌊 Bantay Baha Flood Monitor</h2><div class="card"><div id="statusCard" class="status-box status-normal"><div id="statusLabel">NORMAL</div><div class="water-val"><span id="waterCm">--</span> cm</div></div><p><strong>Avg:</strong> <span id="statAvg">--</span> cm | <strong>Min:</strong> <span id="statMin">--</span> cm | <strong>Max:</strong> <span id="statMax">--</span> cm</p><p><strong>Trend:</strong> <span id="statTrend">--</span></p><button class="btn-adv" onclick="fetchAdvisory()">📢 Generate Advisory</button><div id="advisoryArea" style="margin-top:10px;font-size:13px;white-space:pre-line"></div></div><div class="card"><h3>Water Level Trend</h3><canvas id="trendChart" style="max-height:200px"></canvas></div><script>let chart;function initChart(){chart=new Chart(document.getElementById("trendChart").getContext("2d"),{type:"line",data:{labels:[],datasets:[{label:"Water Level (cm)",data:[],borderColor:"#007bff",fill:false}]},options:{responsive:true,maintainAspectRatio:false}})}async function updateData(){try{const r=await(await fetch("/api/readings")).json(),s=await(await fetch("/api/summary")).json();if(r.length>0){const c=r[0];document.getElementById("waterCm").innerText=c.waterLevelCm;const b=document.getElementById("statusCard"),l=document.getElementById("statusLabel");b.className="status-box ";if(c.waterLevelCm<100){b.classList.add("status-normal");l.innerText="NORMAL"}else if(c.waterLevelCm<150){b.classList.add("status-alert");l.innerText="ALERT"}else{b.classList.add("status-danger");l.innerText="DANGER"}const cd=r.slice(0,15).reverse();chart.data.labels=cd.map(x=>new Date(x.timestamp).toLocaleTimeString());chart.data.datasets[0].data=cd.map(x=>x.waterLevelCm);chart.update()}document.getElementById("statAvg").innerText=s.avg;document.getElementById("statMin").innerText=s.min;document.getElementById("statMax").innerText=s.max;document.getElementById("statTrend").innerText=s.trend.toUpperCase()}catch(e){}}async function fetchAdvisory(){document.getElementById("advisoryArea").innerText="Generating advisory...";const d=await(await fetch("/api/advisory",{method:"POST"})).json();document.getElementById("advisoryArea").innerText=d.advisory}initChart();updateData();setInterval(updateData,5000);</script></body></html>''')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
