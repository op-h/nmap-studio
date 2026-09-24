"""Export a parsed ScanResult to CSV / JSON / Markdown / HTML, and diff two scans."""
from __future__ import annotations

import csv
import html
import io
import json
import time
from dataclasses import asdict

from .parser import ScanResult


CSV_COLUMNS = ["host", "hostname", "mac", "host_state", "os", "os_accuracy",
               "protocol", "port", "state", "reason", "service", "product",
               "version", "extrainfo", "cpe", "scripts"]


def to_csv(result: ScanResult, only_open: bool = False) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    for host in result.hosts:
        ports = host.open_ports if only_open else host.ports
        if not ports:
            writer.writerow([host.ip, host.hostname, host.mac, host.state, host.best_os,
                             host.os_accuracy or "", "", "", "", "", "", "", "", "", "", ""])
            continue
        for port in ports:
            svc = port.service
            writer.writerow([
                host.ip, host.hostname, host.mac, host.state, host.best_os,
                host.os_accuracy or "", port.protocol, port.portid, port.state, port.reason,
                svc.name, svc.product, svc.version, svc.extrainfo,
                ";".join(svc.cpes), " | ".join(f"{k}: {v}" for k, v in port.scripts.items()),
            ])
    return buf.getvalue()


def to_json(result: ScanResult) -> str:
    return json.dumps(asdict(result), indent=2)


def to_markdown(result: ScanResult) -> str:
    out = ["# nmap scan report", ""]
    out += [f"- **Command:** `{result.args}`",
            f"- **Started:** {result.startstr or '-'}",
            f"- **Finished:** {result.endstr or '-'}",
            f"- **Elapsed:** {result.elapsed or '-'} s",
            f"- **Hosts:** {result.hosts_up} up / {result.hosts_total} scanned",
            f"- **Open ports:** {result.open_port_count}", ""]
    for host in result.hosts:
        out.append(f"## {host.display}  — {host.state}")
        meta = []
        if host.mac:
            meta.append(f"MAC {host.mac}")
        if host.best_os:
            meta.append(f"OS {host.best_os} ({host.os_accuracy}%)")
        if host.distance:
            meta.append(f"{host.distance} hops away")
        if meta:
            out += ["", " · ".join(meta), ""]
        if host.ports:
            out += ["| Port | State | Service | Version |", "|---|---|---|---|"]
            for p in host.ports:
                out.append(f"| {p.label} | {p.state} | {p.service.name} | "
                           f"{p.service.banner or '-'} |")
            out.append("")
        for p in host.ports:
            for sid, output in p.scripts.items():
                out += [f"**{p.label} · {sid}**", "", "```", output, "```", ""]
        for sid, output in host.hostscripts.items():
            out += [f"**host · {sid}**", "", "```", output, "```", ""]
    return "\n".join(out)


_HTML_CSS = """
:root{--bg:#0f1319;--panel:#161c24;--line:#242d39;--fg:#e6edf3;--dim:#8b99a8;
--open:#36d399;--closed:#f87272;--filt:#fbbd23;--accent:#3ba3ff;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:14px/1.55 -apple-system,Segoe UI,Inter,Cantarell,sans-serif;padding:32px}
.wrap{max-width:1100px;margin:0 auto}
h1{font-size:24px;margin:0 0 4px} h2{font-size:17px;margin:32px 0 10px}
.sub{color:var(--dim);margin-bottom:24px;font-size:13px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:20px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.card b{display:block;font-size:22px;font-weight:600}
.card span{color:var(--dim);font-size:12px;text-transform:uppercase;letter-spacing:.06em}
table{width:100%;border-collapse:collapse;background:var(--panel);
border:1px solid var(--line);border-radius:10px;overflow:hidden;margin-bottom:10px}
th{text-align:left;font-size:11px;letter-spacing:.07em;text-transform:uppercase;
color:var(--dim);padding:9px 12px;border-bottom:1px solid var(--line)}
td{padding:8px 12px;border-bottom:1px solid rgba(255,255,255,.04);vertical-align:top}
tr:last-child td{border-bottom:none}
code,pre{font-family:JetBrains Mono,DejaVu Sans Mono,monospace;font-size:12.5px}
pre{background:#0b0f14;border:1px solid var(--line);border-radius:8px;padding:12px;
overflow-x:auto;color:#cbd5e1;white-space:pre-wrap}
.pill{padding:1px 8px;border-radius:999px;font-size:11.5px;font-weight:600}
.open{background:rgba(54,211,153,.14);color:var(--open)}
.closed{background:rgba(248,114,114,.14);color:var(--closed)}
.filtered{background:rgba(251,189,35,.14);color:var(--filt)}
.host{background:var(--panel);border:1px solid var(--line);border-radius:12px;
padding:18px 20px;margin-bottom:18px}
.meta{color:var(--dim);font-size:12.5px;margin:2px 0 14px}
.script{margin:10px 0} .script b{color:var(--accent);font-size:12.5px}
footer{color:var(--dim);font-size:12px;margin-top:40px;border-top:1px solid var(--line);
padding-top:14px}
"""


def to_html(result: ScanResult, title: str = "nmap scan report") -> str:
    esc = html.escape
    parts = [f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>{esc(title)}</title><style>{_HTML_CSS}</style></head><body><div class="wrap">
<h1>{esc(title)}</h1>
<div class="sub"><code>{esc(result.args)}</code></div>
<div class="cards">
  <div class="card"><span>Hosts up</span><b>{result.hosts_up}</b></div>
  <div class="card"><span>Hosts scanned</span><b>{result.hosts_total}</b></div>
  <div class="card"><span>Open ports</span><b>{result.open_port_count}</b></div>
  <div class="card"><span>Elapsed</span><b>{esc(result.elapsed or '-')}s</b></div>
</div>"""]

    for host in result.hosts:
        meta = []
        if host.mac:
            meta.append(f"MAC {esc(host.mac)}")
        if host.best_os:
            meta.append(f"OS guess: {esc(host.best_os)} ({host.os_accuracy}%)")
        if host.distance:
            meta.append(f"{esc(host.distance)} hops")
        if host.uptime:
            meta.append(f"uptime {esc(host.uptime)}s")
        parts.append(f'<div class="host"><h2>{esc(host.display)} '
                     f'<span class="pill {"open" if host.state == "up" else "closed"}">'
                     f'{esc(host.state)}</span></h2>')
        if meta:
            parts.append(f'<div class="meta">{" · ".join(meta)}</div>')
        if host.ports:
            parts.append("<table><tr><th>Port</th><th>State</th><th>Service</th>"
                         "<th>Version</th><th>Reason</th></tr>")
            for p in host.ports:
                cls = p.state if p.state in ("open", "closed") else "filtered"
                parts.append(
                    f"<tr><td><code>{p.label}</code></td>"
                    f'<td><span class="pill {cls}">{esc(p.state)}</span></td>'
                    f"<td>{esc(p.service.name)}</td><td>{esc(p.service.banner)}</td>"
                    f"<td>{esc(p.reason)}</td></tr>")
            parts.append("</table>")
        for ep_state, count, reasons in host.extraports:
            parts.append(f'<div class="meta">{esc(count)} more ports are '
                         f'<b>{esc(ep_state)}</b> — {esc(reasons)}</div>')
        for p in host.ports:
            for sid, output in p.scripts.items():
                parts.append(f'<div class="script"><b>{p.label} · {esc(sid)}</b>'
                             f"<pre>{esc(output)}</pre></div>")
        for sid, output in host.hostscripts.items():
            parts.append(f'<div class="script"><b>host · {esc(sid)}</b>'
                         f"<pre>{esc(output)}</pre></div>")
        if host.trace:
            parts.append("<table><tr><th>TTL</th><th>Address</th><th>Host</th><th>RTT</th></tr>")
            for hop in host.trace:
                parts.append(f"<tr><td>{esc(hop.ttl)}</td><td><code>{esc(hop.ipaddr)}</code></td>"
                             f"<td>{esc(hop.host)}</td><td>{esc(hop.rtt)}</td></tr>")
            parts.append("</table>")
        parts.append("</div>")

    parts.append(f"<footer>{esc(result.summary)}<br>Generated by Nmap Studio on "
                 f"{time.strftime('%Y-%m-%d %H:%M:%S')}</footer></div></body></html>")
    return "\n".join(parts)


# ------------------------------------------------------------------- diffing

def diff_results(old: ScanResult, new: ScanResult) -> dict:
    """Compare two scans: which hosts and ports appeared, vanished or changed."""
    old_hosts = {h.ip: h for h in old.hosts}
    new_hosts = {h.ip: h for h in new.hosts}

    report: dict = {
        "new_hosts": [ip for ip in new_hosts if ip not in old_hosts],
        "gone_hosts": [ip for ip in old_hosts if ip not in new_hosts],
        "changed": [],
    }
    for ip in sorted(set(old_hosts) & set(new_hosts)):
        oh, nh = old_hosts[ip], new_hosts[ip]
        op = {p.label: p for p in oh.ports}
        np_ = {p.label: p for p in nh.ports}
        entry = {
            "host": ip,
            "opened": [k for k in np_ if np_[k].state == "open"
                       and (k not in op or op[k].state != "open")],
            "closed": [k for k in op if op[k].state == "open"
                       and (k not in np_ or np_[k].state != "open")],
            "service_changes": [],
            "state_change": (oh.state, nh.state) if oh.state != nh.state else None,
        }
        for label in sorted(set(op) & set(np_)):
            a, b = op[label].service, np_[label].service
            if (a.name, a.banner) != (b.name, b.banner):
                entry["service_changes"].append(
                    (label, f"{a.name} {a.banner}".strip(), f"{b.name} {b.banner}".strip()))
        if entry["opened"] or entry["closed"] or entry["service_changes"] or entry["state_change"]:
            report["changed"].append(entry)
    return report


def diff_to_text(report: dict, old_label: str = "A", new_label: str = "B") -> str:
    lines = [f"Comparing  {old_label}  ->  {new_label}", "=" * 60, ""]
    if report["new_hosts"]:
        lines += ["NEW HOSTS"] + [f"  + {ip}" for ip in report["new_hosts"]] + [""]
    if report["gone_hosts"]:
        lines += ["HOSTS NO LONGER SEEN"] + [f"  - {ip}" for ip in report["gone_hosts"]] + [""]
    for entry in report["changed"]:
        lines.append(f"HOST {entry['host']}")
        if entry["state_change"]:
            lines.append(f"    state: {entry['state_change'][0]} -> {entry['state_change'][1]}")
        for port in entry["opened"]:
            lines.append(f"  + {port} is now open")
        for port in entry["closed"]:
            lines.append(f"  - {port} is no longer open")
        for port, before, after in entry["service_changes"]:
            lines.append(f"  ~ {port}: {before or '?'}  ->  {after or '?'}")
        lines.append("")
    if len(lines) == 3:
        lines.append("No differences found.")
    return "\n".join(lines)
