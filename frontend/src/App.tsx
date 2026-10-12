import { useEffect, useMemo, useRef, useState, type ChangeEvent, type ReactNode } from "react";
import CampusMap, { campusViews, type CampusName } from "./CampusMap";
import { campusPlaces, type MapListing, type PlaceType } from "./mapData";
import { NEAR_RADIUS_METERS, OFF_CAMPUS_METERS, nearestCampusTo, reportsNear, walkMinutes } from "./nearby";
import { useUserLocation } from "./useUserLocation";
import { BrandIcon, Button, Icon, Wordmark, type IconName } from "./ui";
import LocationPicker, { DemoTag, LocationSummary, PhotoButtons } from "./LocationPicker";
import { activeRecognizer, nameOnCard, campuses as campusOptions, campusCenters, formatLocation, sourceLabel, type CampusId, type RoomLocation } from "./roomRecognition";
import * as api from "./api";
import { embedded } from "./embed";
import { categoryIcon, ReportImage, reportCategories, reportStatusLabel, storeReportImage, toPublicReport, useReports, type Claim, type ItemReport, type PublicItemReport, type ReportCategory, type ReportLocation } from "./reports";

type Screen =
  | "signin"
  | "code"
  | "name"
  | "home"
  | "explore"
  | "detail"
  | "capture"
  | "locate"
  | "confirm"
  | "finderStatus"
  | "ownerNotice"
  | "ownership"
  | "handoff"
  | "lost"
  | "items"
  | "map"
  | "profile";

type SensitiveItem = {
  id: string;
  name: string;
  description: string;
  serial: string;
  photoAdded: boolean;
};

type ThemePreference = "system" | "light" | "dark";

type TimelinePlace = {
  id: number;
  time: string;
  sortMinutes: number;
  name: string;
  source: string;
  high: boolean;
};

function Brand({ size = "header", subtitle = false }: { size?: "header" | "welcome"; subtitle?: boolean }) {
  const isWelcome = size === "welcome";
  return <div className={`brand ${isWelcome ? "welcome-brand" : ""}`}>
    {!isWelcome && <BrandIcon className="brand-logo" />}
    <span className={isWelcome ? "welcome-brand-copy" : "brand-copy"}>
      <Wordmark size={size} />
      {subtitle && <small>Student-to-student lost &amp; found</small>}
    </span>
  </div>;
}

function BackHeader({ title, onBack, action }: { title: string; onBack: () => void; action?: ReactNode }) {
  return <header className="page-header"><button type="button" className="icon-button" onClick={onBack} aria-label="Go back"><Icon name="arrow" /></button>{title ? <h1>{title}</h1> : <span aria-hidden="true" />}<div className="header-action">{action}</div></header>;
}

const statusTone: Record<string, string> = {
  "Active": "blue",
  "Possible match": "amber",
  "Claim under review": "amber",
  "Pinging": "blue",
  "Claim pending": "amber",
  "Verified": "green",
  "Approved": "green",
  "Returned": "neutral",
  "Sent to official lost & found": "purple",
};

function Status({ children }: { children: string }) {
  const tone = children.startsWith("Trusted helpers only") ? "purple" : statusTone[children] || "neutral";
  return <span className={`status status-${tone}`}><span />{children}</span>;
}

function Toggle({ on, setOn, label, icon }: { on: boolean; setOn: (value: boolean) => void; label: string; icon?: ReactNode }) {
  return <button type="button" className="toggle-row" aria-pressed={on} onClick={() => setOn(!on)}>{icon}<span className="toggle-label">{label}</span><span className={`toggle ${on ? "on" : ""}`} aria-hidden="true"><span /></span></button>;
}

function SignIn({ go, email, setEmail, onDevSkip }: { go: (screen: Screen) => void; email: string; setEmail: (email: string) => void; onDevSkip?: () => void }) {
  const [error, setError] = useState("");
  // Developer shortcut: tap the logo 3 times within 1.5 s to skip sign-in. Dev builds only.
  const [taps, setTaps] = useState<number[]>([]);
  const tapLogo = () => {
    if (!(import.meta.env.DEV || import.meta.env.VITE_DEMO === "true") || !onDevSkip) return;
    const now = Date.now();
    const recent = [...taps.filter((time) => now - time < 1500), now];
    setTaps(recent);
    if (recent.length >= 3) {
      setTaps([]);
      onDevSkip();
    }
  };
  const submit = () => {
    const isEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    if (!isEmail) {
      setError("Enter a valid email address.");
      return;
    }
    go("code");
  };
  return <main className="welcome-screen">
    <div className="welcome-content">
      <div onClick={tapLogo} style={{ display: "contents" }}><Brand size="welcome" subtitle /></div>
      <div className="welcome-copy">
        <h1>Help it find its way home.</h1>
      </div>
      <WelcomeMap />
      <div className="welcome-form">
        <label className="welcome-field"><span>Email address</span><input value={email} onChange={(e) => { setEmail(e.target.value); setError(""); }} onKeyDown={(e) => { if (e.key === "Enter") submit(); }} placeholder="netid@scarletmail.rutgers.edu" type="email" inputMode="email" autoComplete="email" aria-invalid={Boolean(error)} aria-describedby={error ? "credential-error" : undefined} /></label>
        {error && <p className="welcome-error" id="credential-error" role="alert">{error}</p>}
        <button type="button" className="welcome-button" onClick={submit}>Continue <Icon name="chevron" size={18} /></button>
        <p className="welcome-note"><Icon name="shield" size={15} /> We never ask for your NetID password.</p>
      </div>
    </div>
  </main>;
}

function WelcomeMap() {
  return <svg className="welcome-map" viewBox="0 0 400 430" preserveAspectRatio="xMidYMax meet" aria-hidden="true" focusable="false">
    <g className="wi-items">
      <g transform="translate(58 128) rotate(-14)"><rect x="0" y="14" width="34" height="78" rx="12" /><rect x="7" y="0" width="20" height="16" rx="5" /><circle cx="17" cy="52" r="6" /></g>
      <g transform="translate(300 96) rotate(10)"><rect x="0" y="0" width="70" height="46" rx="8" /><circle cx="20" cy="21" r="9" /><path d="M38 15h22M38 26h16M10 37h50" /></g>
      <g transform="translate(296 262) rotate(-8)"><circle cx="18" cy="18" r="16" /><path d="M30 30l26 26M44 44l7-7M51 51l7-7" /><circle cx="18" cy="18" r="5" /></g>
      <g transform="translate(36 300) rotate(8)"><rect x="0" y="0" width="56" height="72" rx="6" /><path d="M12 0v72M22 18h24M22 30h18" /></g>
      <g transform="translate(330 370) rotate(-18)"><rect x="0" y="0" width="40" height="30" rx="12" /><path d="M0 12h40" /></g>
    </g>
    <path className="wi-trail" d="M78 176 C 120 300, 40 330, 70 350 S 200 400, 250 330 S 330 190, 335 118" />
    <circle className="wi-trail-start" cx="78" cy="176" r="5" />
    <g className="wi-glass">
      <circle className="wi-pulse" cx="190" cy="232" r="70" />
      <circle className="wi-glow" cx="190" cy="232" r="96" />
      <circle className="wi-lens" cx="190" cy="232" r="70" />
      <g className="wi-found" transform="translate(162 196)">
        <rect x="0" y="16" width="56" height="44" rx="16" /><path d="M0 34h56" /><circle cx="28" cy="34" r="3.5" />
      </g>
      <path className="wi-handle" d="M241 283 L 300 342" />
      <path className="wi-shine" d="M146 200 a 52 52 0 0 1 30 -26" />
      <g className="wi-spark" transform="translate(262 168)"><path d="M0 -10v20M-10 0h20" /></g>
      <g className="wi-spark small" transform="translate(118 300)"><path d="M0 -6v12M-6 0h12" /></g>
    </g>
  </svg>;
}

function CodeScreen({ go, email, onVerified }: { go: (screen: Screen) => void; email: string; onVerified: () => void }) {
  const [code, setCode] = useState("");
  const [resent, setResent] = useState(false);
  const validDemoCode = code === "123456";
  return <main className="simple-page auth-code">
    <BackHeader title="" onBack={() => go("signin")} />
    <div className="code-icon"><Icon name="bell" size={30} /></div>
    <p className="eyebrow">Demo access code</p>
    <h1>Enter your 6-digit code</h1>
    <p className="subtext">Demo only: no email was sent to {email}. Enter 123456 to continue; this does not verify your identity or university affiliation.</p>
    <input className="code-input" inputMode="numeric" autoComplete="one-time-code" aria-label="Six digit verification code" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} placeholder="000000" autoFocus />
    {!validDemoCode && <p className="form-hint">{code.length === 6 ? "That is not the demo code." : "Enter the demo code 123456 to continue."}</p>}
    <Button disabled={!validDemoCode} onClick={onVerified}>Continue in demo</Button>
    <button className="text-link" aria-live="polite" onClick={() => setResent(true)}>{resent ? "Demo code: 123456" : "Show demo code again"}</button>
  </main>;
}

function NameScreen({ go, firstName, setFirstName, lastName, setLastName, onContinue }: {
  go: (screen: Screen) => void;
  firstName: string;
  setFirstName: (name: string) => void;
  lastName: string;
  setLastName: (name: string) => void;
  onContinue: () => void;
}) {
  const hasFirstLetter = /\p{L}/u.test(firstName);
  const hasLastName = Boolean(lastName.trim());
  return <main className="simple-page with-bottom name-page">
    <BackHeader title="Your name" onBack={() => go("code")} />
    <div className="verify-heading"><span><Icon name="user" size={27} /></span><p className="eyebrow">ONE LAST STEP</p><h1>What should we call you?</h1><p>Choose the display name used in this local demo.</p></div>
    <div className="flow-form">
      <label className="result-field"><span>First name</span><input autoComplete="given-name" value={firstName} onChange={(event) => setFirstName(event.target.value)} /></label>
      <label className="result-field"><span>Last name</span><input autoComplete="family-name" value={lastName} onChange={(event) => setLastName(event.target.value)} /></label>
    </div>
    <div className="safe-card"><Icon name="shield" /><p><strong>This does not verify your identity.</strong><br />The name remains in the current app session.</p></div>
    <div className="bottom-action">{(!hasFirstLetter || !hasLastName) && <p className="action-hint">{hasFirstLetter ? "Enter your last name" : "Enter your first name"}</p>}<Button disabled={!hasFirstLetter || !hasLastName} onClick={onContinue}>Continue <Icon name="chevron" size={18} /></Button></div>
  </main>;
}

/** Safe public line when details are hidden: "Navy blue Hydro Flask water bottle reported found." */
function plainSummary(color: string, itemName: string, verb: "found" | "lost") {
  const name = itemName.trim(), shade = color.trim();
  const colorInName = shade.toLowerCase().split(/\s+/).some((word) => word && name.toLowerCase().includes(word));
  const text = `${shade && !colorInName ? `${shade.toLowerCase()} ` : ""}${name || "Item"} reported ${verb}.`;
  return text[0].toUpperCase() + text.slice(1);
}

function relativeTime(value: string) {
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 60_000));
  if (minutes < 2) return "Just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function ReportCard({ report, onClick, large = false }: { report: PublicItemReport | ItemReport; onClick?: () => void; large?: boolean }) {
  const restricted = "restrictedProjection" in report && report.restrictedProjection;
  const content = restricted
    ? <><span className="item-thumb">{categoryIcon(report.category)}</span><span className="item-info"><strong>{report.category}</strong><small>{report.location?.campus || "Campus hidden"} · Details hidden for safety</small></span>{onClick && <Icon name="chevron" size={19} />}</>
    : <><span className="item-thumb"><ReportImage src={report.photoUrl} alt="" fallback={categoryIcon(report.category)} /></span><span className="item-info"><span><span className={`report-type-badge ${report.type}`}>{report.type}</span>{report.sample && <span className="sample-report-label">Demo sample</span>}</span><strong>{report.itemName}</strong><small>{report.location?.approximateLabel || "Location unavailable"} · {relativeTime(report.observedAt)}</small><Status>{reportStatusLabel(report.status)}</Status></span>{onClick && <Icon name="chevron" size={19} />}</>;
  return onClick
    ? <button className={`item-card report-card ${large ? "large" : ""}`} onClick={onClick}>{content}</button>
    : <article className={`item-card report-card ${large ? "large" : ""}`}>{content}</article>;
}

function greetingForHour(hour: number) {
  if (hour >= 5 && hour < 12) return "Good morning";
  if (hour >= 12 && hour < 17) return "Good afternoon";
  if (hour >= 17 && hour < 22) return "Good evening";
  return "Up late";
}

function firstLetter(value: string) {
  return Array.from(value).find((character) => /\p{L}/u.test(character))?.toUpperCase() || "";
}

function Home({ go, openReport, reports, firstName, lastName, demo }: { go: (screen: Screen) => void; openReport: (id: string) => void; reports: PublicItemReport[]; firstName: string; lastName: string; demo: boolean }) {
  const displayName = firstName.trim();
  const hasName = /\p{L}/u.test(displayName);
  const greeting = greetingForHour(new Date().getHours());
  const greetingText = hasName ? `${greeting}, ${displayName}${greeting === "Up late" ? "?" : ""}` : greeting;
  const initials = hasName ? `${firstLetter(firstName)}${firstLetter(lastName)}` : "";
  const activeReports = reports.filter((report) => !["returned", "closed"].includes(report.status));
  return <main className="tab-page">
    <header className="home-header"><Brand /><button className="avatar" aria-label={hasName ? `Open ${displayName}'s profile` : "Open profile"} onClick={() => go("profile")}>{initials || <Icon name="user" size={18} />}</button></header>
    <section className="welcome"><p className="eyebrow">{greetingText}</p><h1>What are we looking for?</h1></section>
    <section className="action-grid">
      <button className="action-card found" onClick={() => go("capture")}><span className="action-icon"><Icon name="camera" size={29} /></span><span><strong>I found<br />something</strong><small>Help it ask Where RU?</small></span><Icon name="chevron" size={18} /></button>
      <button className="action-card lost" onClick={() => go("lost")}><span className="action-icon"><Icon name="search" size={29} /></span><span><strong>I lost<br />something</strong><small>Find your item</small></span><Icon name="chevron" size={18} /></button>
    </section>
    {demo && <section className="section priority-requests">
      <div className="section-heading"><div><h2>Priority requests</h2><p>Demo-only restricted role preview</p></div><span className="reputation-badge"><Icon name="shield" size={12} /> Demo helper view</span></div>
      <article className="priority-request-card">
        <span className="sensitive-item-icon"><Icon name="lock" /></span>
        <span className="item-info"><span className="sensitive-label">Demo role preview</span><strong>Restricted requests</strong><small>Private listings appear only to authorized helpers.</small></span>
      </article>
    </section>}
    <section className="section">
      <div className="section-heading"><h2>Active items</h2><button onClick={() => go("explore")}>See all</button></div>
      <div className="stack">{activeReports.slice(0, 3).map((report) => <ReportCard report={report} key={report.id} onClick={() => openReport(report.id)} />)}</div>
      {activeReports.length === 0 && <div className="empty-note"><Icon name="bag" /><p>No active reports yet.</p></div>}
    </section>
    <div className="tip-card"><Icon name="shield" /><div><strong>Your privacy comes first</strong><p>This prototype does not publicly expose claimant names or private evidence.</p></div></div>
  </main>;
}

const campusFilterOptions: Array<{ label: string; value: CampusId | "all" }> = [
  { label: "All", value: "all" },
  { label: "College Avenue", value: "College Ave" },
  { label: "Busch", value: "Busch" },
  { label: "Livingston", value: "Livingston" },
  { label: "Cook/Douglass", value: "Cook/Douglass" },
];

type ExploreState = {
  query: string;
  type: "all" | "lost" | "found";
  campus: CampusId | "all";
  category: ReportCategory | "all";
  sort: "newest" | "oldest";
  scrollY: number;
  /** How many results are drawn; grows as you scroll so a busy campus stays fast. */
  limit: number;
};

const EXPLORE_PAGE = 30;
const initialExploreState: ExploreState = { query: "", type: "all", campus: "all", category: "all", sort: "newest", scrollY: 0, limit: EXPLORE_PAGE };

function Explore({ go, openReport, state, setState }: { go: (screen: Screen) => void; openReport: (id: string) => void; state: ExploreState; setState: (update: ExploreState | ((current: ExploreState) => ExploreState)) => void }) {
  const { publicReports, notifications, currentUserId, markNotificationRead } = useReports();
  const [showReportChooser, setShowReportChooser] = useState(false);
  const { query, type, campus, category, sort, limit } = state;
  // Filter changes start again from the first page; "show more" keeps the current filters.
  const patch = (updates: Partial<ExploreState>) => setState((current) => ({ ...current, limit: EXPLORE_PAGE, ...updates }));
  const showMore = () => setState((current) => ({ ...current, limit: current.limit + EXPLORE_PAGE }));
  const moreRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const button = moreRef.current;
    if (!button || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver((entries) => { if (entries.some((entry) => entry.isIntersecting)) showMore(); }, { rootMargin: "400px" });
    observer.observe(button);
    return () => observer.disconnect();
  });
  useEffect(() => {
    const frame = window.requestAnimationFrame(() => window.scrollTo({ top: state.scrollY }));
    return () => window.cancelAnimationFrame(frame);
  }, []);
  const visible = useMemo(() => {
    const search = query.trim().toLowerCase();
    return publicReports
      .filter((report) => type === "all" || report.type === type)
      .filter((report) => campus === "all" || report.location?.campus === campus)
      .filter((report) => category === "all" || report.category === category)
      .filter((report) => !search || [report.itemName, report.category, report.publicDescription, report.location?.approximateLabel].join(" ").toLowerCase().includes(search))
      .sort((a, b) => sort === "newest" ? b.createdAt.localeCompare(a.createdAt) : a.createdAt.localeCompare(b.createdAt));
  }, [campus, category, publicReports, query, sort, type]);
  const hasFilters = Boolean(query || type !== "all" || campus !== "all" || category !== "all");
  const clearFilters = () => patch({ query: "", type: "all", campus: "all", category: "all" });
  const userNotifications = notifications.filter((notification) => notification.userId === currentUserId && !notification.read);
  const [showNotifications, setShowNotifications] = useState(false);
  return <main className="tab-page explore-page">
    <header className="title-header explore-title"><div><h1>Explore</h1><p>Lost &amp; found across Rutgers</p></div><button className="report-action" onClick={() => setShowReportChooser(!showReportChooser)}><Icon name="plus" size={17} /> Report</button></header>
    {userNotifications.length > 0 && <div className={`notification-menu ${showNotifications ? "open" : ""}`}>
      <button type="button" className="notification-menu-toggle" aria-expanded={showNotifications} onClick={() => setShowNotifications(!showNotifications)}>
        <span className="notification-bell"><Icon name="bell" size={18} /><b>{userNotifications.length}</b></span>
        <span><strong>{userNotifications.length === 1 ? "1 new notification" : `${userNotifications.length} new notifications`}</strong><small>{showNotifications ? "Tap to hide" : userNotifications[0].title}</small></span>
        <Icon name="chevron" size={17} />
      </button>
      {showNotifications && <div className="notification-menu-list">
        {userNotifications.map((notification) => <button className="catalog-notification" onClick={() => { markNotificationRead(notification.id); openReport(notification.reportId); }} key={notification.id}><Icon name="bell" size={18} /><span><strong>{notification.title}</strong><small>{notification.body}</small></span><Icon name="chevron" size={17} /></button>)}
        <button type="button" className="notification-clear" onClick={() => { userNotifications.forEach((notification) => markNotificationRead(notification.id)); setShowNotifications(false); }}>Mark all as read</button>
      </div>}
    </div>}
    {showReportChooser && <div className="report-chooser"><button onClick={() => go("capture")}><Icon name="camera" /><span><strong>I found something</strong><small>Photograph and report it safely</small></span></button><button onClick={() => go("lost")}><Icon name="search" /><span><strong>I lost something</strong><small>Create a lost-item listing</small></span></button></div>}
    <label className="catalog-search"><Icon name="search" size={19} /><input aria-label="Search reports" value={query} onChange={(event) => patch({ query: event.target.value })} placeholder="Search items, categories, or places" />{query && <button aria-label="Clear search" onClick={() => patch({ query: "" })}><Icon name="x" size={16} /></button>}</label>
    <div className="catalog-tabs" aria-label="Report type">{(["all", "lost", "found"] as const).map((value) => <button className={type === value ? "active" : ""} aria-pressed={type === value} onClick={() => patch({ type: value })} key={value}>{value[0].toUpperCase() + value.slice(1)}</button>)}</div>
    <div className="catalog-filter-label"><span>Campus</span><label>Sort <select value={sort} onChange={(event) => patch({ sort: event.target.value as "newest" | "oldest" })}><option value="newest">Newest first</option><option value="oldest">Oldest first</option></select></label></div>
    <div className="catalog-chips">{campusFilterOptions.map((option) => <button className={campus === option.value ? "active" : ""} aria-pressed={campus === option.value} onClick={() => patch({ campus: option.value })} key={option.value}>{option.label}</button>)}</div>
    <p className="catalog-filter-label">Category</p>
    <div className="catalog-chips category-chips"><button className={category === "all" ? "active" : ""} aria-pressed={category === "all"} onClick={() => patch({ category: "all" })}>All</button>{reportCategories.map((value) => <button className={category === value ? "active" : ""} aria-pressed={category === value} onClick={() => patch({ category: value })} key={value}>{value}</button>)}</div>
    <div className="catalog-results"><div className="section-heading"><h2>{visible.length} {visible.length === 1 ? "report" : "reports"}</h2>{hasFilters && <button onClick={clearFilters}>Clear filters</button>}</div>
      <div className="stack">{visible.slice(0, limit).map((report) => <ReportCard report={report} large key={report.id} onClick={() => openReport(report.id)} />)}</div>
      {visible.length > limit && <button ref={moreRef} type="button" className="show-more" onClick={showMore}>Show more <small>{visible.length - limit} left</small></button>}
      {publicReports.length === 0 && <CatalogEmpty icon="bag" title="No reports yet" text="Start the Rutgers lost-and-found catalog by reporting an item." action="Report an item" onAction={() => setShowReportChooser(true)} />}
      {publicReports.length > 0 && visible.length === 0 && <CatalogEmpty icon="search" title={query ? "No matching search results" : "No reports in these filters"} text="Try another campus or category, or clear the active filters." action="Clear filters" onAction={clearFilters} />}
    </div>
  </main>;
}

function CatalogEmpty({ icon, title, text, action, onAction }: { icon: IconName; title: string; text: string; action: string; onAction: () => void }) {
  return <div className="catalog-empty"><span><Icon name={icon} /></span><h2>{title}</h2><p>{text}</p><Button variant="secondary" onClick={onAction}>{action}</Button></div>;
}

function ReportDetail({ reportId, go, onBack, startFoundFromLost }: { reportId: string | null; go: (screen: Screen) => void; onBack: () => void; startFoundFromLost: (report: PublicItemReport) => void }) {
  const { reports, claims, currentUserId, closeReport, updateReport } = useReports();
  const [flagged, setFlagged] = useState(false);
  const report = reports.find((item) => item.id === reportId);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState(report?.itemName ?? "");
  const [editDescription, setEditDescription] = useState(report?.publicDescription ?? "");
  useEffect(() => {
    setEditing(false);
    setEditName(report?.itemName ?? "");
    setEditDescription(report?.publicDescription ?? "");
  }, [report?.id]);
  if (!report) return <main className="simple-page"><BackHeader title="Report unavailable" onBack={onBack} /><CatalogEmpty icon="lock" title="Restricted or unavailable report" text="This report may have been closed, removed, or is not available to your account." action="Go back" onAction={onBack} /></main>;
  const owner = report.reporterId === currentUserId;
  const safeReport = owner ? report : toPublicReport(report);
  const reportClaims = claims.filter((claim) => claim.reportId === report.id);
  const activeClaim = reportClaims.find((claim) => claim.claimantId === currentUserId && !["rejected", "returned"].includes(claim.status));
  const myClaim = reportClaims.filter((claim) => claim.claimantId === currentUserId).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))[0];
  const relatedFoundReports = reports.filter((candidate) => candidate.relatedLostReportId === report.id && (owner || candidate.visibility === "public"));
  const active = !["closed", "returned"].includes(report.status);
  return <main className="simple-page report-detail-page">
    <BackHeader title="Item details" onBack={onBack} action={<span className={`report-type-badge ${report.type}`}>{report.type}</span>} />
    <div className="detail-photo"><ReportImage src={safeReport.photoUrl} alt={`Reported ${safeReport.itemName}`} fallback={<span>{categoryIcon(safeReport.category)}</span>} /></div>
    <div className="detail-heading"><p className="eyebrow">{safeReport.sample ? `DEMO SAMPLE · ${safeReport.category}` : safeReport.category}</p><h1>{safeReport.itemName}</h1><Status>{reportStatusLabel(safeReport.status)}</Status></div>
    {owner && editing && <section className="detail-edit"><label className="result-field"><span>Item name</span><input value={editName} onChange={(event) => setEditName(event.target.value)} /></label><label className="textarea-field"><span>Public description</span><textarea value={editDescription} onChange={(event) => setEditDescription(event.target.value)} /></label><Button disabled={!editName.trim()} onClick={() => { updateReport(report.id, { itemName: editName.trim(), publicDescription: editDescription.trim() }); setEditing(false); }}>Save changes</Button></section>}
    {(report.sensitive || report.visibility !== "public") && !owner && <div className="private-note"><Icon name="shield" /><p><strong>Restricted details.</strong> Identifying features and the precise custody location stay private until a claim is reviewed.</p></div>}
    <section className="detail-card"><div><span>Description</span><p>{safeReport.publicDescription || "No public description provided."}</p></div><div><span>Approximate location</span><p>{safeReport.location?.approximateLabel || "Location unavailable"}</p></div><div><span>Submitted</span><p>{new Date(safeReport.createdAt).toLocaleString()}</p></div><div><span>{safeReport.type === "lost" ? "Last seen" : "Found"}</span><p>{new Date(safeReport.observedAt).toLocaleString()}</p></div>{safeReport.updatedAt !== safeReport.createdAt && <div><span>Last updated</span><p>{new Date(safeReport.updatedAt).toLocaleString()}</p></div>}{safeReport.relatedLostReportId && <div><span>Related lost report</span><p>{safeReport.relatedLostReportId} · potential relationship only</p></div>}{relatedFoundReports.length > 0 && <div><span>Potential found reports</span><p>{relatedFoundReports.map((candidate) => candidate.id).join(", ")} · not verified matches</p></div>}</section>
    <div className="recovery-note"><Icon name={report.sensitive ? "shield" : "bag"} /><p><strong>{report.sensitive ? "Use an official staffed return point." : "Keep recovery public and safe."}</strong><br />Never post private identifiers or meet in an isolated location.</p></div>
    {!owner && myClaim && <ClaimStatusCard claim={myClaim} report={report} />}
    {!owner && myClaim && ["approved", "handoff", "returned"].includes(myClaim.status) && <ClaimChat claim={myClaim} report={report} />}
    {owner ? <div className="detail-actions">
      <p className="helper-text">This is your report. Claim actions are disabled for your own listing.</p>
      {reportClaims.length > 0 && <Button onClick={() => go("finderStatus")}>Review {reportClaims.length} {reportClaims.length === 1 ? "claim" : "claims"}</Button>}
      {active && <Button variant="secondary" onClick={() => setEditing(!editing)}>{editing ? "Cancel editing" : "Edit report"}</Button>}
      {active && <Button variant="secondary" onClick={() => closeReport(report.id)}>Close report</Button>}
    </div> : active ? <div className="detail-actions">
      {report.type === "found" ? activeClaim ? <Button variant="secondary" onClick={() => go("home")}>Back to home</Button> : <Button onClick={() => go("ownership")}>{myClaim?.status === "rejected" ? "Try again with another detail" : "This might be mine"}</Button> : <Button onClick={() => startFoundFromLost(toPublicReport(report))}>I may have found this</Button>}
      <Button variant="ghost" onClick={() => setFlagged(true)}>{flagged ? "Listing flagged for demo review" : "Report suspicious listing"}</Button>
    </div> : null}
  </main>;
}

/** Chat between the finder and the claimant, available once the claim is approved. */
function ClaimChat({ claim, report }: { claim: Claim; report: ItemReport }) {
  const { currentUserId, users, notifyUser } = useReports();
  const [messages, setMessages] = useState<api.ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [offline, setOffline] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const otherId = currentUserId === claim.claimantId ? report.reporterId : claim.claimantId;
  const other = users.find((user) => user.id === otherId);
  const otherName = other ? other.firstName || "them" : currentUserId === claim.claimantId ? "the finder" : "the owner";
  useEffect(() => {
    let active = true;
    const load = () => api.getClaimChat(claim.id).then((list) => {
      if (!active) return;
      if (list === null) { setOffline(true); return; }
      setOffline(false);
      setMessages((current) => current.length === list.length && current[current.length - 1]?.id === list[list.length - 1]?.id ? current : list);
    }).catch(() => active && setOffline(true));
    load();
    const timer = window.setInterval(load, 2000);
    return () => { active = false; window.clearInterval(timer); };
  }, [claim.id]);
  useEffect(() => { listRef.current?.scrollTo({ top: listRef.current.scrollHeight }); }, [messages.length]);
  const send = async () => {
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    try {
      setMessages(await api.sendClaimChat(claim.id, currentUserId, text));
      setError("");
      notifyUser(otherId, report.id, `Message about the ${report.itemName.toLowerCase()}`, text.length > 90 ? `${text.slice(0, 90)}…` : text);
    } catch (sendError) {
      setDraft(text);
      setError(sendError instanceof Error ? sendError.message : "Message not sent.");
    }
  };
  return <section className="claim-chat">
    <div className="claim-chat-head"><Icon name="user" size={18} /><div><strong>Chat with {otherName}</strong><small>Agree on a public place and time. Never share passwords or codes.</small></div></div>
    <div className="claim-chat-list" ref={listRef} aria-live="polite">
      {messages.length === 0 && <p className="claim-chat-empty">{offline ? "Chat needs the demo server running." : "No messages yet. Say hi and suggest where to meet."}</p>}
      {messages.map((message) => <div className={`chat-bubble ${message.sender === currentUserId ? "mine" : ""}`} key={message.id}><p>{message.text}</p><small>{new Date(message.at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</small></div>)}
    </div>
    {error && <div className="camera-error" role="alert">{error}</div>}
    <form className="claim-chat-form" onSubmit={(event) => { event.preventDefault(); send(); }}>
      <input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder={`Message ${otherName}`} maxLength={500} aria-label="Message" disabled={offline} />
      <button type="submit" disabled={!draft.trim() || offline} aria-label="Send message"><Icon name="chevron" size={18} /></button>
    </form>
  </section>;
}

/** What the claimant sees about their own claim, updated live as the finder acts on it. */
function ClaimStatusCard({ claim, report }: { claim: Claim; report: ItemReport }) {
  const place = report.location?.approximateLabel || "a public campus location";
  const views: Record<Claim["status"], { tone: string; icon: IconName; title: string; text: string }> = {
    submitted: { tone: "pending", icon: "clock", title: "Claim under review", text: "The finder is comparing your private detail with theirs. You'll get a notification when they decide." },
    approved: { tone: "approved", icon: "check", title: "Claim approved", text: `The finder confirmed your detail and is arranging the return. You'll be notified when it's ready to pick up. Item location: ${place}.` },
    handoff: { tone: "approved", icon: "bag", title: "Ready for pickup", text: claim.handoffNote ? `The finder left it at ${claim.handoffNote}. Bring your Rutgers ID and confirm hours before you go.` : "The finder dropped it off at a staffed location. Bring your Rutgers ID." },
    returned: { tone: "approved", icon: "check", title: "Returned", text: "The finder marked this item as returned to you. Glad it found its way back." },
    rejected: { tone: "rejected", icon: "lock", title: "Claim not approved", text: "Your detail didn't match what the finder recorded. If it's yours, try again with a more specific detail." },
  };
  const view = views[claim.status];
  return <div className={`claim-status-card ${view.tone}`} role="status"><span><Icon name={view.icon} size={22} /></span><div><p className="eyebrow">YOUR CLAIM</p><strong>{view.title}</strong><p>{view.text}</p></div></div>;
}

type FoundReport = {
  photoUrl: string | null;
  photoPreviewUrl: string | null;
  sample: boolean;
  title: string;
  category: string;
  color: string;
  description: string;
  hideDetails: boolean;
  location: RoomLocation | null;
  foundAt: string;
  relatedLostReportId?: string;
  photoFile: File | null;
  aiDemo: boolean;
  aiNote?: string;
  cardWords?: string[];
  cardName?: string | null;
};

const emptyFoundReport: FoundReport = { photoUrl: null, photoPreviewUrl: null, photoFile: null, aiDemo: true, sample: false, title: "", category: "", color: "", description: "", hideDetails: true, location: null, foundAt: "" };

function normalizeCategory(value: string): ReportCategory {
  const normalized = value.toLowerCase();
  if (normalized.includes("wallet") || normalized.includes("id")) return "Wallets/IDs";
  if (normalized.includes("key")) return "Keys";
  if (normalized.includes("bag") || normalized.includes("backpack")) return "Bags";
  if (normalized.includes("cloth") || normalized.includes("hoodie")) return "Clothing";
  if (normalized.includes("bottle")) return "Bottles";
  if (normalized.includes("school") || normalized.includes("notebook") || normalized.includes("calculator")) return "School Supplies";
  if (normalized.includes("electronic") || normalized.includes("phone") || normalized.includes("laptop") || normalized.includes("airpod")) return "Electronics";
  return "Other";
}

function roomToReportLocation(location: RoomLocation): ReportLocation {
  const known = campusPlaces.find((place) => place.name === location.building);
  const room = location.room.trim();
  return {
    campus: location.campus,
    area: location.building,
    building: location.building,
    room: room || undefined,
    source: room ? location.source : "manual-area",
    placeType: room ? "classroom" : known?.placeType || "building",
    approximateLabel: `Near ${location.building}`,
    approximateCoordinates: known?.coordinates,
    precise: { label: formatLocation(location), coordinates: known?.coordinates },
  };
}

function localDateTimeValue(date = new Date()) {
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function localDateTimeToIso(value: string) {
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toISOString() : null;
}

function Capture({ go, report, setReport }: { go: (screen: Screen) => void; report: FoundReport; setReport: (update: (current: FoundReport) => FoundReport) => void }) {
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");
  const hasPhoto = Boolean(report.photoPreviewUrl || report.photoUrl) || report.sample;
  const setPhoto = (reference: string | null, preview: string | null, sample: boolean, file: File | null = null) => {
    setError("");
    setReport((current) => ({ ...current, photoUrl: reference, photoPreviewUrl: preview, photoFile: file, sample, foundAt: current.foundAt || localDateTimeValue() }));
  };
  const savePhoto = async (file: File, preview: string) => {
    try {
      const reference = await storeReportImage(file);
      setPhoto(reference, preview, false, file);
    } catch (photoError) {
      setPhoto(null, preview, false, file);
      setError(photoError instanceof Error ? `${photoError.message} The preview is not attached yet.` : "The photo could not be stored.");
    }
  };
  const usePhoto = async () => {
    if (report.photoPreviewUrl && !report.photoUrl) {
      setError("Wait for the photo to finish saving locally, or choose another photo.");
      return;
    }
    if (!report.sample && !report.photoFile) {
      go("locate");
      return;
    }
    setAnalyzing(true);
    // Real photos go to the backend's on-device item recognizer; the sample uses demo data.
    const result = await activeRecognizer.describeItem(report.sample ? null : report.photoFile);
    setReport((current) => ({
      ...current,
      title: current.title || result.title,
      category: current.category || result.category,
      color: current.color || result.color,
      description: current.description || result.description,
      aiDemo: result.demo !== false,
      aiNote: result.error,
      cardWords: result.cardWords ?? [],
      cardName: result.cardName ?? null,
    }));
    setAnalyzing(false);
    go("locate");
  };
  if (analyzing) return <main className="camera-screen analyzing" aria-live="polite" aria-busy="true">
    <div className="scan-orbit"><Icon name="sparkles" size={34} /></div>
    <h1>Describing the item…</h1><p>Picking out the category, color, and details you can edit next.</p>
    {report.sample ? <DemoTag>Demo description</DemoTag> : <span className="demo-tag live"><Icon name="check" size={12} />On-device</span>}
  </main>;
  return <main className="camera-screen with-bottom">
    <BackHeader title="Found something" onBack={() => go("home")} action={<span className="camera-step">1/3</span>} />
    <div className="capture-copy"><p className="eyebrow">STEP 1 OF 3 · PHOTOGRAPH ITEM</p><h1>Photograph the item</h1><p>Fit the whole item in the frame, in good light.</p></div>
    <div className={`camera-frame ${hasPhoto ? "has-photo" : ""}`}>
      <span className="corner tl" /><span className="corner tr" /><span className="corner bl" /><span className="corner br" />
      {report.photoPreviewUrl ? <img className="photo-preview" src={report.photoPreviewUrl} alt="Your photo of the found item" /> : <div className={`bottle ${report.sample ? "" : "ghost"}`}><span className="cap" /><span className="bottle-body"><span className="sticker">★</span></span></div>}
      <div className="camera-guide">{hasPhoto ? (report.sample ? "Sample photo" : "Looks good? Use it or retake") : "No photo yet"}</div>
    </div>
    {error && <div className="camera-error" role="alert">{error}</div>}
    <div className="bottom-action camera-actions">
      {hasPhoto ? <div className="photo-buttons">
        <Button onClick={usePhoto}>Use this photo <Icon name="chevron" size={18} /></Button>
        <Button variant="secondary" onClick={() => setPhoto(null, null, false)}><Icon name="refresh" size={18} /> Retake</Button>
      </div> : <>
        <PhotoButtons cameraLabel="Take photo" onPhoto={savePhoto} onError={setError} />
        <button type="button" className="text-button sample on-dark" onClick={() => setPhoto(null, null, true)}>Use a clearly labeled demo sample</button>
      </>}
    </div>
  </main>;
}

function Locate({ go, report, setReport }: { go: (screen: Screen) => void; report: FoundReport; setReport: (update: (current: FoundReport) => FoundReport) => void }) {
  const [campus, setCampus] = useState<CampusId>("College Ave");
  const [area, setArea] = useState("");
  const useArea = () => {
    const name = area.trim();
    if (!name) return;
    setReport((current) => ({ ...current, location: { campus, building: name, code: "", room: "", source: "manual" } }));
  };
  return <main className="simple-page with-bottom">
    <BackHeader title="Identify location" onBack={() => go("capture")} action={<span className="flow-count">2 of 3</span>} />
    <p className="eyebrow">STEP 2 OF 3 · SCAN CLASSROOM</p>
    <h1 className="flow-title">Where did you find it?</h1>
    <p className="subtext">Scan the room to identify it. If that doesn't work, scan the door placard or choose the room.</p>
    <LocationPicker context="found" value={report.location} onChange={(location) => setReport((current) => ({ ...current, location }))} />
    {!report.location && <div className="manual-area-card"><p className="or-divider">or use a broader place</p><label className="result-field"><span>Campus</span><select value={campus} onChange={(event) => setCampus(event.target.value as CampusId)}>{campusOptions.map((option) => <option key={option}>{option}</option>)}</select></label><label className="result-field"><span>Landmark, hallway, bus stop, or area</span><input value={area} onChange={(event) => setArea(event.target.value)} placeholder="e.g. College Ave Student Center" /></label><Button variant="secondary" disabled={!area.trim()} onClick={useArea}>Use this area</Button></div>}
    <div className="bottom-action">
      {!report.location && <p className="action-hint">Confirm a room to continue.</p>}
      <Button disabled={!report.location} onClick={() => go("confirm")}>Continue <Icon name="chevron" size={18} /></Button>
    </div>
  </main>;
}

function Confirm({ go, report, setReport, onSubmit }: { go: (screen: Screen) => void; report: FoundReport; setReport: (update: (current: FoundReport) => FoundReport) => void; onSubmit: () => void }) {
  const set = (key: "title" | "category" | "color" | "description") => (event: ChangeEvent<HTMLInputElement>) => setReport((current) => ({ ...current, [key]: event.target.value }));
  const location = report.location;
  const validObservedAt = Boolean(localDateTimeToIso(report.foundAt));
  const ready = Boolean(report.title.trim() && location && validObservedAt);
  return <main className="simple-page with-bottom">
    <BackHeader title="Review report" onBack={() => go("locate")} action={<span className="flow-count">3 of 3</span>} />
    <div className="ai-banner"><span><Icon name="sparkles" size={20} /></span><div><strong>Check the details</strong><p>{report.aiNote || (report.cardName ? `Name on the card: ${report.cardName}. It stays private and is used only to notify the owner if they use Where RU?.` : "Everything below is editable before the report is saved.")}</p></div>{report.aiDemo ? <DemoTag>Demo AI</DemoTag> : <span className="demo-tag live"><Icon name="check" size={12} />On-device</span>}</div>
    <section className="form-section"><h2>Item</h2>
      <div className="review-photo">{report.photoPreviewUrl ? <img src={report.photoPreviewUrl} alt="Found item" /> : <span className="detail-category-icon">{categoryIcon(normalizeCategory(report.category))}</span>}<button type="button" className="text-button" onClick={() => go("capture")}>{report.photoPreviewUrl ? "Replace photo" : "Add photo"}</button></div>
      <label className="result-field"><span>Item</span><input value={report.title} onChange={set("title")} /></label>
      <div className="field-row"><label className="result-field half"><span>Category</span><input value={report.category} onChange={set("category")} /></label><label className="result-field half"><span>Color</span><input value={report.color} onChange={set("color")} /></label></div>
      <label className="result-field"><span>Details</span><input value={report.description} onChange={set("description")} /></label>
    </section>
    <section className="form-section"><h2>Location</h2>
      {location ? <LocationSummary location={location} onChange={() => go("locate")} /> : <Button variant="secondary" onClick={() => go("locate")}>Identify location</Button>}
      <label className="result-field"><span>Date and time found</span><input type="datetime-local" max={localDateTimeValue()} value={report.foundAt} onChange={(event) => setReport((current) => ({ ...current, foundAt: event.target.value }))} /></label>
      {!validObservedAt && <p className="form-hint">Choose when the item was found.</p>}
    </section>
    <section className="form-section"><div className="section-heading"><h2>Possible lost listing matches</h2><span className="private-label"><Icon name="shield" size={14} /> Anonymous</span></div>
      {report.relatedLostReportId ? <article className="class-match"><span className="time-box"><Icon name="search" size={18} /></span><div><strong>Linked lost report</strong><p>Report {report.relatedLostReportId}</p></div></article> : <p className="helper-text">No match analysis has been run. Potential matches remain suggestions until reviewed.</p>}
    </section>
    <div className="toggle-card"><Toggle on={report.hideDetails} setOn={(hideDetails) => setReport((current) => ({ ...current, hideDetails }))} label="Hide identifying details from public description" /><p>Stickers and damage stay private and can help the reporter review a claim.</p></div>
    <div className="bottom-action">
      {!ready && <p className="action-hint">Add an item name, location, and valid event time to continue.</p>}
      <Button disabled={!ready} onClick={onSubmit}><Icon name="plus" size={19} /> Post found report</Button>
    </div>
  </main>;
}

function FinderStatus({ go, report, claims, onUpdateClaim }: { go: (screen: Screen) => void; report?: ItemReport; claims: Claim[]; onUpdateClaim: (id: string, status: Claim["status"]) => void }) {
  const { currentUserId, getClaimAnswer, switchUser } = useReports();
  const [actionError, setActionError] = useState("");
  if (!report) return <main className="simple-page"><BackHeader title="Item status" onBack={() => go("explore")} /><CatalogEmpty icon="lock" title="Report unavailable" text="This report is no longer available." action="Back to Explore" onAction={() => go("explore")} /></main>;
  if (report.reporterId !== currentUserId) return <main className="simple-page"><BackHeader title="Claim review" onBack={() => go("detail")} /><CatalogEmpty icon="lock" title="Finder review only" text="Only the finder who posted this report can review its private ownership claims." action="Back to report" onAction={() => go("detail")} /></main>;
  const where = report.location?.approximateLabel || "Location unavailable";
  const reportClaims = claims.filter((claim) => claim.reportId === report.id);
  const timeline = [
    [report.type === "found" ? "Found report posted" : "Lost report posted", new Date(report.createdAt).toLocaleString(), true],
    ["Possible match", report.status === "possible_match" ? "Potential related report found" : "No confirmed match", ["possible_match", "claim_under_review", "returned"].includes(report.status)],
    ["Claim under review", reportClaims.length ? `${reportClaims.length} private claim${reportClaims.length === 1 ? "" : "s"}` : "No claims submitted", ["claim_under_review", "returned"].includes(report.status)],
    ["Returned", report.status === "returned" ? "Recovery completed" : "Not completed", report.status === "returned"],
  ] as const;
  return <main className="simple-page with-nav">
    <BackHeader title="Item status" onBack={() => go("detail")} />
    <article className="status-hero"><div className="item-visual"><ReportImage src={report.photoUrl} alt="" fallback={<span className="detail-category-icon">{categoryIcon(report.category)}</span>} /></div><div><Status>{reportStatusLabel(report.status)}</Status><h1>{report.itemName}</h1><p>{where} · event {relativeTime(report.observedAt).toLowerCase()}</p></div></article>
    <div className="notice-card"><span><Icon name="bell" /></span><div><strong>{reportClaims.length ? "Claim activity recorded" : "Report is active"}</strong><p>{reportClaims.length ? "Private claim details are available for demo review below." : "No match or notification is claimed until an event is created."}</p></div></div>
    <section className="timeline">
      {timeline.map(([label, detail, done], i) => <div className={`${done ? "done" : ""} ${i === 2 && report.status === "claim_under_review" ? "current" : ""}`} key={label}><span className="timeline-dot">{done ? <Icon name="check" size={13} /> : i + 1}</span><div><strong>{label}</strong><p>{detail}</p></div></div>)}
    </section>
    {actionError && <div className="camera-error" role="alert">{actionError}</div>}
    {reportClaims.map((claim) => {
      const answer = getClaimAnswer(claim.id);
      return <div className="demo-next" key={claim.id}><p className="eyebrow">SIMULATED CLAIM · {claim.status}</p><h3>Compare private details</h3><p><strong>Finder's hidden report detail:</strong><br />{report.privateDetails || "No hidden finder detail was recorded."}</p><p><strong>Claimant's private answer:</strong><br />{answer || "Private answer unavailable after refresh — ask the claimant to resubmit."}</p>
        {claim.status === "submitted" && <div className="detail-actions"><Button variant="secondary" onClick={() => { try { onUpdateClaim(claim.id, "rejected"); setActionError(""); } catch (error) { setActionError(error instanceof Error ? error.message : "Unable to reject claim."); } }}>Reject claim</Button><Button disabled={!answer} onClick={() => { try { onUpdateClaim(claim.id, "approved"); go("handoff"); } catch (error) { setActionError(error instanceof Error ? error.message : "Unable to approve claim."); } }}>Approve claim</Button></div>}
        {["approved", "handoff"].includes(claim.status) && <Button onClick={() => go("handoff")}>Arrange handoff</Button>}
        {["approved", "handoff", "returned"].includes(claim.status) && <ClaimChat claim={claim} report={report} />}
      </div>;
    })}
    {report.type === "found" && reportClaims.length === 0 && <div className="demo-next"><p className="eyebrow">INTERACTIVE DEMO</p><h3>Preview a claim event</h3><p>This creates a labeled in-app demo claim from a different simulated user.</p><Button variant="secondary" onClick={() => { switchUser("demo-maya"); go("ownerNotice"); }}>Preview demo notification <Icon name="chevron" size={18} /></Button></div>}
  </main>;
}

function OwnerNotice({ go, report }: { go: (screen: Screen) => void; report?: ItemReport }) {
  if (!report) return <main className="simple-page"><CatalogEmpty icon="lock" title="Report unavailable" text="The associated report could not be found." action="Back to Explore" onAction={() => go("explore")} /></main>;
  const title = report.itemName.toLowerCase();
  const where = report.location?.approximateLabel || "an approximate Rutgers location";
  const at = new Date(report.observedAt).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  return <main className="simple-page notice-page">
    <BackHeader title="Notification preview" onBack={() => go("finderStatus")} />
    <div className="phone-lock">
      <div className="lock-top"><span>{at.replace(/\s?[AP]M/, "")}</span><small>Today</small></div>
      <article className="push-card"><div className="push-head"><BrandIcon className="app-mini" /><Wordmark size="notification" /><small>now</small></div><h3>Where RU? Possible match</h3><p>Is this your {title}? It was found in <strong>{where}</strong>.</p></article>
    </div>
    <p className="eyebrow center">DEMO IN-APP NOTIFICATION</p>
    <p className="privacy-note"><Icon name="user" size={16} /> Switched to Maya (demo) to preview the owner's side.</p>
    <article className="claim-card"><span className="claim-icon"><Icon name="search" /></span><h2>Could this be yours?</h2><p>A {title} was reported near <strong>{where}</strong>. This preview does not represent a verified match or real notification.</p><div className="found-meta"><Icon name="clock" size={18} /><span><strong>Observed at {at}</strong><small>Linked to report {report.id}</small></span></div><Button onClick={() => go("ownership")}>This might be mine</Button><Button variant="ghost" onClick={() => go("detail")}>Not mine</Button></article>
    <p className="privacy-note"><Icon name="shield" size={16} /> The finder won't know you received this.</p>
  </main>;
}

function Ownership({ go, report, claimantId, onSubmit }: { go: (screen: Screen) => void; report?: ItemReport; claimantId: string; onSubmit: (reportId: string, detail: string) => Claim }) {
  const [detail, setDetail] = useState("");
  const [chips, setChips] = useState<string[]>([]);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");
  const toggleChip = (chip: string) => setChips(chips.includes(chip) ? chips.filter((c) => c !== chip) : [...chips, chip]);
  if (!report) return <main className="simple-page"><CatalogEmpty icon="lock" title="Invalid claim" text="A claim must reference an available report." action="Back to Explore" onAction={() => go("explore")} /></main>;
  if (report.reporterId === claimantId) return <main className="simple-page"><CatalogEmpty icon="lock" title="This is your listing" text="You cannot submit an ownership claim against your own report." action="Back to report" onAction={() => go("detail")} /></main>;
  if (["closed", "returned"].includes(report.status)) return <main className="simple-page"><CatalogEmpty icon="lock" title="Claims unavailable" text="This report is no longer accepting ownership claims." action="Back to report" onAction={() => go("detail")} /></main>;
  if (submitted) return <ResultState tone="green" icon="check" title="Claim submitted" text="The finder will compare your private detail with theirs. You'll get a notification when they decide." button="Back to home" onClick={() => go("home")} secondary="View claim status" onSecondary={() => go("detail")} eyebrow="DEMO CLAIM" />;
  return <main className="simple-page with-bottom">
    <BackHeader title="Private Verification" onBack={() => go("detail")} />
    <div className="verify-heading"><span><Icon name="shield" size={27} /></span><p className="eyebrow">PRIVATE VERIFICATION</p><h1>Tell us something only the owner would know.</h1><p>Only the finder sees this answer. It is never posted publicly.</p></div>
    <label className="textarea-field"><span>Private detail</span><textarea value={detail} onChange={(e) => setDetail(e.target.value)} placeholder="For example: There's a small white cat sticker near the bottom…" /></label>
    {error && <div className="camera-error" role="alert">{error}</div>}
    <p className="field-label">What kind of detail are you sharing? <small>Optional</small></p>
    <div className="chip-row">{["Sticker", "Engraving", "Contents", "Damage"].map((chip) => <button key={chip} aria-pressed={chips.includes(chip)} className={chips.includes(chip) ? "selected" : ""} onClick={() => toggleChip(chip)}>{chips.includes(chip) && <Icon name="check" size={14} />}{chip}</button>)}</div>
    <div className="bottom-action">
      {detail.trim().length < 8 && <p className="action-hint">Enter at least 8 characters to continue.</p>}
      <Button disabled={detail.trim().length < 8} onClick={() => { try { onSubmit(report.id, detail.trim()); setSubmitted(true); setError(""); } catch (claimError) { setError(claimError instanceof Error ? claimError.message : "The claim could not be submitted."); } }}>Submit claim for review</Button>
    </div>
  </main>;
}

function ResultState({ tone, icon, title, text, button, onClick, secondary, onSecondary, eyebrow = "PRIVATE VERIFICATION" }: { tone: string; icon: IconName; title: string; text: string; button: string; onClick: () => void; secondary?: string; onSecondary?: () => void; eyebrow?: string }) {
  return <main className="result-screen"><div className={`result-icon ${tone}`}><Icon name={icon} size={42} /></div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p>{text}</p><Button onClick={onClick}>{button}</Button>{secondary && onSecondary && <Button variant="secondary" onClick={onSecondary}>{secondary}</Button>}</main>;
}

function Handoff({ go, report, claim, onUpdateClaim }: { go: (screen: Screen) => void; report?: ItemReport; claim?: Claim; onUpdateClaim: (id: string, status: Claim["status"], note?: string) => void }) {
  const { currentUserId } = useReports();
  const recommendDropOff = Boolean(report?.sensitive);
  const [returned, setReturned] = useState(false);
  const [handoffMethod, setHandoffMethod] = useState<"meet" | "drop">(recommendDropOff ? "drop" : "meet");
  const [meeting, setMeeting] = useState("College Ave Student Center");
  const [dropLocation, setDropLocation] = useState("Student Center information desk");
  const [readyForPickup, setReadyForPickup] = useState(false);
  const [problemReported, setProblemReported] = useState(false);
  const [actionError, setActionError] = useState("");
  const beginPickup = () => {
    try {
      if (!claim) throw new Error("The approved claim is unavailable.");
      onUpdateClaim(claim.id, "handoff", dropLocation);
      setActionError("");
      setReadyForPickup(true);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to arrange the handoff.");
    }
  };
  const completeReturn = () => {
    try {
      if (!claim) throw new Error("The approved claim is unavailable.");
      if (claim.status === "approved") onUpdateClaim(claim.id, "handoff", handoffMethod === "meet" ? meeting : dropLocation);
      onUpdateClaim(claim.id, "returned");
      setActionError("");
      setReturned(true);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to mark the item returned.");
      setProblemReported(true);
    }
  };
  if (returned) return <ResultState tone="green" icon="check" title="Return marked complete" text="This simulated handoff is now recorded as returned in the local demo." button="Back to home" onClick={() => go("home")} eyebrow="SIMULATED HANDOFF" />;
  if (!report || report.reporterId !== currentUserId || !claim || claim.status !== "approved" && claim.status !== "handoff") return <main className="simple-page"><CatalogEmpty icon="lock" title="Return unavailable" text="Only the finder can arrange a return after approving a claim." action="Back to report" onAction={() => go("detail")} /></main>;
  if (readyForPickup) return <main className="simple-page with-bottom">
    <BackHeader title="Item pickup" onBack={() => setReadyForPickup(false)} />
    <div className="verified-hero"><div className="result-icon green"><Icon name="check" size={30} /></div><h1>Simulated pickup plan</h1><p>No real drop-off or custody confirmation has been made.</p></div>
    <article className="meeting-card selected"><span><Icon name="map" /></span><div><strong>{dropLocation}</strong><p>Demo selection only; confirm details directly before traveling.</p></div><Icon name="check" size={18} /></article>
    <ClaimChat claim={claim} report={report} />
    {actionError && <div className="camera-error" role="alert">{actionError}</div>}
    <div className="bottom-action"><Button onClick={completeReturn}>I picked it up</Button></div>
  </main>;
  return <main className="simple-page with-bottom">
    <BackHeader title="Arrange a handoff" onBack={() => go("finderStatus")} />
    <div className="verified-hero"><div className="result-icon green"><Icon name="check" size={30} /></div><Status>Approved</Status><h1>Simulated approval</h1><p>The listing owner reviewed the private answer in this frontend demo. This is not identity or ownership verification.</p></div>
    <section className="handoff-choice"><h2>How do you want to return it?</h2>
      <div className="method-cards">
        <button aria-pressed={handoffMethod === "meet"} className={handoffMethod === "meet" ? "selected" : ""} onClick={() => setHandoffMethod("meet")}><span className="method-icon"><Icon name="user" size={27} /></span><span><strong>Meet in person</strong><small>Choose a public campus meeting spot</small></span><span className="radio-dot">{handoffMethod === "meet" && <span />}</span></button>
        <button aria-pressed={handoffMethod === "drop"} className={handoffMethod === "drop" ? "selected" : ""} onClick={() => setHandoffMethod("drop")}><span className="method-icon"><Icon name="bag" size={27} /></span><span><strong>Drop it off</strong><small>Leave it at a staffed pickup location</small></span><span className="radio-dot">{handoffMethod === "drop" && <span />}</span></button>
      </div>
    </section>
    {actionError && <div className="camera-error" role="alert">{actionError}</div>}
    {recommendDropOff && <div className="warning-banner"><strong>For your safety, we recommend dropping this at an official lost and found.</strong></div>}
    <section className="identity-card"><p className="eyebrow">DEMO PARTICIPANTS</p><div className="people"><div><span className="person-avatar scarlet">C</span><strong>Claimant</strong><small>Simulated role</small></div><span className="meet-line"><Icon name="chevron" /><Icon name="chevron" /></span><div><span className="person-avatar blue">R</span><strong>Reporter</strong><small>Simulated role</small></div></div></section>
    {handoffMethod === "meet" ? <>
      <section className="meeting-section"><h2>Choose a public meeting spot</h2><p>Meet in a staffed, well-lit campus location.</p>
        <button className={`meeting-card ${meeting === "College Ave Student Center" ? "selected" : ""}`} aria-pressed={meeting === "College Ave Student Center"} onClick={() => setMeeting("College Ave Student Center")}><span><Icon name="map" /></span><div><strong>College Ave Student Center</strong><p>Confirm a public meeting point and current hours yourself</p></div>{meeting === "College Ave Student Center" ? <Icon name="check" size={18} /> : <Icon name="chevron" size={18} />}</button>
        <button className={`meeting-card ${meeting === "Alexander Library" ? "selected" : ""}`} aria-pressed={meeting === "Alexander Library"} onClick={() => setMeeting("Alexander Library")}><span><Icon name="map" /></span><div><strong>Alexander Library</strong><p>Confirm a staffed meeting point and current hours yourself</p></div>{meeting === "Alexander Library" ? <Icon name="check" size={18} /> : <Icon name="chevron" size={18} />}</button>
      </section>
      <ClaimChat claim={claim} report={report} />
      <div className="bottom-action dual"><Button onClick={completeReturn}>Mark as returned</Button><Button variant="ghost" onClick={() => setProblemReported(true)} className={problemReported ? "reported" : ""}>Report a problem</Button></div>
    </> : <>
      <section className="meeting-section"><h2>Choose a drop-off location</h2><p>Leave the item with staff and keep the receipt.</p>
        <button className={`meeting-card ${dropLocation === "Student Center information desk" ? "selected" : ""}`} aria-pressed={dropLocation === "Student Center information desk"} onClick={() => setDropLocation("Student Center information desk")}><span><Icon name="map" /></span><div><strong>Student Center information desk</strong><p>Demo option; confirm acceptance and current hours directly</p></div>{dropLocation === "Student Center information desk" ? <Icon name="check" size={18} /> : <Icon name="chevron" size={18} />}</button>
        <button className={`meeting-card ${dropLocation === "Confirmed official lost-and-found office" ? "selected" : ""}`} aria-pressed={dropLocation === "Confirmed official lost-and-found office"} onClick={() => setDropLocation("Confirmed official lost-and-found office")}><span><Icon name="shield" /></span><div><strong>Confirmed official lost-and-found office</strong><p>Locate and confirm an appropriate office before traveling</p></div>{dropLocation === "Confirmed official lost-and-found office" ? <Icon name="check" size={18} /> : <Icon name="chevron" size={18} />}</button>
        <button className="meeting-card" disabled><span><Icon name="lock" /></span><div><strong>Where RU? Locker (coming soon)</strong><p>Secure self-service pickup</p></div></button>
      </section>
      <ClaimChat claim={claim} report={report} />
      <div className="bottom-action"><Button onClick={beginPickup}>I dropped it off</Button></div>
    </>}
  </main>;
}

function currentTimeValue() {
  const now = new Date();
  return `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
}

function formatTimelineTime(value: string) {
  const [hours, minutes] = value.split(":").map(Number);
  return new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" }).format(new Date(2025, 0, 1, hours, minutes));
}

type LostSubmission = {
  clientSubmissionId: string;
  itemName: string;
  itemDescription: string;
  category: string;
  color: string;
  observedAt: string;
  sensitive: boolean;
  photoUrl: string | null;
  location: ReportLocation | null;
  visibility: "public" | "trusted-only";
};

function Lost({ go, openReport, onSubmit, sensitiveItems }: { go: (screen: Screen) => void; openReport: (id: string) => void; onSubmit: (submission: LostSubmission) => string; sensitiveItems: SensitiveItem[] }) {
  const { reports, currentUserId } = useReports();
  const [step, setStep] = useState(1);
  const [posted, setPosted] = useState(false);
  const [submittedId, setSubmittedId] = useState<string | null>(null);
  const [submissionKey] = useState(() => `lost-${Date.now()}-${Math.random()}`);
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [photoPreviewUrl, setPhotoPreviewUrl] = useState<string | null>(null);
  const [photoError, setPhotoError] = useState("");
  const [itemName, setItemName] = useState("");
  const [itemDescription, setItemDescription] = useState("");
  const [category, setCategory] = useState("");
  const [color, setColor] = useState("");
  const [rememberedAt, setRememberedAt] = useState(localDateTimeValue());
  const [value, setValue] = useState("Everyday item");
  const [method, setMethod] = useState<"retrace" | "room" | null>(null);
  const [lostLocation, setLostLocationState] = useState<RoomLocation | null>(null);
  const setLostLocation = (location: RoomLocation | null) => {
    setLostLocationState(location);
    setPlaces((current) => {
      const rest = current.filter((place) => place.source !== "Known room");
      if (!location) return rest;
      return [{ id: -1, time: "Today", sortMinutes: -1, name: formatLocation(location), source: "Known room", high: true }, ...rest];
    });
  };
  const [places, setPlaces] = useState<TimelinePlace[]>([]);
  const [manualPlace, setManualPlace] = useState("");
  const [manualRoom, setManualRoom] = useState("");
  const [manualTime, setManualTime] = useState(currentTimeValue);
  const [locationMessage, setLocationMessage] = useState("");
  const totalSteps = value === "Valuable or sensitive" ? 6 : 5;
  const reviewStep = totalSteps;
  useEffect(() => {
    if (value !== "Valuable or sensitive" || step !== 5) return;
    const row = document.querySelector<HTMLElement>(".timer-options");
    const selected = row?.querySelector<HTMLElement>(".selected");
    if (row && selected) row.scrollLeft = selected.offsetLeft - row.offsetLeft - 8;
  }, [step, value]);
  const selectRegisteredItem = (item: SensitiveItem) => {
    setItemName(item.name);
    setItemDescription(item.description);
    setValue("Valuable or sensitive");
  };
  const saveLostPhoto = async (file: File, preview: string) => {
    setPhotoPreviewUrl(preview);
    setPhotoError("");
    try {
      setPhotoUrl(await storeReportImage(file));
    } catch (error) {
      setPhotoUrl(null);
      setPhotoError(error instanceof Error ? `${error.message} The preview is not attached yet.` : "The photo could not be stored.");
    }
  };
  const removeLostPhoto = () => {
    if (photoPreviewUrl?.startsWith("blob:")) URL.revokeObjectURL(photoPreviewUrl);
    setPhotoPreviewUrl(null);
    setPhotoUrl(null);
    setPhotoError("");
  };
  const changePriority = (id: number, high: boolean) => setPlaces(places.map((place) => place.id === id ? { ...place, high } : place));
  const removePlace = (id: number) => setPlaces(places.filter((place) => place.id !== id));
  const addManualPlace = () => {
    const name = manualPlace.trim();
    if (!name) return;
    const knownPlace = campusPlaces.find((place) => place.name.toLowerCase() === name.toLowerCase());
    const placeType: PlaceType = knownPlace?.placeType || "building";
    const timeValue = manualTime || currentTimeValue();
    const [hours, minutes] = timeValue.split(":").map(Number);
    const sortMinutes = hours * 60 + minutes;
    const high = !["bus_stop", "outdoor"].includes(placeType);
    setPlaces([...places, {
      id: Date.now(),
      name: `${name}${manualRoom.trim() ? `, ${manualRoom.trim()}` : ""}`,
      time: formatTimelineTime(timeValue),
      sortMinutes,
      source: "Added",
      high,
    }].sort((a, b) => a.sortMinutes - b.sortMinutes));
    setManualPlace("");
    setManualRoom("");
    setLocationMessage("");
  };
  const useCurrentLocation = () => {
    if (!navigator.geolocation) {
      setLocationMessage("Location is unavailable in this browser.");
      return;
    }
    setLocationMessage("Finding your nearest campus place…");
    navigator.geolocation.getCurrentPosition((position) => {
      const { longitude, latitude } = position.coords;
      const nearest = campusPlaces.reduce((closest, place) => {
        const distance = Math.hypot(place.coordinates[0] - longitude, place.coordinates[1] - latitude);
        return distance < closest.distance ? { place, distance } : closest;
      }, { place: campusPlaces[0], distance: Number.POSITIVE_INFINITY });
      setManualPlace(nearest.place.name);
      setLocationMessage(`Using nearest campus place: ${nearest.place.name}.`);
    }, () => {
      setLocationMessage("Location permission was denied. Search for a place or enter one manually.");
    });
  };
  const next = () => {
    setStep(Math.min(totalSteps, step + 1));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const back = () => {
    if (step === 1) go("home");
    else {
      setStep(step - 1);
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };
  const submit = () => {
    const observedAt = localDateTimeToIso(rememberedAt);
    if (submittedId || !itemName.trim() || !category || !observedAt) return;
    const priorityPlace = places.find((place) => place.high);
    const knownPlace = priorityPlace && campusPlaces.find((place) => priorityPlace.name.toLowerCase().includes(place.name.toLowerCase()));
    const location = lostLocation ? roomToReportLocation(lostLocation) : priorityPlace ? {
      campus: knownPlace?.campus ?? "College Ave",
      area: priorityPlace.name,
      source: "timeline" as const,
      placeType: knownPlace?.placeType ?? "building" as PlaceType,
      approximateLabel: `Around ${priorityPlace.name}`,
      approximateCoordinates: knownPlace?.coordinates,
      precise: { label: priorityPlace.name },
    } : null;
    const id = onSubmit({
      clientSubmissionId: submissionKey,
      itemName: itemName.trim(),
      itemDescription: itemDescription.trim(),
      category,
      color: color.trim(),
      observedAt,
      sensitive: value === "Valuable or sensitive",
      photoUrl,
      location,
      visibility: value === "Valuable or sensitive" ? "trusted-only" : "public",
    });
    setSubmittedId(id);
    setPosted(true);
  };

  const possibleMatches = reports
    .filter((report) => report.type === "found" && report.reporterId !== currentUserId && !["returned", "closed"].includes(report.status) && report.visibility !== "private" && report.category === normalizeCategory(category))
    .map(toPublicReport)
    .slice(0, 3);
  if (posted) return <main className="simple-page with-nav"><BackHeader title="Possible matches" onBack={() => setPosted(false)} /><div className="match-heading"><p className="eyebrow">LISTING POSTED · {possibleMatches.length} POSSIBLE {possibleMatches.length === 1 ? "MATCH" : "MATCHES"}</p>{value === "Valuable or sensitive" && <Status>Trusted helpers only</Status>}<h1>{possibleMatches.length ? "Review possible matches" : "Your report is now active"}</h1><p>Suggestions are based on shared catalog data. A match never verifies ownership automatically.</p></div>
    <div className="stack">{possibleMatches.map((report) => <ReportCard report={report} large key={report.id} onClick={() => openReport(report.id)} />)}</div>
    {possibleMatches.length === 0 && <CatalogEmpty icon="search" title="No matches yet" text="Your report remains active and searchable. Check Explore again later." action="View my report" onAction={() => submittedId && openReport(submittedId)} />}
    <div className="tip-card"><Icon name="shield" /><div><strong>Matches are suggestions</strong><p>A listing owner must explicitly review and approve a simulated claim.</p></div></div>
    <Button variant="ghost" onClick={() => go("home")}>Back to home</Button>
    <BottomNav screen="home" go={go} />
  </main>;

  return <main className="simple-page with-bottom lost-flow">
    <BackHeader title="Report a lost item" onBack={back} action={<span className="flow-count">{step} of {totalSteps}</span>} />
    <div className="flow-progress" role="progressbar" aria-label="Lost listing progress" aria-valuemin={1} aria-valuemax={totalSteps} aria-valuenow={step}><span style={{ width: `${step / totalSteps * 100}%` }} /></div>

    {step === 1 && <section className="flow-step">
      <p className="eyebrow">STEP 1 · BASIC INFO</p>
      <h1>What did you lose?</h1>
      <p className="subtext">Start with the details someone would notice first.</p>
      <div className="registered-prefill"><div className="prefill-heading"><span><Icon name="lock" size={16} /></span><div><strong>Pick from My sensitive items</strong><small>Prefill details from a private saved item</small></div></div><div>{sensitiveItems.map((item) => <button key={item.id} onClick={() => selectRegisteredItem(item)}>{item.name}</button>)}</div></div>
      <div className="flow-form">
        <label className="result-field"><span>Item name</span><input value={itemName} onChange={(event) => setItemName(event.target.value)} /></label>
        <label className="textarea-field"><span>Private description</span><textarea value={itemDescription} onChange={(event) => setItemDescription(event.target.value)} /></label>
        <label className="result-field"><span>Category</span><select value={category} onChange={(event) => setCategory(event.target.value)}><option value="" disabled>Choose a category</option>{reportCategories.map((option) => <option key={option}>{option}</option>)}</select></label>
        <label className="result-field"><span>Color</span><input value={color} onChange={(event) => setColor(event.target.value)} /></label>
        <label className="result-field"><span>When did you last have it?</span><input type="datetime-local" max={localDateTimeValue()} value={rememberedAt} onChange={(event) => setRememberedAt(event.target.value)} /></label>
        {photoPreviewUrl ? <div className="lost-photo-preview"><img src={photoPreviewUrl} alt="Uploaded lost item" /><div><strong>Photo attached</strong><small>Stored locally on this device</small></div><button type="button" className="text-button" onClick={removeLostPhoto}>Remove</button></div> : <PhotoButtons cameraLabel="Take photo" uploadLabel="Choose photo" onPhoto={saveLostPhoto} onError={setPhotoError} />}
        {photoError && <div className="camera-error" role="alert">{photoError}</div>}
      </div>
    </section>}

    {step === 2 && <section className="flow-step">
      <p className="eyebrow">STEP 2 · ITEM VALUE</p>
      <h1>How valuable or sensitive is this?</h1>
      <p className="subtext">This helps us choose the right privacy and safety settings.</p>
      <div className="value-options">
        {[
          ["Everyday item", "Bottle, notebook, umbrella, clothing"],
          ["Valuable or sensitive", "ID, wallet, keys, laptop, phone, AirPods, jewelry"],
        ].map(([name, detail], index) => <button aria-pressed={value === name} className={value === name ? "selected" : ""} onClick={() => setValue(name)} key={name}>
          <span className="value-icon"><Icon name={index === 1 ? "shield" : "bag"} /></span>
          <span><strong>{name}</strong><small>{detail}</small></span>
          <span className="radio-dot">{value === name && <span />}</span>
        </button>)}
      </div>
      {value === "Valuable or sensitive" && <div className="sensitive-note"><Icon name="shield" /><div><strong>Sensitive listings stay restricted.</strong><p>This local demo does not automatically release them or their identifying details.</p></div></div>}
    </section>}

    {step === 3 && <section className="flow-step">
      <p className="eyebrow">STEP 3 · FIND THE PLACE</p>
      <h1>How do you want to find where you lost it?</h1>
      <p className="subtext">Choose the option that best fits what you remember.</p>
      <div className="method-cards">
        <button aria-pressed={method === "retrace"} className={method === "retrace" ? "selected" : ""} onClick={() => setMethod("retrace")}><span className="method-icon"><Icon name="map" size={27} /></span><span><strong>Retrace my steps</strong><small>Build a timeline from today's places and classes</small></span><span className="radio-dot">{method === "retrace" && <span />}</span></button>
        <button aria-pressed={method === "room"} className={method === "room" ? "selected" : ""} onClick={() => setMethod("room")}><span className="method-icon"><Icon name="camera" size={27} /></span><span><strong>I know the room</strong><small>Scan the room, read the placard, or pick it</small></span><span className="radio-dot">{method === "room" && <span />}</span></button>
      </div>
      {method === "retrace" && <div className="method-panel">
        <div className="source-note"><Icon name="shield" size={17} /><p>No device history or class schedule is connected. Add only the places you choose below; this prototype does not read your real location history.</p></div>
        <div className="place-timeline">
          {places.map((place) => <div key={place.id}><span className="place-dot" /><time>{place.time}</time><div><strong>{place.name}</strong><small>{place.source}</small></div><button onClick={() => removePlace(place.id)} aria-label={`Remove ${place.name}`}><Icon name="x" size={17} /></button></div>)}
        </div>
        <div className="manual-place-form">
          <label className="result-field"><span>Place</span><input list="campus-place-suggestions" value={manualPlace} onChange={(event) => setManualPlace(event.target.value)} placeholder="Search or enter a campus place" /></label>
          <datalist id="campus-place-suggestions">{campusPlaces.map((place) => <option value={place.name} key={place.name} />)}</datalist>
          <div className="field-row"><label className="result-field half"><span>Room, optional</span><input value={manualRoom} onChange={(event) => setManualRoom(event.target.value)} /></label><label className="result-field half"><span>Time</span><input type="time" value={manualTime} onChange={(event) => setManualTime(event.target.value)} /></label></div>
          <button className="current-location-button" onClick={useCurrentLocation}><Icon name="map" size={17} /> Use my current location</button>
          {locationMessage && <p className="location-message" role="status">{locationMessage}</p>}
          <Button variant="secondary" disabled={!manualPlace.trim()} onClick={addManualPlace}>Save place</Button>
          {!manualPlace.trim() && <p className="form-hint">Enter a place to save it.</p>}
        </div>
      </div>}
      {method === "room" && <div className="method-panel room-method">
        <LocationPicker context="lost" value={lostLocation} onChange={setLostLocation} />
      </div>}
    </section>}

    {step === 4 && <section className="flow-step">
      <p className="eyebrow">STEP 4 · PRIORITIZE</p>
      <h1>Where do you think you lost it?</h1>
      <p className="subtext">Tap a place to move it. You can also drag between groups.</p>
      <PriorityGroup title="High priority spots" note="Flagged places and stops after you last remember having it" high places={places} onMove={changePriority} />
      <PriorityGroup title="Low priority spots" note="Earlier stops and less likely places" high={false} places={places} onMove={changePriority} />
    </section>}

    {value === "Valuable or sensitive" && step === 5 && <section className="flow-step">
      <p className="eyebrow">STEP 5 · VISIBILITY</p>
      <h1>Sensitive listings stay restricted.</h1>
      <p className="subtext">Automatic expiration is unavailable in this local demo.</p>
      <div className="timer-hero"><span><Icon name="lock" size={27} /></span><div><strong>No automatic public release</strong><p>Your listing remains restricted until you explicitly edit or close it.</p></div></div>
      <div className="timer-preview"><Status>Trusted helpers only</Status><p>The demo will never reveal sensitive details when time passes.</p></div>
    </section>}

    {step === reviewStep && <section className="flow-step">
      <p className="eyebrow">STEP {reviewStep} · REVIEW</p>
      <h1>Ready to post?</h1>
      <p className="subtext">Check your listing. You can edit it anytime.</p>
      <article className="review-card">
        <div className="review-item"><div className="review-thumb">{photoPreviewUrl ? <img src={photoPreviewUrl} alt="" /> : <span className="detail-category-icon">{categoryIcon(normalizeCategory(category))}</span>}</div><div><span className="review-badge">{value}</span><h2>{itemName}</h2><p>{color} · {category}</p></div></div>
        <div className="review-row"><span><Icon name="clock" size={18} /> Last remembered</span><strong>{new Date(rememberedAt).toLocaleString()}</strong></div>
        <div className="review-row"><span><Icon name="map" size={18} /> Search method</span><strong>{method === "room" ? (lostLocation ? `${formatLocation(lostLocation)} · ${sourceLabel[lostLocation.source]}` : "Known room") : "Retraced steps"}</strong></div>
        {value === "Valuable or sensitive" && <div className="review-row"><span><Icon name="lock" size={18} /> Visibility</span><strong>Trusted helpers only · no auto-release</strong></div>}
      </article>
      <section className="review-priority"><h2>High priority spots</h2>{places.filter((place) => place.high).map((place) => <div key={place.id}><span><Icon name="map" size={16} /></span><p><strong>{place.name}</strong><small>{place.time}</small></p></div>)}</section>
      <div className="safe-card"><Icon name="shield" /><p><strong>Your exact timeline stays private.</strong><br />Finders only see the details needed to identify a possible match.</p></div>
    </section>}

    <div className="bottom-action">
      {step === 1 && !category && <p className="action-hint">Choose a category to continue.</p>}
      {step === 3 && !method && <p className="action-hint">Choose an option to continue.</p>}
      {step === 3 && method === "room" && !lostLocation && <p className="action-hint">Confirm a room to continue.</p>}
      {step < totalSteps ? <Button onClick={next} disabled={step === 1 && !category || step === 3 && (!method || (method === "room" && !lostLocation))}>Continue <Icon name="chevron" size={18} /></Button> : <Button disabled={!itemName.trim() || !category || !localDateTimeToIso(rememberedAt) || Boolean(submittedId)} onClick={submit}><Icon name="search" size={19} /> Post lost listing</Button>}
    </div>
  </main>;
}

function PriorityGroup({ title, note, high, places, onMove }: { title: string; note: string; high: boolean; places: TimelinePlace[]; onMove: (id: number, high: boolean) => void }) {
  const visible = places.filter((place) => place.high === high);
  return <section className={`priority-group ${high ? "high" : "low"}`} onDragOver={(event) => event.preventDefault()} onDrop={(event) => onMove(Number(event.dataTransfer.getData("placeId")), high)}>
    <div className="priority-heading"><div><h2>{title}</h2><p>{note}</p></div><span>{visible.length}</span></div>
    <div className="priority-list">
      {visible.map((place) => <button key={place.id} draggable onDragStart={(event) => event.dataTransfer.setData("placeId", String(place.id))} onClick={() => onMove(place.id, !high)}>
        <span className="drag-handle">⠿</span><span className="priority-pin"><Icon name="map" size={17} /></span><span><strong>{place.name}</strong><small>{place.time} · {place.source}</small></span><Icon name="chevron" size={17} />
      </button>)}
      {visible.length === 0 && <p className="drop-empty">Drag or tap a place to move it here</p>}
    </div>
  </section>;
}

function Items({ openReport }: { openReport: (id: string) => void }) {
  const { reports, claims, currentUserId } = useReports();
  const [tab, setTab] = useState("Found by me");
  const claimedIds = new Set(claims.filter((claim) => claim.claimantId === currentUserId).map((claim) => claim.reportId));
  const lists: Record<string, ItemReport[]> = {
    "Found by me": reports.filter((report) => report.reporterId === currentUserId && report.type === "found" && !["returned", "closed"].includes(report.status)),
    "Lost by me": reports.filter((report) => report.reporterId === currentUserId && report.type === "lost" && !["returned", "closed"].includes(report.status)),
    "My claims": reports.filter((report) => claimedIds.has(report.id)),
    "History": reports.filter((report) => report.reporterId === currentUserId && ["returned", "closed"].includes(report.status)),
  };
  return <main className="tab-page"><header className="title-header"><h1>My items</h1><p>Track finds, reports, and claims</p></header>
    <div className="tabs">{Object.keys(lists).map((name) => <button aria-pressed={tab === name} className={tab === name ? "active" : ""} onClick={() => setTab(name)} key={name}>{name}</button>)}</div>
    <div className="stack item-list">{lists[tab].map((report) => <ReportCard report={report} large key={report.id} onClick={() => openReport(report.id)} />)}</div>
    {lists[tab].length === 0 && <div className="empty-note"><Icon name="bag" /><p>No reports in this section.</p></div>}
  </main>;
}

function CampusMapScreen({ go, openReport, reports, firstName, lastName, dark }: { go: (screen: Screen) => void; openReport: (id: string) => void; reports: PublicItemReport[]; firstName: string; lastName: string; dark: boolean }) {
  const [campus, setCampus] = useState<CampusName>("College Ave");
  const initials = `${firstLetter(firstName)}${firstLetter(lastName)}`;
  const location = useUserLocation();
  const mapListings = useMemo<MapListing[]>(() => reports
    .filter((report) => report.location?.approximateCoordinates && report.status !== "closed")
    .map((report) => ({
      id: report.id,
      title: report.itemName,
      type: report.type,
      status: report.status === "returned" ? "returned" : "active",
      placeType: report.location!.placeType,
      coordinates: report.location!.approximateCoordinates!,
      hoursAgo: Math.max(0, Math.floor((Date.now() - new Date(report.observedAt).getTime()) / 3_600_000)),
      weight: report.location!.placeType === "classroom" ? 1 : ["building", "library", "dining"].includes(report.location!.placeType) ? .8 : .4,
    })), [reports]);
  // "Near you" is measured from the phone when location is on and it's on campus; otherwise from the chosen campus.
  const nearestCampus = location.position ? nearestCampusTo(location.position, campusCenters) : null;
  const onCampus = Boolean(nearestCampus && nearestCampus.meters <= OFF_CAMPUS_METERS);
  const [originLng, originLat] = onCampus ? location.position! : campusViews[campus].center;
  const near = useMemo(() => reportsNear(reports, [originLng, originLat]), [reports, originLng, originLat]);
  const lostCount = near.filter(({ report }) => report.type === "lost").length;
  const foundCount = near.length - lostCount;
  const label = onCampus ? "near you" : `near ${campus}`;
  const note = onCampus ? `within a ${walkMinutes(NEAR_RADIUS_METERS)} min walk`
    : location.status === "on" ? `You're off campus, so this shows ${campus}`
    : location.status === "asking" ? "Finding your location…"
    : location.status === "denied" ? "Location is off for this site"
    : location.status === "unavailable" ? "Your location isn't available"
    : `within a ${walkMinutes(NEAR_RADIUS_METERS)} min walk of campus center`;
  return <main className="tab-page map-page">
    <header className="title-header map-title"><div><h1>Campus map</h1><p>Approximate activity areas · includes labeled demo samples</p></div><button className="map-profile" aria-label="Open profile" onClick={() => go("profile")}>{initials || <Icon name="user" size={18} />}</button></header>
    <div className="campus-filter" aria-label="Choose campus">{(Object.keys(campusViews) as CampusName[]).map((name) => <button aria-pressed={campus === name} className={campus === name ? "active" : ""} onClick={() => setCampus(name)} key={name}>{name}</button>)}</div>
    <CampusMap campus={campus} dark={dark} listings={mapListings} onSelectReport={openReport} />
    <div className="map-summary near-you" aria-live="polite">
      <span className="near-you-count"><b key={near.length} className="count-bump">{near.length}</b></span>
      <p><strong>{near.length === 1 ? "open item" : "open items"} {label}</strong><small>{near.length ? `${lostCount} lost · ${foundCount} found · ` : ""}{note}</small>
        {!onCampus && location.status !== "on" && location.status !== "asking" && <button type="button" className="near-you-action" onClick={location.enable}><Icon name="locate" size={14} />{location.status === "off" ? "Use my location" : "Try again"}</button>}</p>
    </div>
    <section className="section nearby-items">
      <div className="section-heading"><h2>{onCampus ? "Nearest to you" : "Nearest items"}</h2><button onClick={() => go("lost")}>Refine search</button></div>
      {near.slice(0, 3).map(({ report, meters }) => <button className="map-result-card" onClick={() => openReport(report.id)} key={report.id}><span className="map-result-icon">{categoryIcon(report.category)}</span><span><strong>{report.itemName}</strong><small>{relativeTime(report.observedAt)} · {report.location?.approximateLabel ?? report.category}</small><em>{walkMinutes(meters)} min walk</em></span><span className={`distance ${report.type}`}>{report.type === "lost" ? "Lost" : "Found"}</span></button>)}
      {near.length === 0 && <CatalogEmpty icon="map" title="Nothing open nearby" text={`No open lost or found items within a ${walkMinutes(NEAR_RADIUS_METERS)} min walk. Try another campus or browse everything.`} action="Browse all items" onAction={() => go("explore")} />}
    </section>
    <div className="tip-card"><Icon name="shield" /><div><strong>Locations are approximate</strong><p>The map uses broad activity areas to protect student privacy.</p></div></div>
  </main>;
}

function Profile({ go, email, firstName, lastName, theme, setTheme, demo, setDemo, notifications, setNotifications, sensitiveItems, addSensitiveItem, deleteSensitiveItem, homeCampus, setHomeCampus }: {
  go: (screen: Screen) => void;
  email: string;
  firstName: string;
  lastName: string;
  theme: ThemePreference;
  setTheme: (value: ThemePreference) => void;
  demo: boolean;
  setDemo: (value: boolean) => void;
  notifications: boolean;
  setNotifications: (value: boolean) => void;
  sensitiveItems: SensitiveItem[];
  addSensitiveItem: (item: Omit<SensitiveItem, "id">) => void;
  deleteSensitiveItem: (id: string) => void;
  homeCampus: string;
  setHomeCampus: (value: string) => void;
}) {
  const { currentUserId, switchUser, users } = useReports();
  const [addingItem, setAddingItem] = useState(false);
  const [registerPhotoAdded, setRegisterPhotoAdded] = useState(false);
  const [registerName, setRegisterName] = useState("");
  const [registerDescription, setRegisterDescription] = useState("");
  const [registerSerial, setRegisterSerial] = useState("");
  const campuses = ["College Avenue", "Busch", "Livingston", "Cook/Douglass"];
  const initials = `${firstName[0] || ""}${lastName[0] || ""}`.toUpperCase();
  const saveSensitiveItem = () => {
    if (!registerName.trim()) return;
    addSensitiveItem({
      name: registerName.trim(),
      description: registerDescription.trim(),
      serial: registerSerial.trim(),
      photoAdded: registerPhotoAdded,
    });
    setRegisterName("");
    setRegisterDescription("");
    setRegisterSerial("");
    setRegisterPhotoAdded(false);
    setAddingItem(false);
  };
  return <main className="tab-page"><header className="title-header"><h1>Profile</h1><p>Privacy, preferences, and account</p></header>
    <section className="profile-card"><span className="profile-avatar">{initials}</span><div><h2>{firstName} {lastName}</h2><p>{email}</p><span>Demo account · email not verified</span></div></section>
    <p className="settings-label">DEMO PERSONA</p><div className="settings-card persona-switcher">{users.map((user) => <button aria-pressed={currentUserId === user.id} className={currentUserId === user.id ? "active" : ""} onClick={() => switchUser(user.id)} key={user.id}><span className="setting-icon"><Icon name={currentUserId === user.id ? "check" : "user"} /></span><span><strong>{user.firstName} {user.lastName}{user.id === "demo-maya" ? " (demo owner)" : ""}</strong><small>{user.email}</small></span></button>)}</div>
    <section className="reputation-card">
      <span className="reputation-shield"><Icon name="shield" size={25} /></span><div className="reputation-copy"><p className="eyebrow">DEMO ROLE PREVIEW</p><h2>Reputation unavailable</h2><p className="demo-caption">No reputation score, return history, or trusted-helper status has been verified.</p></div>
    </section>

    <div className="sensitive-section-heading"><div><h2>My sensitive items</h2><p>Register important items before they go missing.</p></div><button aria-label={addingItem ? "Close sensitive item form" : "Register a sensitive item"} onClick={() => setAddingItem(!addingItem)}><Icon name={addingItem ? "x" : "plus"} size={17} /></button></div>
    <div className="private-note"><Icon name="lock" size={17} /><p><strong>Private.</strong> Used only to help verify your claim if this item is found.</p></div>
    <div className="sensitive-items">
      {sensitiveItems.map((item) => <article key={item.id}><span className="registered-photo">{item.photoAdded ? "▰" : "⌁"}</span><div><strong>{item.name}</strong><small>{item.serial ? "Serial saved" : "No serial number"}</small><p>{item.description || "No private description"}</p></div><button className="delete-sensitive-item" aria-label={`Delete ${item.name}`} onClick={() => deleteSensitiveItem(item.id)}><Icon name="x" size={16} /></button></article>)}
    </div>
    {addingItem && <section className="register-item-form">
      <h3>Register a sensitive item</h3>
      <button className="register-photo" onClick={() => setRegisterPhotoAdded(!registerPhotoAdded)}><Icon name={registerPhotoAdded ? "check" : "camera"} /><span><strong>{registerPhotoAdded ? "Sample photo added" : "Add a photo"}</strong><small>Tap to use a sample</small></span></button>
      <label className="result-field"><span>Item name</span><input value={registerName} onChange={(event) => setRegisterName(event.target.value)} /></label>
      <label className="textarea-field"><span>Private description</span><textarea value={registerDescription} onChange={(event) => setRegisterDescription(event.target.value)} /></label>
      <label className="result-field"><span>Serial number, optional</span><input value={registerSerial} onChange={(event) => setRegisterSerial(event.target.value)} placeholder="Enter serial number" /></label>
      {!registerName.trim() && <p className="form-hint">Enter an item name to save.</p>}
      <Button disabled={!registerName.trim()} onClick={saveSensitiveItem}>Save private item</Button>
    </section>}
    <p className="settings-label">MY ACTIVITY</p><div className="settings-card"><button onClick={() => go("items")}><span className="setting-icon"><Icon name="bag" /></span><span><strong>My items</strong><small>Finds, lost listings, and claims</small></span><Icon name="chevron" size={18} /></button></div>
    <p className="settings-label">CAMPUS</p><div className="settings-card"><button onClick={() => setHomeCampus(campuses[(campuses.indexOf(homeCampus) + 1) % campuses.length])}><span className="setting-icon"><Icon name="map" /></span><span><strong>Home campus</strong><small>{homeCampus}</small></span><Icon name="chevron" size={18} /></button></div>
    <p className="settings-label">PREFERENCES</p><div className="settings-card toggles"><Toggle on={notifications} setOn={setNotifications} label="Notifications" icon={<span className="setting-icon"><Icon name="bell" /></span>} /><div className="theme-setting"><span className="setting-icon"><Icon name="moon" /></span><div><strong>Theme</strong><div className="theme-control">{(["system", "light", "dark"] as ThemePreference[]).map((option) => <button className={theme === option ? "active" : ""} aria-pressed={theme === option} onClick={() => setTheme(option)} key={option}>{option[0].toUpperCase() + option.slice(1)}</button>)}</div></div></div><Toggle on={demo} setOn={setDemo} label="Demo mode" icon={<span className="setting-icon"><Icon name="settings" /></span>} /></div>
    <p className="demo-caption">Demo mode loads sample items and keeps every flow available offline.</p>
    <button className="signout" onClick={() => { try { localStorage.removeItem(SIGNED_IN_KEY); } catch { /* storage unavailable */ } go("signin"); }}><Icon name="logout" /> Sign out</button>
    <p className="project-note">Where RU? is an independent student project.<br />Not affiliated with or endorsed by Rutgers University.</p>
  </main>;
}

/** Pops up new notifications for this phone's persona on any screen (they arrive through demo sync). */
function NotificationToast({ onOpen }: { onOpen: (reportId: string) => void }) {
  const { notifications, currentUserId, markNotificationRead } = useReports();
  const [shown, setShown] = useState<{ id: string; reportId: string; title: string; body: string } | null>(null);
  const seen = useRef(new Set<string>());
  const opened = useRef(false);
  const lastUser = useRef(currentUserId);
  useEffect(() => {
    // Alerts already there when the app opens count as seen. After that, a new unread alert for
    // this persona pops up. Switching persona (one phone playing both people) pops up that
    // persona's latest alert from the last 10 minutes, so the story works on a single phone.
    if (!opened.current) {
      notifications.forEach((notification) => seen.current.add(notification.id));
      opened.current = true;
      return;
    }
    const switched = lastUser.current !== currentUserId;
    lastUser.current = currentUserId;
    const mine = notifications.filter((notification) => notification.userId === currentUserId && !notification.read);
    const fresh = mine.find((notification) => !seen.current.has(notification.id) && (!switched || Date.now() - new Date(notification.createdAt).getTime() < 10 * 60_000));
    mine.forEach((notification) => seen.current.add(notification.id));
    if (!fresh) return;
    setShown({ id: fresh.id, reportId: fresh.reportId, title: fresh.title, body: fresh.body });
    try { navigator.vibrate?.(200); } catch { /* not supported */ }
  }, [notifications, currentUserId]);
  useEffect(() => {
    if (!shown) return;
    const timer = window.setTimeout(() => setShown(null), 8000);
    return () => window.clearTimeout(timer);
  }, [shown]);
  if (!shown) return null;
  return <button type="button" className="notification-toast" role="alert" onClick={() => { markNotificationRead(shown.id); onOpen(shown.reportId); setShown(null); }}>
    <span className="toast-icon"><Icon name="bell" size={20} /></span>
    <span className="toast-copy"><strong>{shown.title}</strong><small>{shown.body}</small></span>
    <Icon name="chevron" size={18} />
  </button>;
}

function BottomNav({ screen, go }: { screen: Screen; go: (screen: Screen) => void }) {
  const items: [IconName, string, Screen][] = [["home", "Home", "home"], ["search", "Explore", "explore"], ["map", "Map", "map"], ["user", "Profile", "profile"]];
  const activeScreen = screen === "items" ? "profile" : screen === "finderStatus" ? "home" : screen;
  return <nav className="bottom-nav" aria-label="Primary navigation">{items.map(([icon, label, target]) => <button type="button" aria-current={activeScreen === target ? "page" : undefined} className={activeScreen === target ? "active" : ""} onClick={() => go(target)} key={label}><span><Icon name={icon} size={22} /></span><small>{label}</small></button>)}</nav>;
}

function nameFromEmail(email: string) {
  const match = email.match(/^([a-z0-9]+)\.([a-z0-9]+)@rutgers\.edu$/i);
  const format = (value: string) => {
    const letters = value.replace(/\d/g, "").toLowerCase();
    return letters ? letters[0].toUpperCase() + letters.slice(1) : "";
  };
  return match ? { first: format(match[1]), last: format(match[2]) } : { first: "", last: "" };
}

// Remembers that this phone finished signing in, so a refresh during a demo returns to Home.
const SIGNED_IN_KEY = "where-ru.signed-in";
function rememberSignedIn() {
  try { localStorage.setItem(SIGNED_IN_KEY, "1"); } catch { /* storage unavailable: sign in again after a refresh */ }
}
function wasSignedIn() {
  try { return localStorage.getItem(SIGNED_IN_KEY) === "1"; } catch { return false; }
}

const initialSensitiveItems: SensitiveItem[] = [
  { id: "demo-laptop", name: "Demo laptop", description: "Fictional sample item for form prefilling", serial: "", photoAdded: false },
  { id: "demo-earbuds", name: "Demo earbuds", description: "Fictional sample item for form prefilling", serial: "", photoAdded: false },
];

export default function App() {
  const { reports, claims, publicReports, currentUserId, currentUser, users, updatePrimaryUser, createReport, updateReport, createClaim, updateClaim, notifyUser } = useReports();
  const [screen, setScreen] = useState<Screen>("signin");
  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [theme, setTheme] = useState<ThemePreference>("system");
  const [systemDark, setSystemDark] = useState(() => typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  const [foundReport, setFoundReportState] = useState<FoundReport>(emptyFoundReport);
  const [foundSubmissionKey, setFoundSubmissionKey] = useState(() => `found-${Date.now()}`);
  const [foundSubmissionId, setFoundSubmissionId] = useState<string | null>(null);
  const [selectedReportId, setSelectedReportId] = useState<string | null>("report-bottle-found");
  const [detailReturnScreen, setDetailReturnScreen] = useState<Screen>("explore");
  const [exploreState, setExploreState] = useState<ExploreState>(initialExploreState);
  const setFoundReport = (update: (current: FoundReport) => FoundReport) => setFoundReportState(update);
  const [demo, setDemo] = useState(true);
  const [notifications, setNotifications] = useState(true);
  const [sensitiveItems, setSensitiveItems] = useState<SensitiveItem[]>(initialSensitiveItems);
  const [homeCampus, setHomeCampus] = useState("College Avenue");
  const dark = theme === "dark" || (theme === "system" && systemDark);
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const updateSystemTheme = (event: MediaQueryListEvent) => setSystemDark(event.matches);
    setSystemDark(media.matches);
    media.addEventListener("change", updateSystemTheme);
    return () => media.removeEventListener("change", updateSystemTheme);
  }, []);
  const addSensitiveItem = (item: Omit<SensitiveItem, "id">) => {
    setSensitiveItems((current) => [...current, { ...item, id: `sensitive-${Date.now()}` }]);
  };
  const deleteSensitiveItem = (id: string) => {
    setSensitiveItems((current) => current.filter((item) => item.id !== id));
  };
  const go = (next: Screen) => {
    if (next === "capture" && !["locate", "confirm"].includes(screen)) {
      setFoundReportState(emptyFoundReport);
      setFoundSubmissionId(null);
      setFoundSubmissionKey(`found-${Date.now()}-${Math.random()}`);
      api.startNewFoundReport();
    }
    setScreen(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const openReport = (id: string) => {
    setDetailReturnScreen(screen);
    if (screen === "explore") setExploreState((current) => ({ ...current, scrollY: window.scrollY }));
    setSelectedReportId(id);
    setScreen("detail");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const selectedReport = reports.find((report) => report.id === selectedReportId);
  const submitFoundReport = () => {
    if (foundSubmissionId) {
      setSelectedReportId(foundSubmissionId);
      setScreen("finderStatus");
      return;
    }
    const observedAt = localDateTimeToIso(foundReport.foundAt);
    if (!foundReport.title.trim() || !foundReport.location || !observedAt) return;
    const sensitive = ["Wallets/IDs", "Keys", "Electronics"].includes(normalizeCategory(foundReport.category));
    const report = createReport({
      type: "found",
      itemName: foundReport.title.trim(),
      category: normalizeCategory(foundReport.category),
      color: foundReport.color.trim(),
      publicDescription: foundReport.hideDetails ? plainSummary(foundReport.color, foundReport.title, "found") : foundReport.description.trim(),
      privateDetails: [foundReport.hideDetails ? foundReport.description.trim() : "", foundReport.cardName ? `Name on the card: ${foundReport.cardName}` : ""].filter(Boolean).join(" · ") || undefined,
      photoUrl: foundReport.photoUrl,
      location: roomToReportLocation(foundReport.location),
      observedAt,
      status: foundReport.relatedLostReportId ? "possible_match" : "active",
      visibility: sensitive ? "trusted-only" : "public",
      sensitive,
      sample: foundReport.sample,
      clientSubmissionId: foundSubmissionKey,
      relatedLostReportId: foundReport.relatedLostReportId,
    });
    // A found ID card: privately notify its owner if they use Where RU? (first and last name must match).
    const cardWords = foundReport.cardWords ?? [];
    if (cardWords.length >= 2) {
      const owner = users.find((user) => user.id !== currentUserId && nameOnCard(cardWords, user.firstName, user.lastName));
      if (owner) {
        notifyUser(owner.id, report.id, "Your ID may have been found", "A student ID with your name was turned in. Open the listing to verify it's yours and arrange a safe return.");
        notifyUser(currentUserId, report.id, "Owner notified privately", "The name on this ID matches a Where RU? user. They've been notified; you won't see who they are until they claim it.");
      }
      api.notifyIdOwner(cardWords).catch((error) => console.warn("Backend owner lookup skipped:", error));
    }
    // Teach item recognition from what the finder confirmed (real photos only, never the sample).
    if (foundReport.photoFile && !foundReport.sample) {
      api.sendItemFeedback(foundReport.photoFile, foundReport.title).catch((error) => console.warn("Item feedback skipped:", error));
    }
    // Mirror to the Flask backend (matching engine, cross-device). Best effort: the app keeps working offline.
    api.publishFoundReport({
      title: report.itemName,
      description: report.publicDescription,
      private_description: report.privateDetails ?? "",
      category: api.toApiCategory(foundReport.category || foundReport.title),
      campus: report.location?.campus,
      location: report.location?.precise?.label ?? report.location?.approximateLabel ?? "",
    }).catch((error) => console.warn("Backend publish skipped:", error));
    setFoundSubmissionId(report.id);
    setSelectedReportId(report.id);
    setScreen("finderStatus");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const submitLostReport = (submission: LostSubmission) => {
    const report = createReport({
      type: "lost",
      itemName: submission.itemName,
      category: normalizeCategory(submission.category),
      color: submission.color,
      publicDescription: plainSummary(submission.color, submission.itemName, "lost"),
      privateDetails: submission.itemDescription || undefined,
      photoUrl: submission.photoUrl,
      location: submission.location,
      observedAt: submission.observedAt,
      status: "active",
      visibility: submission.visibility,
      sensitive: submission.sensitive,
      sample: false,
      clientSubmissionId: submission.clientSubmissionId,
    });
    api.createLostReport({
      title: report.itemName,
      description: report.publicDescription,
      private_description: report.privateDetails ?? "",
      category: api.toApiCategory(submission.category || submission.itemName),
      campus: report.location?.campus,
      location: report.location?.precise?.label ?? report.location?.approximateLabel ?? "",
      visibility: submission.sensitive ? "PRIVATE" : "PUBLIC",
    }).catch((error) => console.warn("Backend lost report skipped:", error));
    setSelectedReportId(report.id);
    return report.id;
  };
  const startFoundFromLost = (report: PublicItemReport) => {
    setFoundReportState({
      ...emptyFoundReport,
      title: report.itemName,
      category: report.category,
      color: report.color,
      description: "",
      foundAt: localDateTimeValue(),
      relatedLostReportId: report.id,
    });
    setFoundSubmissionId(null);
    setFoundSubmissionKey(`found-${Date.now()}-${report.id}`);
    setScreen("capture");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const activeClaim = claims.find((claim) => claim.reportId === selectedReportId && ["approved", "handoff", "returned"].includes(claim.status));
  const completeEmailVerification = () => {
    api.signIn(email).catch((error) => console.warn("Backend sign-in skipped; demo mode continues", error));
    const names = nameFromEmail(email);
    setFirstName(names.first);
    setLastName(names.last);
    go("name");
  };
  const devSkipSignIn = () => {
    // Signs in as this phone's demo persona (?as=jordan / ?as=maya), straight to Home.
    setEmail(currentUser.email);
    setFirstName(currentUser.firstName);
    setLastName(currentUser.lastName);
    api.signIn(currentUser.email, `${currentUser.firstName} ${currentUser.lastName}`.trim()).catch(() => {});
    rememberSignedIn();
    go("home");
  };
  useEffect(() => {
    // After a refresh, pick up where this phone left off instead of the sign-in screen. Phones in
    // the desktop showcase open straight to Home as their persona.
    if (wasSignedIn() || embedded) devSkipSignIn();
  }, []);
  const completeProfile = () => {
    updatePrimaryUser({ firstName: firstName.trim(), lastName: lastName.trim(), email: email.trim() });
    api.updateName(`${firstName.trim()} ${lastName.trim()}`.trim()).catch(() => {});
    rememberSignedIn();
    go("home");
  };
  const screens: Record<Screen, ReactNode> = {
    signin: <SignIn go={go} email={email} setEmail={setEmail} onDevSkip={devSkipSignIn} />, code: <CodeScreen go={go} email={email} onVerified={completeEmailVerification} />, name: <NameScreen go={go} firstName={firstName} setFirstName={setFirstName} lastName={lastName} setLastName={setLastName} onContinue={completeProfile} />, home: <Home go={go} openReport={openReport} reports={[...publicReports].sort((a, b) => b.createdAt.localeCompare(a.createdAt))} firstName={currentUser.firstName} lastName={currentUser.lastName} demo={demo} />,
    explore: <Explore go={go} openReport={openReport} state={exploreState} setState={setExploreState} />, detail: <ReportDetail reportId={selectedReportId} go={go} onBack={() => go(detailReturnScreen === "detail" ? "explore" : detailReturnScreen)} startFoundFromLost={startFoundFromLost} />,
    capture: <Capture go={go} report={foundReport} setReport={setFoundReport} />, locate: <Locate go={go} report={foundReport} setReport={setFoundReport} />, confirm: <Confirm go={go} report={foundReport} setReport={setFoundReport} onSubmit={submitFoundReport} />, finderStatus: <FinderStatus go={go} report={selectedReport} claims={claims} onUpdateClaim={updateClaim} />, ownerNotice: <OwnerNotice go={go} report={selectedReport} />,
    ownership: <Ownership go={go} report={selectedReport} claimantId={currentUserId} onSubmit={createClaim} />, handoff: <Handoff go={go} report={selectedReport} claim={activeClaim} onUpdateClaim={updateClaim} />, lost: <Lost go={go} openReport={openReport} onSubmit={submitLostReport} sensitiveItems={sensitiveItems} />, items: <Items openReport={openReport} />,
    map: <CampusMapScreen go={go} openReport={openReport} reports={publicReports} firstName={currentUser.firstName} lastName={currentUser.lastName} dark={dark} />, profile: <Profile go={go} email={currentUser.email} firstName={currentUser.firstName} lastName={currentUser.lastName} theme={theme} setTheme={setTheme} demo={demo} setDemo={setDemo} notifications={notifications} setNotifications={setNotifications} sensitiveItems={sensitiveItems} addSensitiveItem={addSensitiveItem} deleteSensitiveItem={deleteSensitiveItem} homeCampus={homeCampus} setHomeCampus={setHomeCampus} />,
  };
  const navScreens: Screen[] = ["home", "explore", "items", "map", "profile", "finderStatus"];
  return <div className={dark ? "app-root dark" : "app-root"}><div className="app-shell">{!["signin", "code", "name"].includes(screen) && <NotificationToast onOpen={openReport} />}{screens[screen]}{navScreens.includes(screen) && <BottomNav screen={screen} go={go} />}</div></div>;
}
