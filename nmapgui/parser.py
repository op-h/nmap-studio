"""Parse nmap XML into plain dataclasses.

Handles half-written files too: nmap flushes XML host by host, so the results
panes can fill in live while the scan is still running.
"""
from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


@dataclass
class Service:
    name: str = ""
    product: str = ""
    version: str = ""
    extrainfo: str = ""
    ostype: str = ""
    devicetype: str = ""
    tunnel: str = ""
    method: str = ""
    conf: str = ""
    cpes: list = field(default_factory=list)

    @property
    def banner(self) -> str:
        bits = [self.product, self.version]
        if self.extrainfo:
            bits.append(f"({self.extrainfo})")
        if self.tunnel:
            bits.append(f"[{self.tunnel}]")
        return " ".join(b for b in bits if b)


@dataclass
class Port:
    protocol: str = ""
    portid: int = 0
    state: str = ""
    reason: str = ""
    reason_ttl: str = ""
    service: Service = field(default_factory=Service)
    scripts: dict = field(default_factory=dict)   # script id -> output

    @property
    def label(self) -> str:
        return f"{self.portid}/{self.protocol}"


@dataclass
class Hop:
    ttl: str = ""
    ipaddr: str = ""
    host: str = ""
    rtt: str = ""


@dataclass
class OSMatch:
    name: str = ""
    accuracy: int = 0
    family: str = ""
    gen: str = ""
    osclass: str = ""
    cpes: list = field(default_factory=list)


@dataclass
class Host:
    state: str = ""
    reason: str = ""
    addresses: list = field(default_factory=list)      # (addr, addrtype, vendor)
    hostnames: list = field(default_factory=list)      # (name, type)
    ports: list = field(default_factory=list)
    extraports: list = field(default_factory=list)     # (state, count, reasons)
    osmatches: list = field(default_factory=list)
    uptime: str = ""
    lastboot: str = ""
    distance: str = ""
    tcpsequence: str = ""
    ipidsequence: str = ""
    trace: list = field(default_factory=list)
    hostscripts: dict = field(default_factory=dict)
    starttime: str = ""
    endtime: str = ""
    comment: str = ""          # user annotation, filled in by the UI

    # -------------------------------------------------- convenience
    @property
    def ip(self) -> str:
        for addr, kind, _ in self.addresses:
            if kind in ("ipv4", "ipv6"):
                return addr
        return self.addresses[0][0] if self.addresses else "?"

    @property
    def mac(self) -> str:
        for addr, kind, vendor in self.addresses:
            if kind == "mac":
                return f"{addr} ({vendor})" if vendor else addr
        return ""

    @property
    def vendor(self) -> str:
        for _, kind, vendor in self.addresses:
            if kind == "mac" and vendor:
                return vendor
        return ""

    @property
    def hostname(self) -> str:
        return self.hostnames[0][0] if self.hostnames else ""

    @property
    def display(self) -> str:
        return f"{self.ip} ({self.hostname})" if self.hostname else self.ip

    @property
    def best_os(self) -> str:
        return self.osmatches[0].name if self.osmatches else ""

    @property
    def os_accuracy(self) -> int:
        return self.osmatches[0].accuracy if self.osmatches else 0

    def ports_in(self, *states: str) -> list:
        return [p for p in self.ports if p.state in states]

    @property
    def open_ports(self) -> list:
        return [p for p in self.ports if p.state == "open"]


@dataclass
class ScanResult:
    args: str = ""
    version: str = ""
    start: str = ""
    startstr: str = ""
    endstr: str = ""
    elapsed: str = ""
    summary: str = ""
    exit_status: str = ""
    scaninfo: list = field(default_factory=list)      # dicts
    hosts: list = field(default_factory=list)
    hosts_up: int = 0
    hosts_down: int = 0
    hosts_total: int = 0
    verbose: str = ""
    debugging: str = ""
    taskprogress: list = field(default_factory=list)
    complete: bool = False

    @property
    def open_port_count(self) -> int:
        return sum(len(h.open_ports) for h in self.hosts)

    def host_by_ip(self, ip: str) -> Host | None:
        return next((h for h in self.hosts if h.ip == ip), None)


_CLOSE = re.compile(r"</host>", re.I)


def _repair(xml_text: str) -> str:
    """Make a partially written nmap XML document parseable."""
    if "</nmaprun>" in xml_text:
        return xml_text
    matches = list(_CLOSE.finditer(xml_text))
    if matches:
        cut = xml_text[: matches[-1].end()]
    else:
        # Nothing complete yet — keep just the header so we still get args/start.
        head = xml_text.find(">", xml_text.find("<nmaprun"))
        if head == -1:
            return ""
        cut = xml_text[: head + 1]
    return cut + "\n</nmaprun>"


def parse_xml_text(xml_text: str) -> ScanResult | None:
    if not xml_text or "<nmaprun" not in xml_text:
        return None
    text = xml_text if "</nmaprun>" in xml_text else _repair(xml_text)
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        try:
            root = ET.fromstring(_repair(xml_text[: xml_text.rfind("<")]))
        except Exception:
            return None
    return _from_root(root, complete="</nmaprun>" in xml_text)


def parse_xml_file(path: str) -> ScanResult | None:
    try:
        with open(path, "r", errors="replace") as fh:
            return parse_xml_text(fh.read())
    except OSError:
        return None


def _from_root(root: ET.Element, complete: bool) -> ScanResult:
    res = ScanResult(
        args=root.get("args", ""),
        version=root.get("version", ""),
        start=root.get("start", ""),
        startstr=root.get("startstr", ""),
        complete=complete,
    )
    for si in root.findall("scaninfo"):
        res.scaninfo.append(dict(si.attrib))
    verbose = root.find("verbose")
    if verbose is not None:
        res.verbose = verbose.get("level", "")
    debugging = root.find("debugging")
    if debugging is not None:
        res.debugging = debugging.get("level", "")
    for tp in root.findall("taskprogress"):
        res.taskprogress.append(dict(tp.attrib))

    for hel in root.findall("host"):
        res.hosts.append(_parse_host(hel))

    runstats = root.find("runstats")
    if runstats is not None:
        fin = runstats.find("finished")
        if fin is not None:
            res.elapsed = fin.get("elapsed", "")
            res.summary = fin.get("summary", "")
            res.endstr = fin.get("timestr", "")
            res.exit_status = fin.get("exit", "")
        hs = runstats.find("hosts")
        if hs is not None:
            res.hosts_up = int(hs.get("up", 0) or 0)
            res.hosts_down = int(hs.get("down", 0) or 0)
            res.hosts_total = int(hs.get("total", 0) or 0)
    if not res.hosts_total:
        res.hosts_up = sum(1 for h in res.hosts if h.state == "up")
        res.hosts_total = len(res.hosts)
    return res


def _parse_host(hel: ET.Element) -> Host:
    host = Host(starttime=hel.get("starttime", ""), endtime=hel.get("endtime", ""))
    st = hel.find("status")
    if st is not None:
        host.state = st.get("state", "")
        host.reason = st.get("reason", "")

    for a in hel.findall("address"):
        host.addresses.append((a.get("addr", ""), a.get("addrtype", ""), a.get("vendor", "")))
    hn = hel.find("hostnames")
    if hn is not None:
        for n in hn.findall("hostname"):
            host.hostnames.append((n.get("name", ""), n.get("type", "")))

    ports = hel.find("ports")
    if ports is not None:
        for ep in ports.findall("extraports"):
            reasons = ", ".join(
                f"{r.get('reason','')} ({r.get('count','')})" for r in ep.findall("extrareasons"))
            host.extraports.append((ep.get("state", ""), ep.get("count", ""), reasons))
        for pel in ports.findall("port"):
            host.ports.append(_parse_port(pel))
    host.ports.sort(key=lambda p: (p.protocol, p.portid))

    os_el = hel.find("os")
    if os_el is not None:
        for m in os_el.findall("osmatch"):
            match = OSMatch(name=m.get("name", ""), accuracy=int(m.get("accuracy", 0) or 0))
            cls = m.find("osclass")
            if cls is not None:
                match.family = cls.get("osfamily", "")
                match.gen = cls.get("osgen", "")
                match.osclass = " / ".join(
                    v for v in (cls.get("type", ""), cls.get("vendor", ""),
                                cls.get("osfamily", ""), cls.get("osgen", "")) if v)
                match.cpes = [c.text or "" for c in cls.findall("cpe")]
            host.osmatches.append(match)
        host.osmatches.sort(key=lambda m: -m.accuracy)

    up = hel.find("uptime")
    if up is not None:
        host.uptime = up.get("seconds", "")
        host.lastboot = up.get("lastboot", "")
    dist = hel.find("distance")
    if dist is not None:
        host.distance = dist.get("value", "")
    seq = hel.find("tcpsequence")
    if seq is not None:
        host.tcpsequence = f"{seq.get('difficulty','')} (index {seq.get('index','')})"
    ipid = hel.find("ipidsequence")
    if ipid is not None:
        host.ipidsequence = ipid.get("class", "")

    trace = hel.find("trace")
    if trace is not None:
        for h in trace.findall("hop"):
            host.trace.append(Hop(ttl=h.get("ttl", ""), ipaddr=h.get("ipaddr", ""),
                                  host=h.get("host", ""), rtt=h.get("rtt", "")))

    for s in hel.findall("hostscript/script"):
        host.hostscripts[s.get("id", "")] = (s.get("output", "") or "").strip()
    return host


def _parse_port(pel: ET.Element) -> Port:
    port = Port(protocol=pel.get("protocol", ""), portid=int(pel.get("portid", 0) or 0))
    st = pel.find("state")
    if st is not None:
        port.state = st.get("state", "")
        port.reason = st.get("reason", "")
        port.reason_ttl = st.get("reason_ttl", "")
    sv = pel.find("service")
    if sv is not None:
        port.service = Service(
            name=sv.get("name", ""), product=sv.get("product", ""),
            version=sv.get("version", ""), extrainfo=sv.get("extrainfo", ""),
            ostype=sv.get("ostype", ""), devicetype=sv.get("devicetype", ""),
            tunnel=sv.get("tunnel", ""), method=sv.get("method", ""),
            conf=sv.get("conf", ""),
            cpes=[c.text or "" for c in sv.findall("cpe")])
    for s in pel.findall("script"):
        port.scripts[s.get("id", "")] = (s.get("output", "") or "").strip()
    return port


# --------------------------------------------------------------------------
# live progress, scraped from nmap's --stats-every output
# --------------------------------------------------------------------------

_PROGRESS = re.compile(
    r"About\s+([\d.]+)%\s+done(?:;\s*ETC:\s*(\S+)\s*\(([^)]*)\s*remaining\))?", re.I)
_TASK = re.compile(r"^(.*?)\s+Timing:", re.M)
_STATS = re.compile(
    r"Stats:\s*(\S+)\s+elapsed;\s*(\d+)\s+hosts? completed\s*\((\d+)\s+up\)", re.I)


@dataclass
class Progress:
    percent: float = 0.0
    task: str = ""
    etc: str = ""
    remaining: str = ""
    elapsed: str = ""
    hosts_done: int = 0
    hosts_up: int = 0


def progress_from_xml(result: "ScanResult", current: Progress | None = None) -> Progress | None:
    """The newest <taskprogress> element as a Progress.

    nmap writes the same estimates it prints into the XML, so this is a second
    source of progress that does not depend on reading stdout — which matters
    wherever the process is not on a terminal.
    """
    if result is None or not result.taskprogress:
        return None
    last = result.taskprogress[-1]
    prog = Progress() if current is None else Progress(**vars(current))
    try:
        prog.percent = float(last.get("percent", 0) or 0)
    except ValueError:
        return None
    prog.task = last.get("task", "") or prog.task
    remaining = last.get("remaining")
    if remaining:
        prog.remaining = str(remaining)          # seconds; parse_duration copes
    etc = last.get("etc")
    if etc:
        try:
            prog.etc = time.strftime("%H:%M:%S", time.localtime(int(etc)))
        except (ValueError, OSError):
            pass
    return prog


def scrape_progress(chunk: str, current: Progress | None = None) -> Progress | None:
    """Pull a Progress out of a chunk of nmap stdout, or None if there is none."""
    prog = Progress() if current is None else Progress(**vars(current))
    hit = False
    m = _STATS.search(chunk)
    if m:
        prog.elapsed, prog.hosts_done, prog.hosts_up = m.group(1), int(m.group(2)), int(m.group(3))
        hit = True
    m = _PROGRESS.search(chunk)
    if m:
        prog.percent = float(m.group(1))
        prog.etc = m.group(2) or ""
        prog.remaining = (m.group(3) or "").strip()
        hit = True
    m = _TASK.search(chunk)
    if m:
        prog.task = m.group(1).strip().split("\n")[-1]
        hit = True
    return prog if hit else None
