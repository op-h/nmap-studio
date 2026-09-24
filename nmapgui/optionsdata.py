"""Catalogue of nmap options, scan profiles and NSE metadata.

Everything the option-builder UI shows is generated from OPTIONS below, so
adding support for a new nmap flag means adding one row here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# --------------------------------------------------------------------------
# option model
# --------------------------------------------------------------------------

FLAG = "flag"        # on/off  ->  emits the flag
TEXT = "text"        # free text value
INT = "int"          # numeric value
CHOICE = "choice"    # combobox of fixed values
FILE = "file"        # path, with a browse button
EXCLUSIVE = "excl"   # radio button inside a named exclusive set


@dataclass
class Opt:
    key: str
    flag: str
    label: str
    kind: str
    section: str
    help: str = ""
    default: Any = None
    choices: tuple = ()
    placeholder: str = ""
    joiner: str = " "        # how the value is attached: " ", "=" or ""
    root: bool = False       # requires raw sockets / root
    exclusive: str = ""      # name of the radio set, for kind == EXCLUSIVE
    lo: int = 0
    hi: int = 1_000_000


SECTIONS = [
    ("discovery", "Host Discovery", "Decide which hosts are worth scanning."),
    ("technique", "Scan Techniques", "How probes are crafted and sent."),
    ("ports", "Ports", "Which ports to look at, and in what order."),
    ("service", "Service & OS", "Version fingerprinting and OS detection."),
    ("timing", "Timing & Performance", "Speed versus stealth versus accuracy."),
    ("evasion", "Firewall / IDS Evasion", "Fragmentation, decoys and spoofing."),
    ("output", "Output & Verbosity", "How much nmap tells you, and where it lands."),
    ("misc", "Misc", "Everything else."),
]


OPTIONS: list[Opt] = [
    # ---------------- host discovery ----------------
    Opt("sL", "-sL", "List scan (only enumerate targets)", EXCLUSIVE, "discovery",
        "Simply list the targets that would be scanned. Sends no packets to the hosts "
        "beyond reverse-DNS.", exclusive="hostdisc"),
    Opt("sn", "-sn", "Ping scan — host discovery only, no port scan", EXCLUSIVE, "discovery",
        "Find which hosts are up and stop there. The classic 'what is alive on this /24'.",
        exclusive="hostdisc"),
    Opt("Pn", "-Pn", "Treat all hosts as online (skip discovery)", EXCLUSIVE, "discovery",
        "Scan every target even if it never answers a ping. Essential against hosts that "
        "drop ICMP.", exclusive="hostdisc"),
    Opt("PS", "-PS", "TCP SYN ping ports", TEXT, "discovery",
        "SYN-ping the given ports, e.g. 22,80,443. Empty value still probes port 80.",
        placeholder="21,22,80,443,3389", joiner=""),
    Opt("PA", "-PA", "TCP ACK ping ports", TEXT, "discovery",
        "ACK-ping the given ports. Gets through stateless filters that block SYN.",
        placeholder="80,443", joiner=""),
    Opt("PU", "-PU", "UDP ping ports", TEXT, "discovery",
        "UDP-ping the given ports; an ICMP port-unreachable proves the host is up.",
        placeholder="40125", joiner=""),
    Opt("PY", "-PY", "SCTP INIT ping ports", TEXT, "discovery",
        "SCTP INIT chunk ping.", placeholder="80", joiner=""),
    Opt("PE", "-PE", "ICMP echo ping", FLAG, "discovery", "Classic ICMP echo request."),
    Opt("PP", "-PP", "ICMP timestamp ping", FLAG, "discovery",
        "ICMP timestamp request — often allowed where echo is blocked."),
    Opt("PM", "-PM", "ICMP netmask ping", FLAG, "discovery", "ICMP address-mask request."),
    Opt("PO", "-PO", "IP protocol ping", TEXT, "discovery",
        "Send raw IP packets with the given protocol numbers.", placeholder="1,2,4", joiner=""),
    Opt("PR", "-PR", "ARP ping (local network)", FLAG, "discovery",
        "Fastest and most reliable discovery on a LAN. Used automatically for local targets.",
        root=True),
    Opt("disable_arp", "--disable-arp-ping", "Disable ARP/ND ping", FLAG, "discovery",
        "Force IP-level discovery even on the local segment."),
    Opt("n", "-n", "Never do DNS resolution", EXCLUSIVE, "discovery",
        "Big speed win on large ranges.", exclusive="dns"),
    Opt("R", "-R", "Always do DNS resolution", EXCLUSIVE, "discovery",
        "Resolve even hosts that are down.", exclusive="dns"),
    Opt("dns_servers", "--dns-servers", "Custom DNS servers", TEXT, "discovery",
        "Comma-separated resolvers to use instead of the system ones.",
        placeholder="1.1.1.1,8.8.8.8"),
    Opt("system_dns", "--system-dns", "Use the system DNS resolver", FLAG, "discovery",
        "Slower, but respects /etc/hosts and nsswitch."),
    Opt("traceroute", "--traceroute", "Trace path to each host", FLAG, "discovery",
        "Adds a hop-by-hop trace, which feeds the Topology view.", root=True),

    # ---------------- scan techniques ----------------
    Opt("sS", "-sS", "TCP SYN (stealth) — the default when root", EXCLUSIVE, "technique",
        "Half-open scan. Fast, accurate and relatively quiet. Needs raw sockets.",
        exclusive="scantype", root=True),
    Opt("sT", "-sT", "TCP connect()", EXCLUSIVE, "technique",
        "Completes the handshake through the OS. No privileges needed, but noisy and slower.",
        exclusive="scantype"),
    Opt("sU", "-sU", "UDP scan", EXCLUSIVE, "technique",
        "Slow but the only way to find DNS/SNMP/TFTP and friends. Pair with --top-ports.",
        exclusive="scantype", root=True),
    Opt("sA", "-sA", "TCP ACK — map firewall rules", EXCLUSIVE, "technique",
        "Does not find open ports; it tells you which ports are filtered.",
        exclusive="scantype", root=True),
    Opt("sW", "-sW", "TCP Window", EXCLUSIVE, "technique",
        "ACK scan variant that can distinguish open from closed on some stacks.",
        exclusive="scantype", root=True),
    Opt("sM", "-sM", "TCP Maimon", EXCLUSIVE, "technique",
        "FIN/ACK probe; works against some BSD-derived stacks.",
        exclusive="scantype", root=True),
    Opt("sN", "-sN", "TCP Null", EXCLUSIVE, "technique",
        "No flags set. Sneaks past some non-stateful filters.", exclusive="scantype", root=True),
    Opt("sF", "-sF", "TCP FIN", EXCLUSIVE, "technique",
        "Bare FIN probe.", exclusive="scantype", root=True),
    Opt("sX", "-sX", "TCP Xmas", EXCLUSIVE, "technique",
        "FIN, PSH and URG all lit up 'like a Christmas tree'.", exclusive="scantype", root=True),
    Opt("sY", "-sY", "SCTP INIT", EXCLUSIVE, "technique",
        "SCTP equivalent of a SYN scan.", exclusive="scantype", root=True),
    Opt("sZ", "-sZ", "SCTP COOKIE-ECHO", EXCLUSIVE, "technique",
        "Stealthier SCTP scan.", exclusive="scantype", root=True),
    Opt("sO", "-sO", "IP protocol scan", EXCLUSIVE, "technique",
        "Finds which IP protocols (TCP, ICMP, IGMP…) the host speaks.",
        exclusive="scantype", root=True),
    Opt("sI", "-sI", "Idle / zombie scan", TEXT, "technique",
        "Bounce the scan off a zombie host: zombie[:probeport]. Truly blind scanning.",
        placeholder="zombie.host:80", root=True),
    Opt("b", "-b", "FTP bounce scan", TEXT, "technique",
        "Relay the scan through an FTP server: user:pass@server:port.",
        placeholder="user:pass@ftp.host:21"),
    Opt("scanflags", "--scanflags", "Custom TCP flags", TEXT, "technique",
        "Hand-built flag combination, e.g. URGACKPSHRSTSYNFIN or a number.",
        placeholder="SYNFIN", root=True),

    # ---------------- ports ----------------
    Opt("p", "-p", "Port ranges", TEXT, "ports",
        "e.g. 22,80,443  |  1-65535  |  U:53,T:21-25  |  http*  for named services.",
        placeholder="1-1000"),
    Opt("exclude_ports", "--exclude-ports", "Exclude ports", TEXT, "ports",
        "Ports to leave alone no matter what else is selected.", placeholder="9100"),
    Opt("F", "-F", "Fast scan (top 100 ports)", FLAG, "ports",
        "Shorthand for the 100 most common ports."),
    Opt("top_ports", "--top-ports", "Scan N most common ports", INT, "ports",
        "Ranked by nmap-services frequency data.", placeholder="1000", lo=1, hi=65535),
    Opt("port_ratio", "--port-ratio", "Ports more common than ratio", TEXT, "ports",
        "A float between 0 and 1, e.g. 0.05.", placeholder="0.05"),
    Opt("r", "-r", "Scan ports consecutively (no randomise)", FLAG, "ports",
        "Predictable order — easier to read, easier to spot."),

    # ---------------- service / OS ----------------
    Opt("sV", "-sV", "Service / version detection", FLAG, "service",
        "Probe open ports and fingerprint what is actually listening."),
    Opt("version_intensity", "--version-intensity", "Version intensity (0-9)", INT, "service",
        "Higher tries more probes. 7 is the default, 9 tries everything.",
        placeholder="7", lo=0, hi=9),
    Opt("version_light", "--version-light", "Light version probes (intensity 2)", FLAG, "service",
        "Much faster, catches the obvious services."),
    Opt("version_all", "--version-all", "Try every version probe (intensity 9)", FLAG, "service"),
    Opt("version_trace", "--version-trace", "Trace version scan activity", FLAG, "service"),
    Opt("O", "-O", "OS detection", FLAG, "service",
        "TCP/IP stack fingerprinting. Needs raw sockets.", root=True),
    Opt("osscan_limit", "--osscan-limit", "Only fingerprint promising hosts", FLAG, "service",
        "Skip OS detection unless the host has one open and one closed TCP port."),
    Opt("osscan_guess", "--osscan-guess", "Guess OS more aggressively", FLAG, "service"),
    Opt("A", "-A", "Aggressive: -O -sV -sC --traceroute", FLAG, "service",
        "Everything at once. Loud, slow, and extremely informative.", root=True),

    # ---------------- timing ----------------
    Opt("T", "-T", "Timing template", CHOICE, "timing",
        "T0 paranoid · T1 sneaky · T2 polite · T3 normal · T4 aggressive · T5 insane.",
        choices=("", "0", "1", "2", "3", "4", "5"), joiner=""),
    Opt("min_hostgroup", "--min-hostgroup", "Min hosts per group", INT, "timing",
        "Scan at least this many hosts in parallel."),
    Opt("max_hostgroup", "--max-hostgroup", "Max hosts per group", INT, "timing"),
    Opt("min_parallelism", "--min-parallelism", "Min probe parallelism", INT, "timing"),
    Opt("max_parallelism", "--max-parallelism", "Max probe parallelism", INT, "timing"),
    Opt("min_rtt", "--min-rtt-timeout", "Min RTT timeout", TEXT, "timing",
        "Accepts ms by default; suffix with s/m/h.", placeholder="100ms"),
    Opt("max_rtt", "--max-rtt-timeout", "Max RTT timeout", TEXT, "timing", placeholder="1250ms"),
    Opt("initial_rtt", "--initial-rtt-timeout", "Initial RTT timeout", TEXT, "timing",
        placeholder="500ms"),
    Opt("max_retries", "--max-retries", "Max port-scan retries", INT, "timing",
        "Lowering this is the single biggest speed win on flaky networks.", hi=100),
    Opt("host_timeout", "--host-timeout", "Give up on a host after", TEXT, "timing",
        placeholder="30m"),
    Opt("scan_delay", "--scan-delay", "Delay between probes", TEXT, "timing",
        "Defeats rate-based IDS thresholds.", placeholder="500ms"),
    Opt("max_scan_delay", "--max-scan-delay", "Max scan delay", TEXT, "timing", placeholder="1s"),
    Opt("min_rate", "--min-rate", "Min packets / second", INT, "timing", placeholder="300"),
    Opt("max_rate", "--max-rate", "Max packets / second", INT, "timing", placeholder="1000"),
    Opt("defeat_rst", "--defeat-rst-ratelimit", "Defeat RST rate limiting", FLAG, "timing"),
    Opt("defeat_icmp", "--defeat-icmp-ratelimit", "Defeat ICMP rate limiting", FLAG, "timing"),

    # ---------------- evasion ----------------
    Opt("f", "-f", "Fragment packets", FLAG, "evasion",
        "Split probes into tiny IP fragments.", root=True),
    Opt("ff", "-ff", "Fragment harder (8-byte fragments)", FLAG, "evasion", root=True),
    Opt("mtu", "--mtu", "Custom fragment MTU (multiple of 8)", INT, "evasion", root=True, hi=9000),
    Opt("D", "-D", "Decoy addresses", TEXT, "evasion",
        "Comma list; RND:5 generates random decoys; ME marks your real position.",
        placeholder="RND:5,ME", root=True),
    Opt("S", "-S", "Spoof source address", TEXT, "evasion",
        "You will not see replies unless you are on the path.", placeholder="10.0.0.5", root=True),
    Opt("e", "-e", "Network interface", TEXT, "evasion",
        "Force a specific interface, e.g. eth0 / tun0.", placeholder="eth0"),
    Opt("g", "--source-port", "Source port", INT, "evasion",
        "Old firewalls trust traffic from 53 or 20.", hi=65535),
    Opt("proxies", "--proxies", "Proxy chain", TEXT, "evasion",
        "Comma-separated HTTP/SOCKS4 proxy URLs.", placeholder="socks4://127.0.0.1:9050"),
    Opt("data", "--data", "Append hex payload", TEXT, "evasion", placeholder="0xdeadbeef"),
    Opt("data_string", "--data-string", "Append ASCII payload", TEXT, "evasion",
        placeholder="authorised scan"),
    Opt("data_length", "--data-length", "Append N random bytes", INT, "evasion", hi=1400),
    Opt("ip_options", "--ip-options", "IP options", TEXT, "evasion",
        "e.g. 'L 10.0.0.1 10.0.0.2' for loose source routing.", root=True),
    Opt("ttl", "--ttl", "Set IP TTL", INT, "evasion", root=True, hi=255),
    Opt("spoof_mac", "--spoof-mac", "Spoof MAC address", TEXT, "evasion",
        "A MAC, a vendor prefix, a vendor name, or 0 for fully random.",
        placeholder="Apple", root=True),
    Opt("badsum", "--badsum", "Send bad checksums", FLAG, "evasion",
        "Only broken stacks and IDS boxes answer these.", root=True),

    # ---------------- output ----------------
    Opt("v", "-v", "Verbosity", CHOICE, "output",
        "How chatty nmap is while it works.",
        choices=("", "-v", "-vv", "-vvv"), joiner="RAW"),
    Opt("d", "-d", "Debug level", CHOICE, "output",
        "Packet-level detail for troubleshooting.",
        choices=("", "-d", "-dd", "-ddd"), joiner="RAW"),
    Opt("reason", "--reason", "Show why a port is in its state", FLAG, "output",
        "Adds 'syn-ack', 'host-unreach' etc. to every result."),
    Opt("open", "--open", "Only show open (or possibly open) ports", FLAG, "output"),
    Opt("packet_trace", "--packet-trace", "Trace every packet sent and received", FLAG, "output"),
    Opt("oN", "-oN", "Also write normal output to", FILE, "output"),
    Opt("oG", "-oG", "Also write grepable output to", FILE, "output"),
    Opt("oS", "-oS", "Also write sCRiPt KiDDi3 output to", FILE, "output"),
    Opt("append_output", "--append-output", "Append to output files", FLAG, "output"),
    Opt("resume", "--resume", "Resume an aborted scan from", FILE, "output",
        "Point at a previous normal or grepable output file."),

    # ---------------- misc ----------------
    Opt("ipv6", "-6", "IPv6 scan", FLAG, "misc", "Targets must be IPv6 addresses or names."),
    Opt("iL", "-iL", "Read targets from file", FILE, "misc",
        "One host, range or CIDR per line."),
    Opt("iR", "-iR", "Choose N random internet targets", INT, "misc",
        "Deliberately left off the profiles — only use it where you are authorised."),
    Opt("exclude", "--exclude", "Exclude hosts", TEXT, "misc",
        "Comma-separated hosts or ranges to skip.", placeholder="10.0.0.1,10.0.0.254"),
    Opt("excludefile", "--excludefile", "Exclude hosts listed in file", FILE, "misc"),
    Opt("send_eth", "--send-eth", "Send at the ethernet layer", FLAG, "misc", root=True),
    Opt("send_ip", "--send-ip", "Send at the raw IP layer", FLAG, "misc", root=True),
    Opt("privileged", "--privileged", "Assume full privileges", FLAG, "misc"),
    Opt("unprivileged", "--unprivileged", "Assume no raw-socket privileges", FLAG, "misc"),
    Opt("datadir", "--datadir", "Custom nmap data directory", FILE, "misc"),
    Opt("release_memory", "--release-memory", "Release memory before quitting", FLAG, "misc"),
]

OPT_BY_KEY = {o.key: o for o in OPTIONS}

# Order flags are emitted in, so generated commands read the way a human writes them.
EMIT_ORDER = [o.key for o in OPTIONS]


# --------------------------------------------------------------------------
# profiles
# --------------------------------------------------------------------------

@dataclass
class Profile:
    name: str
    description: str
    opts: dict = field(default_factory=dict)
    scripts: tuple = ()
    script_args: str = ""


BUILTIN_PROFILES: list[Profile] = [
    Profile("Quick scan", "Top 100 ports, aggressive timing. The 'what is this box' opener.",
            {"sS": True, "F": True, "T": "4"}),
    Profile("Quick scan plus", "Fast port sweep with version and OS detection.",
            {"sS": True, "F": True, "T": "4", "sV": True, "version_light": True, "O": True}),
    Profile("Intense scan", "The Zenmap default: -T4 -A -v.",
            {"sS": True, "T": "4", "A": True, "v": "-v"}),
    Profile("Intense scan plus UDP", "TCP and UDP together. Slow — start it and go for coffee.",
            {"sS": True, "sU": True, "T": "4", "A": True, "v": "-v"}),
    Profile("Intense scan, all TCP ports", "All 65535 ports with version and OS detection.",
            {"sS": True, "p": "1-65535", "T": "4", "A": True, "v": "-v"}),
    Profile("Intense scan, no ping", "For hosts that drop ICMP and refuse discovery.",
            {"sS": True, "Pn": True, "T": "4", "A": True, "v": "-v"}),
    Profile("Ping sweep", "Who is alive on this subnet? No ports touched.",
            {"sn": True}),
    Profile("List scan", "Resolve and list targets without sending them a single packet.",
            {"sL": True}),
    Profile("Slow comprehensive", "Every discovery method, all ports, full scripts. Very loud.",
            {"sS": True, "sU": True, "T": "4", "A": True, "v": "-v",
             "PE": True, "PP": True, "PS": "80,443", "PA": "3389", "PU": "40125",
             "osscan_guess": True},
            scripts=("default", "discovery", "safe")),
    Profile("Stealth / low and slow", "Fragmented SYN scan at T1 with decoys.",
            {"sS": True, "T": "1", "f": True, "D": "RND:5", "Pn": True}),
    Profile("Web server audit", "HTTP-focused ports plus the http-* NSE family.",
            {"sS": True, "sV": True, "T": "4",
             "p": "80,81,443,591,2082,2087,2095,2096,3000,8000,8008,8080,8443,8888,9090"},
            scripts=("http-title", "http-headers", "http-methods", "http-enum",
                     "http-robots.txt", "http-server-header")),
    Profile("SMB / Windows enumeration", "445/139 plus safe SMB discovery scripts.",
            {"sS": True, "sV": True, "T": "4", "p": "139,445,3389,5985"},
            scripts=("smb-os-discovery", "smb-security-mode", "smb2-security-mode",
                     "smb-enum-shares", "smb-protocols")),
    Profile("Vulnerability sweep", "Version detection plus the vuln NSE category.",
            {"sS": True, "sV": True, "T": "4"}, scripts=("vuln",)),
    Profile("UDP top 200", "The UDP services that actually show up in practice.",
            {"sU": True, "top_ports": "200", "T": "4", "sV": True, "version_intensity": "0"}),
    Profile("Firewall rule mapping", "ACK scan to separate filtered from unfiltered.",
            {"sA": True, "T": "4", "p": "1-1000"}),
    Profile("CTF opener", "All TCP ports fast, then version-detect whatever answered.",
            {"sS": True, "p": "-", "T": "4", "min_rate": "1000", "Pn": True, "sV": True,
             "reason": True, "open": True},
            scripts=("default",)),
]


NSE_CATEGORIES = [
    ("auth", "Authentication bypass and credential handling"),
    ("broadcast", "Discovers hosts by broadcasting on the local network"),
    ("brute", "Credential brute-force — loud and slow"),
    ("default", "Run by -sC / -A. Fast, useful and generally safe"),
    ("discovery", "Actively pulls more information out of a service"),
    ("dos", "May crash the target. Never run without permission"),
    ("exploit", "Actively exploits a vulnerability"),
    ("external", "Sends data to a third-party service"),
    ("fuzzer", "Throws malformed input at a service"),
    ("intrusive", "Likely to be noticed, may disrupt the target"),
    ("malware", "Checks for backdoors and malware"),
    ("safe", "Not designed to crash, flood or exploit anything"),
    ("version", "Extends -sV fingerprinting"),
    ("vuln", "Checks for a specific known vulnerability"),
]

CATEGORY_RISK = {
    "safe": "low", "default": "low", "discovery": "low", "version": "low",
    "auth": "medium", "broadcast": "medium", "external": "medium", "malware": "medium",
    "vuln": "medium", "intrusive": "medium",
    "brute": "high", "dos": "high", "exploit": "high", "fuzzer": "high",
}
