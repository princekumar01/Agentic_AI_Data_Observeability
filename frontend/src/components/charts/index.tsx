import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from 'recharts';

const STYLE = {
  grid: { stroke: 'rgba(255,255,255,0.05)', strokeDasharray: '3 3' },
  axis: { fill: '#8BACC8', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' },
  tooltip: { background: '#0D1E35', border: '1px solid #1A3050', color: '#E8F4FF', fontSize: 12, borderRadius: 8, padding: '8px 12px' },
};

function Wrap({ children, h = 220 }: { children: React.ReactNode; h?: number }) {
  return <ResponsiveContainer width="100%" height={h}>{children as any}</ResponsiveContainer>;
}

// Consumer Lag — backend returns: [{time, lag}]
export function ConsumerLagChart({ data, threshold = 1000 }: { data: any[]; threshold?: number }) {
  return (
    <Wrap>
      <LineChart data={data}>
        <CartesianGrid {...STYLE.grid} />
        <XAxis dataKey="time" tick={STYLE.axis} />
        <YAxis tick={STYLE.axis} />
        <Tooltip contentStyle={STYLE.tooltip} />
        <ReferenceLine y={threshold} stroke="#EF4444" strokeDasharray="4 4"
          label={{ value: `Limit: ${threshold}`, fill: '#EF4444', fontSize: 10, position: 'insideTopRight' }} />
        <Line type="monotone" dataKey="lag" stroke="#F59E0B" strokeWidth={2} dot={false} name="Lag" />
      </LineChart>
    </Wrap>
  );
}

// Throughput — backend returns: [{time, in, out}]
export function ThroughputChart({ data }: { data: any[] }) {
  return (
    <Wrap>
      <AreaChart data={data}>
        <defs>
          <linearGradient id="inGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="outGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#10B981" stopOpacity={0.2} />
            <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid {...STYLE.grid} />
        <XAxis dataKey="time" tick={STYLE.axis} />
        <YAxis tick={STYLE.axis} />
        <Tooltip contentStyle={STYLE.tooltip} />
        <Legend wrapperStyle={{ color: '#8BACC8', fontSize: 11 }} />
        <Area type="monotone" dataKey="in" stroke="#3B82F6" fill="url(#inGrad)" strokeWidth={2} name="In" />
        <Area type="monotone" dataKey="out" stroke="#10B981" fill="url(#outGrad)" strokeWidth={2} name="Out" />
      </AreaChart>
    </Wrap>
  );
}

// Pipeline Runs Bar — backend returns: [{time, completed, failed}]
export function PipelineRunsChart({ data }: { data: any[] }) {
  return (
    <Wrap h={200}>
      <BarChart data={data}>
        <CartesianGrid {...STYLE.grid} />
        <XAxis dataKey="time" tick={STYLE.axis} interval={3} />
        <YAxis tick={STYLE.axis} />
        <Tooltip contentStyle={STYLE.tooltip} />
        <Legend wrapperStyle={{ color: '#8BACC8', fontSize: 11 }} />
        <Bar dataKey="completed" stackId="a" fill="#10B981" name="Completed" />
        <Bar dataKey="failed" stackId="a" fill="#EF4444" name="Failed" radius={[3,3,0,0]} />
      </BarChart>
    </Wrap>
  );
}

// Severity Pie — backend returns: [{name, value, color}]
export function SeverityPieChart({ data }: { data: any[] }) {
  return (
    <Wrap h={200}>
      <PieChart>
        <Pie data={data} cx="50%" cy="50%" innerRadius={55} outerRadius={80} dataKey="value" nameKey="name">
          {data.map((entry, i) => <Cell key={i} fill={entry.color || '#3B82F6'} />)}
        </Pie>
        <Tooltip contentStyle={STYLE.tooltip} />
        <Legend wrapperStyle={{ color: '#8BACC8', fontSize: 11 }} />
      </PieChart>
    </Wrap>
  );
}

// Anomalies Trend — backend returns: [{date, critical, high, medium, low}]
export function AnomaliesTrendChart({ data }: { data: any[] }) {
  return (
    <Wrap h={200}>
      <LineChart data={data}>
        <CartesianGrid {...STYLE.grid} />
        <XAxis dataKey="date" tick={STYLE.axis} />
        <YAxis tick={STYLE.axis} />
        <Tooltip contentStyle={STYLE.tooltip} />
        <Legend wrapperStyle={{ color: '#8BACC8', fontSize: 11 }} />
        <Line type="monotone" dataKey="critical" stroke="#EF4444" strokeWidth={2} dot={false} name="Critical" />
        <Line type="monotone" dataKey="high"     stroke="#F59E0B" strokeWidth={2} dot={false} name="High" />
        <Line type="monotone" dataKey="medium"   stroke="#3B82F6" strokeWidth={2} dot={false} name="Medium" />
        <Line type="monotone" dataKey="low"      stroke="#10B981" strokeWidth={2} dot={false} name="Low" />
      </LineChart>
    </Wrap>
  );
}

// Token Cost Bar — backend returns: [{run, cost}]
export function TokenCostChart({ data }: { data: any[] }) {
  return (
    <Wrap h={200}>
      <BarChart data={data}>
        <CartesianGrid {...STYLE.grid} />
        <XAxis dataKey="run" tick={STYLE.axis} />
        <YAxis tick={STYLE.axis} tickFormatter={v => `$${v}`} />
        <Tooltip contentStyle={STYLE.tooltip} formatter={(v: any) => [`$${Number(v).toFixed(3)}`, 'Cost']} />
        <Bar dataKey="cost" fill="#8B5CF6" radius={[3,3,0,0]} name="Cost (USD)" />
      </BarChart>
    </Wrap>
  );
}

// Run Status Pie — backend returns: [{name, value, color}]
export function RunStatusPieChart({ data }: { data: any[] }) {
  return (
    <Wrap h={200}>
      <PieChart>
        <Pie data={data} cx="50%" cy="50%" innerRadius={50} outerRadius={75} dataKey="value" nameKey="name">
          {data.map((entry, i) => <Cell key={i} fill={entry.color || '#3B82F6'} />)}
        </Pie>
        <Tooltip contentStyle={STYLE.tooltip} />
        <Legend wrapperStyle={{ color: '#8BACC8', fontSize: 11 }} />
      </PieChart>
    </Wrap>
  );
}

// Progress Donut (SVG)
export function ProgressDonut({ pct, size = 120, color = '#3B82F6', label }: { pct: number; size?: number; color?: string; label?: string }) {
  const r = 44, c = 2 * Math.PI * r;
  const dash = (Math.min(Math.max(pct, 0), 100) / 100) * c;
  return (
    <div style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox="0 0 100 100">
        <circle cx="50" cy="50" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="8" />
        <circle cx="50" cy="50" r={r} fill="none" stroke={color} strokeWidth="8"
          strokeDasharray={`${dash} ${c - dash}`} strokeDashoffset={c / 4} strokeLinecap="round"
          style={{ transition: 'stroke-dasharray 0.6s ease' }} />
        <text x="50" y="47" textAnchor="middle" fill="#E8F4FF" fontSize="16" fontFamily="Space Grotesk" fontWeight="700">{pct}%</text>
        {label && <text x="50" y="61" textAnchor="middle" fill="#8BACC8" fontSize="8" fontFamily="Space Grotesk">{label}</text>}
      </svg>
    </div>
  );
}

// Confidence Gauge
export function ConfidenceGauge({ score, size = 80 }: { score: number; size?: number }) {
  const color = score >= 80 ? '#10B981' : score >= 60 ? '#F59E0B' : '#EF4444';
  const r = 35, c = 2 * Math.PI * r;
  const dash = (score / 100) * c;
  return (
    <div style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox="0 0 80 80">
        <circle cx="40" cy="40" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6" />
        <circle cx="40" cy="40" r={r} fill="none" stroke={color} strokeWidth="6"
          strokeDasharray={`${dash} ${c - dash}`} strokeDashoffset={c / 4} strokeLinecap="round" />
        <text x="40" y="44" textAnchor="middle" fill={color} fontSize="14" fontFamily="Space Grotesk" fontWeight="700">{score}</text>
      </svg>
    </div>
  );
}

// Pipeline Health Gauge
export function PipelineHealthGauge({ score, label }: { score: number; label: string }) {
  const color = score >= 90 ? '#10B981' : score >= 70 ? '#F59E0B' : '#EF4444';
  return <ProgressDonut pct={score} size={140} color={color} label={label} />;
}
