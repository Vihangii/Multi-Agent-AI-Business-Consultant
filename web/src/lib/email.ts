// Monthly forecast email: HTML built from the API result, sent with Resend.

import { Resend } from "resend";
import { fmtDate, fmtMoney, fmtPct } from "./format";
import type { AnalyzeResult } from "./types";

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/** Minimal markdown → HTML for the email body (headings, bullets, bold, paragraphs). */
export function markdownToHtml(md: string): string {
  const lines = md.split("\n");
  const html: string[] = [];
  let inList = false;
  const closeList = () => {
    if (inList) {
      html.push("</ul>");
      inList = false;
    }
  };
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) {
      closeList();
      continue;
    }
    const inline = esc(line).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`(.+?)`/g, "<code>$1</code>");
    const h = /^(#{1,6})\s+(.*)$/.exec(inline);
    if (h) {
      closeList();
      const lvl = Math.min(3, h[1].length + 1);
      html.push(`<h${lvl} style="margin:16px 0 6px;font-size:${lvl === 2 ? 17 : 14}px">${h[2]}</h${lvl}>`);
    } else if (/^([-*•]|\d+\.)\s/.test(inline)) {
      if (!inList) {
        html.push('<ul style="margin:4px 0 8px 18px;padding:0">');
        inList = true;
      }
      html.push(`<li style="margin:3px 0">${inline.replace(/^([-*•]|\d+\.)\s*/, "")}</li>`);
    } else {
      closeList();
      html.push(`<p style="margin:6px 0;line-height:1.5">${inline}</p>`);
    }
  }
  closeList();
  return html.join("\n");
}

export function buildEmail(result: AnalyzeResult, opts: { fileName: string; appUrl: string; unsubscribeUrl: string }) {
  const a = result.analysis;
  const fs = result.forecast_summary;
  const acc = fs.accuracy;
  const kpi = (label: string, value: string) =>
    `<td style="padding:10px 12px;border:1px solid #e1e0d9;border-radius:6px;vertical-align:top">
       <div style="font-size:10px;letter-spacing:.05em;text-transform:uppercase;color:#52514e">${esc(label)}</div>
       <div style="font-size:20px;font-weight:700;margin-top:4px">${esc(value)}</div>
     </td>`;

  const subject = `Monthly revenue forecast — ${opts.fileName} (${fs.forecast_trend}, ${fmtPct(fs.predicted_growth_percent, { sign: true })})`;

  const html = `<!doctype html><html><body style="margin:0;background:#f9f9f7;font-family:system-ui,-apple-system,Segoe UI,sans-serif;color:#0b0b0b">
  <div style="max-width:640px;margin:0 auto;padding:24px">
    <h1 style="font-size:20px;margin:0 0 4px">Monthly revenue forecast</h1>
    <div style="font-size:12px;color:#52514e;margin-bottom:16px">${esc(opts.fileName)} · ${esc(fmtDate(a.date_range.start))} → ${esc(fmtDate(a.date_range.end))} · generated ${esc(new Date().toLocaleDateString())}</div>
    <table cellspacing="8" style="border-collapse:separate;width:100%"><tr>
      ${kpi("Total revenue", fmtMoney(a.revenue.total))}
      ${kpi("Historical growth", fmtPct(a.growth?.overall_percent, { sign: true }))}
      ${kpi("Forecast outlook", fmtPct(fs.predicted_growth_percent, { sign: true }))}
      ${kpi("Horizon end", fmtMoney(fs.forecast_end_value))}
    </tr></table>
    <p style="font-size:13px;color:#52514e;margin:12px 0">
      Peak forecast ${esc(fmtMoney(fs.peak_forecasted_value))} on ${esc(fmtDate(fs.peak_forecasted_date))}.
      ${acc ? `Model accuracy: MAPE ${esc(fmtPct(acc.mape_percent, { digits: 1 }))} (${esc(acc.rating)}), 95% interval coverage ${esc(fmtPct(acc.interval_coverage_percent, { digits: 0 }))}.` : ""}
    </p>
    ${result.recommendations ? `<div style="background:#fff;border:1px solid #e1e0d9;border-radius:8px;padding:16px;font-size:13px">${markdownToHtml(result.recommendations)}</div>`
      : result.recommendations_error ? `<p style="font-size:13px;color:#b02a2a">AI recommendations unavailable: ${esc(result.recommendations_error)}</p>` : ""}
    <p style="margin-top:20px"><a href="${esc(opts.appUrl)}" style="display:inline-block;background:#2a78d6;color:#fff;text-decoration:none;padding:10px 16px;border-radius:6px;font-size:13px">Open the dashboard</a></p>
    <p style="font-size:11px;color:#898781;margin-top:24px">You receive this because a monthly re-run was scheduled for this dataset. <a href="${esc(opts.unsubscribeUrl)}" style="color:#898781">Unsubscribe</a></p>
  </div></body></html>`;

  return { subject, html };
}

export async function sendEmail(to: string, subject: string, html: string): Promise<void> {
  const resend = new Resend(process.env.RESEND_API_KEY);
  const from = process.env.EMAIL_FROM ?? "AI Business Consultant <onboarding@resend.dev>";
  const { error } = await resend.emails.send({ from, to, subject, html });
  if (error) throw new Error(error.message);
}
