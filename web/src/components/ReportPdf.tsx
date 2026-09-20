// PDF report rendered with @react-pdf/renderer. The forecast chart is drawn as
// SVG primitives (band polygon, forecast path, actual dots) so no rasterising
// or canvas is needed and the PDF stays vector and small.

import {
  Document,
  Page,
  Path,
  Polygon,
  StyleSheet,
  Svg,
  Text,
  View,
  Circle,
  Line as SvgLine,
} from "@react-pdf/renderer";
import type { ReportData } from "@/lib/export";
import { markdownToBlocks } from "@/lib/export";

const BLUE = "#2a78d6";
const GREEN = "#1baf7a";
const INK = "#0b0b0b";
const MUTED = "#52514e";
const GRID = "#e1e0d9";

const st = StyleSheet.create({
  page: { padding: 36, fontFamily: "Helvetica", fontSize: 10, color: INK },
  h1: { fontSize: 18, fontFamily: "Helvetica-Bold", marginBottom: 2 },
  sub: { fontSize: 9, color: MUTED, marginBottom: 14 },
  h2: { fontSize: 12.5, fontFamily: "Helvetica-Bold", marginTop: 14, marginBottom: 6, color: BLUE },
  h3: { fontSize: 11, fontFamily: "Helvetica-Bold", marginTop: 8, marginBottom: 3 },
  row: { flexDirection: "row", gap: 8 },
  kpi: { flex: 1, borderWidth: 1, borderColor: GRID, borderRadius: 4, padding: 8 },
  kpiLabel: { fontSize: 7, color: MUTED, textTransform: "uppercase", marginBottom: 3 },
  kpiValue: { fontSize: 14, fontFamily: "Helvetica-Bold" },
  kpiHint: { fontSize: 7.5, color: MUTED, marginTop: 2 },
  table: { borderWidth: 1, borderColor: GRID, borderRadius: 4 },
  tr: { flexDirection: "row", borderBottomWidth: 1, borderBottomColor: GRID, paddingVertical: 3, paddingHorizontal: 6 },
  trLast: { borderBottomWidth: 0 },
  tk: { width: "38%", color: MUTED },
  tv: { width: "62%", fontFamily: "Helvetica-Bold" },
  p: { marginBottom: 4, lineHeight: 1.45 },
  li: { flexDirection: "row", marginBottom: 2.5, paddingLeft: 8 },
  bullet: { width: 10 },
  liText: { flex: 1, lineHeight: 1.4 },
  legend: { flexDirection: "row", gap: 12, marginTop: 4 },
  legendItem: { flexDirection: "row", alignItems: "center", gap: 4, fontSize: 8, color: MUTED },
  swatch: { width: 10, height: 3 },
  footer: { position: "absolute", bottom: 20, left: 36, right: 36, fontSize: 7.5, color: MUTED, flexDirection: "row", justifyContent: "space-between" },
});

const W = 523; // page width minus padding
const H = 200;
const PAD = { l: 44, r: 8, t: 8, b: 22 };

function Chart({ data }: { data: ReportData }) {
  const pts = data.chart;
  if (pts.length < 2) return null;
  const xs = pts.map((p) => new Date(p.ds).getTime());
  const xmin = xs[0];
  const xmax = xs[xs.length - 1];
  const ymax = Math.max(...pts.map((p) => Math.max(p.upper, p.actual ?? 0))) * 1.05;
  const ymin = 0;
  const X = (t: number) => PAD.l + ((t - xmin) / (xmax - xmin)) * (W - PAD.l - PAD.r);
  const Y = (v: number) => PAD.t + (1 - (v - ymin) / (ymax - ymin)) * (H - PAD.t - PAD.b);

  const band = pts.map((p, i) => `${X(xs[i]).toFixed(1)},${Y(p.upper).toFixed(1)}`)
    .concat([...pts].reverse().map((p, i) => `${X(xs[pts.length - 1 - i]).toFixed(1)},${Y(p.lower).toFixed(1)}`))
    .join(" ");
  const line = pts.map((p, i) => `${i === 0 ? "M" : "L"}${X(xs[i]).toFixed(1)} ${Y(p.predicted).toFixed(1)}`).join(" ");
  const split = X(new Date(data.lastActualDate).getTime());

  // y ticks
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => ymin + f * (ymax - ymin));
  const fmt = (v: number) =>
    v >= 1e6 ? `$${(v / 1e6).toFixed(1)}M` : v >= 1e3 ? `$${(v / 1e3).toFixed(v < 1e4 ? 1 : 0)}K` : `$${v.toFixed(0)}`;
  // x labels: 5 evenly spaced
  const xl = [0, 0.25, 0.5, 0.75, 1].map((f) => xmin + f * (xmax - xmin));

  return (
    <View>
      <Svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
        {ticks.map((v) => (
          <SvgLine key={v} x1={PAD.l} x2={W - PAD.r} y1={Y(v)} y2={Y(v)} stroke={GRID} strokeWidth={0.5} />
        ))}
        {ticks.map((v) => (
          <Text key={`t${v}`} x={PAD.l - 4} y={Y(v) + 2.5} style={{ fontSize: 7, fill: MUTED }} textAnchor="end">
            {fmt(v)}
          </Text>
        ))}
        {xl.map((t) => (
          <Text key={`x${t}`} x={X(t)} y={H - 6} style={{ fontSize: 7, fill: MUTED }} textAnchor="middle">
            {new Date(t).toLocaleDateString("en-US", { month: "short", year: "2-digit" })}
          </Text>
        ))}
        <Polygon points={band} fill={BLUE} fillOpacity={0.14} stroke="none" />
        <Path d={line} stroke={BLUE} strokeWidth={1.5} fill="none" />
        {pts.map((p, i) =>
          p.actual !== undefined ? <Circle key={i} cx={X(xs[i])} cy={Y(p.actual)} r={1.6} fill={GREEN} fillOpacity={0.85} /> : null,
        )}
        <SvgLine x1={split} x2={split} y1={PAD.t} y2={H - PAD.b} stroke={MUTED} strokeWidth={0.6} strokeDasharray="3 3" />
      </Svg>
      <View style={st.legend}>
        <View style={st.legendItem}><View style={[st.swatch, { backgroundColor: BLUE }]} /><Text>Forecast</Text></View>
        <View style={st.legendItem}><View style={[st.swatch, { backgroundColor: BLUE, opacity: 0.2, height: 8 }]} /><Text>95% interval</Text></View>
        <View style={st.legendItem}><View style={[st.swatch, { backgroundColor: GREEN, height: 6, width: 6, borderRadius: 3 }]} /><Text>Actual</Text></View>
      </View>
    </View>
  );
}

function KV({ rows }: { rows: [string, string][] }) {
  return (
    <View style={st.table}>
      {rows.map(([k, v], i) => (
        <View key={k} style={[st.tr, i === rows.length - 1 ? st.trLast : {}]}>
          <Text style={st.tk}>{k}</Text>
          <Text style={st.tv}>{v}</Text>
        </View>
      ))}
    </View>
  );
}

export function ReportPdf({ data }: { data: ReportData }) {
  const blocks = data.reportMarkdown ? markdownToBlocks(data.reportMarkdown) : [];
  return (
    <Document title={data.title} author="Multi-Agent AI Business Consultant">
      <Page size="A4" style={st.page}>
        <Text style={st.h1}>{data.title}</Text>
        <Text style={st.sub}>Generated {data.generatedAt} · Multi-Agent AI Business Consultant</Text>

        <View style={st.row}>
          {data.kpis.map((k) => (
            <View key={k.label} style={st.kpi}>
              <Text style={st.kpiLabel}>{k.label}</Text>
              <Text style={st.kpiValue}>{k.value}</Text>
              {k.hint ? <Text style={st.kpiHint}>{k.hint}</Text> : null}
            </View>
          ))}
        </View>

        <Text style={st.h2}>Revenue forecast (Prophet)</Text>
        <Chart data={data} />

        <Text style={st.h2}>Data & forecast details</Text>
        <KV rows={data.detection} />

        {data.accuracy && (
          <>
            <Text style={st.h2}>Model accuracy (backtest)</Text>
            <KV rows={data.accuracy} />
          </>
        )}

        <View style={st.footer} fixed>
          <Text>Multi-Agent AI Business Consultant</Text>
          <Text render={({ pageNumber, totalPages }) => `${pageNumber} / ${totalPages}`} />
        </View>
      </Page>

      {(data.whatif || blocks.length > 0) && (
        <Page size="A4" style={st.page}>
          {data.whatif && (
            <>
              <Text style={st.h2}>What-if scenarios</Text>
              <View style={st.table}>
                {data.whatif.map((w, i) => (
                  <View key={w.label} style={[st.tr, i === data.whatif!.length - 1 ? st.trLast : {}]}>
                    <Text style={{ width: "50%" }}>{w.label}</Text>
                    <Text style={{ width: "28%", fontFamily: "Helvetica-Bold" }}>{w.total}</Text>
                    <Text style={{ width: "22%", color: MUTED }}>{w.delta}</Text>
                  </View>
                ))}
              </View>
            </>
          )}

          {blocks.length > 0 && (
            <>
              <Text style={st.h2}>Strategic recommendations</Text>
              {blocks.map((b, i) =>
                b.kind === "h" ? (
                  <Text key={i} style={st.h3}>{b.text}</Text>
                ) : b.kind === "li" ? (
                  <View key={i} style={st.li}>
                    <Text style={st.bullet}>•</Text>
                    <Text style={st.liText}>{b.text}</Text>
                  </View>
                ) : (
                  <Text key={i} style={st.p}>{b.text}</Text>
                ),
              )}
            </>
          )}

          <View style={st.footer} fixed>
            <Text>Multi-Agent AI Business Consultant</Text>
            <Text render={({ pageNumber, totalPages }) => `${pageNumber} / ${totalPages}`} />
          </View>
        </Page>
      )}
    </Document>
  );
}
