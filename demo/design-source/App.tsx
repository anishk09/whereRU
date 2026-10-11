import { useEffect, useState, type ChangeEvent, type ReactNode } from "react";
import CampusMap, { campusViews, type CampusName } from "./CampusMap";
import { campusPlaces, type ListingProperties, type PlaceType } from "./mapData";
import { BrandIcon, Button, Icon, Wordmark, type IconName } from "./ui";
import LocationPicker, { DemoTag, LocationSummary, PhotoButtons } from "./LocationPicker";
import { activeRecognizer, formatLocation, shortLocation, sourceLabel, type RoomLocation } from "./roomRecognition";

type Screen =
  | "signin"
  | "code"
  | "name"
  | "home"
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
  "Pinging": "blue",
  "Claim pending": "amber",
  "Verified": "green",
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

function SignIn({ go, email, setEmail }: { go: (screen: Screen) => void; email: string; setEmail: (email: string) => void }) {
  const [error, setError] = useState("");
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
      <Brand size="welcome" subtitle />
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
  return <main className="simple-page auth-code">
    <BackHeader title="" onBack={() => go("signin")} />
    <div className="code-icon"><Icon name="bell" size={30} /></div>
    <p className="eyebrow">Check your email</p>
    <h1>Enter your 6-digit code</h1>
    <p className="subtext">We sent a one-time code to {email}. Any six digits work in this demo.</p>
    <input className="code-input" inputMode="numeric" autoComplete="one-time-code" aria-label="Six digit verification code" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} placeholder="000000" autoFocus />
    {code.length !== 6 && <p className="form-hint">Enter the 6-digit code to continue.</p>}
    <Button disabled={code.length !== 6} onClick={onVerified}>Verify code</Button>
    <button className="text-link" aria-live="polite" onClick={() => setResent(true)}>{resent ? "Email code resent" : "Resend code to email"}</button>
  </main>;
}

function NameScreen({ go, firstName, setFirstName, lastName, setLastName }: {
  go: (screen: Screen) => void;
  firstName: string;
  setFirstName: (name: string) => void;
  lastName: string;
  setLastName: (name: string) => void;
}) {
  const hasFirstLetter = /\p{L}/u.test(firstName);
  const hasLastName = Boolean(lastName.trim());
  return <main className="simple-page with-bottom name-page">
    <BackHeader title="Your name" onBack={() => go("code")} />
    <div className="verify-heading"><span><Icon name="user" size={27} /></span><p className="eyebrow">ONE LAST STEP</p><h1>What should we call you?</h1><p>Add your name so other students know who they are meeting.</p></div>
    <div className="flow-form">
      <label className="result-field"><span>First name</span><input autoComplete="given-name" value={firstName} onChange={(event) => setFirstName(event.target.value)} /></label>
      <label className="result-field"><span>Last name</span><input autoComplete="family-name" value={lastName} onChange={(event) => setLastName(event.target.value)} /></label>
    </div>
    <div className="safe-card"><Icon name="shield" /><p><strong>Your identity stays private.</strong><br />Only your first name is shown to other users.</p></div>
    <div className="bottom-action">{(!hasFirstLetter || !hasLastName) && <p className="action-hint">{hasFirstLetter ? "Enter your last name" : "Enter your first name"}</p>}<Button disabled={!hasFirstLetter || !hasLastName} onClick={() => go("home")}>Continue <Icon name="chevron" size={18} /></Button></div>
  </main>;
}

const activeItems = [
  { emoji: "◒", title: "Blue water bottle", place: "Hardenbergh Hall · Today, 11:46 AM", status: "Claim pending" },
  { emoji: "⌁", title: "AirPods case", place: "Academic Resource Center · Yesterday", status: "Pinging" },
];

type ItemData = (typeof activeItems)[number];

function ItemCard({ item, onClick, large = false }: { item: ItemData; onClick?: () => void; large?: boolean }) {
  const content = <><span className="item-thumb">{item.emoji}</span><span className="item-info"><strong>{item.title}</strong><small>{item.place}</small><Status>{item.status}</Status></span>{onClick && <Icon name="chevron" size={19} />}</>;
  return onClick
    ? <button className={`item-card ${large ? "large" : ""}`} onClick={onClick}>{content}</button>
    : <article className={`item-card ${large ? "large" : ""}`}>{content}</article>;
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

function Home({ go, firstName, lastName }: { go: (screen: Screen) => void; firstName: string; lastName: string }) {
  const displayName = firstName.trim();
  const hasName = /\p{L}/u.test(displayName);
  const greeting = greetingForHour(new Date().getHours());
  const greetingText = hasName ? `${greeting}, ${displayName}${greeting === "Up late" ? "?" : ""}` : greeting;
  const initials = hasName ? `${firstLetter(firstName)}${firstLetter(lastName)}` : "";
  return <main className="tab-page">
    <header className="home-header"><Brand /><button className="avatar" aria-label={hasName ? `Open ${displayName}'s profile` : "Open profile"} onClick={() => go("profile")}>{initials || <Icon name="user" size={18} />}</button></header>
    <section className="welcome"><p className="eyebrow">{greetingText}</p><h1>What are we looking for?</h1></section>
    <section className="action-grid">
      <button className="action-card found" onClick={() => go("capture")}><span className="action-icon"><Icon name="camera" size={29} /></span><span><strong>I found<br />something</strong><small>Help it ask Where RU?</small></span><Icon name="chevron" size={18} /></button>
      <button className="action-card lost" onClick={() => go("lost")}><span className="action-icon"><Icon name="search" size={29} /></span><span><strong>I lost<br />something</strong><small>Find your item</small></span><Icon name="chevron" size={18} /></button>
    </section>
    <section className="section priority-requests">
      <div className="section-heading"><div><h2>Priority requests</h2><p>Available to trusted helpers</p></div><span className="reputation-badge"><Icon name="shield" size={12} /> Trusted Helper</span></div>
      <article className="priority-request-card">
        <span className="sensitive-item-icon"><Icon name="lock" /></span>
        <span className="item-info"><span className="sensitive-label">Sensitive listing</span><strong>Black laptop sleeve</strong><small>Last seen near ARC · Limited details</small></span>
        <span className="countdown"><Icon name="clock" size={14} /> 18h left</span>
      </article>
    </section>
    <section className="section">
      <div className="section-heading"><h2>Active items</h2><button onClick={() => go("items")}>See all</button></div>
      <div className="stack">{activeItems.map((item, i) => <ItemCard item={item} key={item.title} onClick={() => go(i === 0 ? "finderStatus" : "map")} />)}</div>
    </section>
    <div className="tip-card"><Icon name="shield" /><div><strong>Your privacy comes first</strong><p>Names are only shared after ownership is verified.</p></div></div>
  </main>;
}

type FoundReport = {
  photoUrl: string | null;
  sample: boolean;
  title: string;
  category: string;
  color: string;
  description: string;
  hideDetails: boolean;
  location: RoomLocation | null;
  foundAt: string;
};

const emptyFoundReport: FoundReport = { photoUrl: null, sample: false, title: "", category: "", color: "", description: "", hideDetails: true, location: null, foundAt: "" };

function nowLabel() {
  return new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" }).format(new Date());
}

function Capture({ go, report, setReport }: { go: (screen: Screen) => void; report: FoundReport; setReport: (update: (current: FoundReport) => FoundReport) => void }) {
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");
  const hasPhoto = Boolean(report.photoUrl) || report.sample;
  const setPhoto = (url: string | null, sample: boolean) => {
    setError("");
    setReport((current) => ({ ...current, photoUrl: url, sample, foundAt: current.foundAt || nowLabel() }));
  };
  const usePhoto = async () => {
    setAnalyzing(true);
    const result = await activeRecognizer.describeItem(null);
    setReport((current) => ({
      ...current,
      title: current.title || result.title,
      category: current.category || result.category,
      color: current.color || result.color,
      description: current.description || result.description,
    }));
    setAnalyzing(false);
    go("locate");
  };
  if (analyzing) return <main className="camera-screen analyzing" aria-live="polite" aria-busy="true">
    <div className="scan-orbit"><Icon name="sparkles" size={34} /></div>
    <h1>Describing the item…</h1><p>Picking out the category, color, and details you can edit next.</p>
    <DemoTag>Demo description</DemoTag>
  </main>;
  return <main className="camera-screen with-bottom">
    <BackHeader title="Found something" onBack={() => go("home")} action={<span className="camera-step">1/3</span>} />
    <div className="capture-copy"><p className="eyebrow">STEP 1 OF 3 · PHOTOGRAPH ITEM</p><h1>Photograph the item</h1><p>Fit the whole item in the frame, in good light.</p></div>
    <div className={`camera-frame ${hasPhoto ? "has-photo" : ""}`}>
      <span className="corner tl" /><span className="corner tr" /><span className="corner bl" /><span className="corner br" />
      {report.photoUrl ? <img className="photo-preview" src={report.photoUrl} alt="Your photo of the found item" /> : <div className={`bottle ${report.sample ? "" : "ghost"}`}><span className="cap" /><span className="bottle-body"><span className="sticker">★</span></span></div>}
      <div className="camera-guide">{hasPhoto ? (report.sample ? "Sample photo" : "Looks good? Use it or retake") : "No photo yet"}</div>
    </div>
    {error && <div className="camera-error" role="alert">{error}</div>}
    <div className="bottom-action camera-actions">
      {hasPhoto ? <div className="photo-buttons">
        <Button onClick={usePhoto}>Use this photo <Icon name="chevron" size={18} /></Button>
        <Button variant="secondary" onClick={() => setPhoto(null, false)}><Icon name="refresh" size={18} /> Retake</Button>
      </div> : <>
        <PhotoButtons cameraLabel="Take photo" onPhoto={(_file, url) => setPhoto(url, false)} onError={setError} />
        <button type="button" className="text-button sample on-dark" onClick={() => setPhoto(null, true)}>Use a sample photo</button>
      </>}
    </div>
  </main>;
}

function Locate({ go, report, setReport }: { go: (screen: Screen) => void; report: FoundReport; setReport: (update: (current: FoundReport) => FoundReport) => void }) {
  return <main className="simple-page with-bottom">
    <BackHeader title="Identify location" onBack={() => go("capture")} action={<span className="flow-count">2 of 3</span>} />
    <p className="eyebrow">STEP 2 OF 3 · SCAN CLASSROOM</p>
    <h1 className="flow-title">Where did you find it?</h1>
    <p className="subtext">Scan the room to identify it. If that doesn't work, scan the door placard or choose the room.</p>
    <LocationPicker context="found" value={report.location} onChange={(location) => setReport((current) => ({ ...current, location }))} />
    <div className="bottom-action">
      {!report.location && <p className="action-hint">Confirm a room to continue.</p>}
      <Button disabled={!report.location} onClick={() => go("confirm")}>Continue <Icon name="chevron" size={18} /></Button>
    </div>
  </main>;
}

function Confirm({ go, report, setReport }: { go: (screen: Screen) => void; report: FoundReport; setReport: (update: (current: FoundReport) => FoundReport) => void }) {
  const set = (key: "title" | "category" | "color" | "description") => (event: ChangeEvent<HTMLInputElement>) => setReport((current) => ({ ...current, [key]: event.target.value }));
  const location = report.location;
  const ready = Boolean(report.title.trim() && location);
  return <main className="simple-page with-bottom">
    <BackHeader title="Review report" onBack={() => go("locate")} action={<span className="flow-count">3 of 3</span>} />
    <div className="ai-banner"><span><Icon name="sparkles" size={20} /></span><div><strong>Check the details</strong><p>Everything below is editable before anyone is notified.</p></div><DemoTag>Demo AI</DemoTag></div>
    <section className="form-section"><h2>Item</h2>
      <div className="review-photo">{report.photoUrl ? <img src={report.photoUrl} alt="Found item" /> : <div className="mini-bottle" />}<button type="button" className="text-button" onClick={() => go("capture")}>Replace photo</button></div>
      <label className="result-field"><span>Item</span><input value={report.title} onChange={set("title")} /></label>
      <div className="field-row"><label className="result-field half"><span>Category</span><input value={report.category} onChange={set("category")} /></label><label className="result-field half"><span>Color</span><input value={report.color} onChange={set("color")} /></label></div>
      <label className="result-field"><span>Details</span><input value={report.description} onChange={set("description")} /></label>
    </section>
    <section className="form-section"><h2>Location</h2>
      {location ? <LocationSummary location={location} onChange={() => go("locate")} /> : <Button variant="secondary" onClick={() => go("locate")}>Identify location</Button>}
      <p className="helper-text">Found at about {report.foundAt || nowLabel()}.</p>
    </section>
    <section className="form-section"><div className="section-heading"><h2>Possible lost listing matches</h2><span className="private-label"><Icon name="shield" size={14} /> Anonymous</span></div>
      <article className="class-match"><span className="time-box">11:42<small>AM</small></span><div><strong>{report.title || "Similar item"}</strong><p>{location ? shortLocation(location) : "Same building"} · Posted earlier today</p></div></article>
      <p className="helper-text">Sample listing. Only students who posted matching lost listings are notified, and their identities stay hidden.</p>
    </section>
    <div className="toggle-card"><Toggle on={report.hideDetails} setOn={(hideDetails) => setReport((current) => ({ ...current, hideDetails }))} label="Hide identifying details from public description" /><p>Stickers and damage stay private and are used to verify the owner.</p></div>
    <div className="bottom-action">
      {!ready && <p className="action-hint">Add an item name and location to continue.</p>}
      <Button disabled={!ready} onClick={() => go("finderStatus")}><Icon name="bell" size={19} /> Notify matching listings</Button>
    </div>
  </main>;
}

function FinderStatus({ go, report }: { go: (screen: Screen) => void; report: FoundReport }) {
  const where = report.location ? shortLocation(report.location) : "HH A2";
  const title = report.title || "Blue water bottle";
  const at = report.foundAt || "11:46 AM";
  const timeline = [
    ["Found", `Today, ${at}`, true],
    ["Listings matched", "2 private reports", true],
    ["Claim pending", "Waiting for private verification", true],
    ["Verified", "Next step", false],
    ["Returned", "", false],
  ];
  return <main className="simple-page with-nav">
    <BackHeader title="Item status" onBack={() => go("home")} />
    <article className="status-hero"><div className="item-visual">{report.photoUrl ? <img src={report.photoUrl} alt="" /> : <div className="mini-bottle" />}</div><div><Status>Claim pending</Status><h1>{title}</h1><p>{where} · Today, {at}</p></div></article>
    <div className="notice-card"><span><Icon name="bell" /></span><div><strong>Matching reports notified</strong><p>We privately notified 2 students who posted similar lost listings. You won't see who.</p></div></div>
    <section className="timeline">
      {timeline.map(([label, detail, done], i) => <div className={`${done ? "done" : ""} ${i === 2 ? "current" : ""}`} key={label as string}><span className="timeline-dot">{done && i < 2 ? <Icon name="check" size={13} /> : i + 1}</span><div><strong>{label}</strong><p>{detail}</p></div></div>)}
    </section>
    <div className="demo-next"><p className="eyebrow">INTERACTIVE DEMO</p><h3>See what the owner receives</h3><p>Preview the private claim and verification flow.</p><Button variant="secondary" onClick={() => go("ownerNotice")}>Preview owner notification <Icon name="chevron" size={18} /></Button></div>
  </main>;
}

function OwnerNotice({ go, report }: { go: (screen: Screen) => void; report: FoundReport }) {
  const title = (report.title || "Blue water bottle").toLowerCase();
  const where = report.location ? formatLocation(report.location) : "Hardenbergh Hall A2";
  const short = report.location ? shortLocation(report.location) : "HH A2";
  const at = report.foundAt || "11:46 AM";
  return <main className="simple-page notice-page">
    <BackHeader title="Notification preview" onBack={() => go("finderStatus")} />
    <div className="phone-lock">
      <div className="lock-top"><span>{at.replace(/\s?[AP]M/, "")}</span><small>Today</small></div>
      <article className="push-card"><div className="push-head"><BrandIcon className="app-mini" /><Wordmark size="notification" /><small>now</small></div><h3>Where RU? Possible match</h3><p>Is this your {title}? It was found in <strong>{where}</strong>.</p></article>
    </div>
    <p className="eyebrow center">IN-APP NOTIFICATION</p>
    <article className="claim-card"><span className="claim-icon"><Icon name="search" /></span><h2>Is this yours?</h2><p>A {title} was found in <strong>{where}</strong> and may match the listing you posted.</p><div className="found-meta"><Icon name="clock" size={18} /><span><strong>Found today at {at}</strong><small>Matched against your lost listing</small></span></div><Button onClick={() => go("ownership")}>That's mine</Button><Button variant="ghost" onClick={() => go("home")}>Not mine</Button></article>
    <p className="privacy-note"><Icon name="shield" size={16} /> The finder won't know you received this.</p>
  </main>;
}

function Ownership({ go }: { go: (screen: Screen) => void }) {
  const [detail, setDetail] = useState("");
  const [result, setResult] = useState<"form" | "more" | "rejected">("form");
  const [chips, setChips] = useState<string[]>([]);
  const toggleChip = (chip: string) => setChips(chips.includes(chip) ? chips.filter((c) => c !== chip) : [...chips, chip]);
  if (result === "rejected") return <ResultState tone="red" icon="x" title="Not approved" text="Too many attempts. Try again later. This protects the item and its owner." button="Back to home" onClick={() => go("home")} />;
  return <main className="simple-page with-bottom">
    <BackHeader title="Private Verification" onBack={() => go("ownerNotice")} />
    <div className="verify-heading"><span><Icon name="shield" size={27} /></span><p className="eyebrow">PRIVATE VERIFICATION</p><h1>Tell us something only the owner would know.</h1><p>Only the finder sees this answer. It is never posted publicly.</p></div>
    {result === "more" && <div className="warning-banner"><strong>Needs more detail</strong><p>Try mentioning a sticker, dent, engraving, or what's inside. You have one retry.</p></div>}
    <label className="textarea-field"><span>Private detail</span><textarea value={detail} onChange={(e) => setDetail(e.target.value)} placeholder="For example: There's a small white cat sticker near the bottom…" /></label>
    <p className="field-label">What kind of detail are you sharing? <small>Optional</small></p>
    <div className="chip-row">{["Sticker", "Engraving", "Contents", "Damage"].map((chip) => <button key={chip} aria-pressed={chips.includes(chip)} className={chips.includes(chip) ? "selected" : ""} onClick={() => toggleChip(chip)}>{chips.includes(chip) && <Icon name="check" size={14} />}{chip}</button>)}</div>
    <div className="bottom-action">
      {result === "more" && <button className="reject-link" onClick={() => setResult("rejected")}>Demo Not approved state</button>}
      {detail.trim().length < 8 && <p className="action-hint">Enter at least 8 characters to continue.</p>}
      <Button disabled={detail.trim().length < 8} onClick={() => result === "form" && detail.toLowerCase().includes("cat") ? go("handoff") : result === "more" ? go("handoff") : setResult("more")}>Check my answer</Button>
    </div>
  </main>;
}

function ResultState({ tone, icon, title, text, button, onClick, eyebrow = "PRIVATE VERIFICATION" }: { tone: string; icon: IconName; title: string; text: string; button: string; onClick: () => void; eyebrow?: string }) {
  return <main className="result-screen"><div className={`result-icon ${tone}`}><Icon name={icon} size={42} /></div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p>{text}</p><Button onClick={onClick}>{button}</Button></main>;
}

function Handoff({ go, itemValue = "Everyday item" }: { go: (screen: Screen) => void; itemValue?: "Everyday item" | "Valuable or sensitive" }) {
  const recommendDropOff = itemValue === "Valuable or sensitive";
  const [returned, setReturned] = useState(false);
  const [handoffMethod, setHandoffMethod] = useState<"meet" | "drop">(recommendDropOff ? "drop" : "meet");
  const [meeting, setMeeting] = useState("College Ave Student Center");
  const [dropLocation, setDropLocation] = useState("Student Center information desk");
  const [readyForPickup, setReadyForPickup] = useState(false);
  const [problemReported, setProblemReported] = useState(false);
  if (returned) return <ResultState tone="green" icon="check" title="Found you!" text="Back where it belongs. Thanks for helping a fellow Scarlet Knight." button="Back to home" onClick={() => go("home")} eyebrow="HANDOFF COMPLETE" />;
  if (readyForPickup) return <main className="simple-page with-bottom">
    <BackHeader title="Item pickup" onBack={() => setReadyForPickup(false)} />
    <div className="verified-hero"><div className="result-icon green"><Icon name="check" size={30} /></div><h1>Ready for pickup at {dropLocation}</h1><p>The finder has confirmed that your item was dropped off.</p></div>
    <article className="meeting-card selected"><span><Icon name="map" /></span><div><strong>{dropLocation}</strong><p>Bring identification and your verified claim details.</p></div><Icon name="check" size={18} /></article>
    <div className="bottom-action"><Button onClick={() => setReturned(true)}>I picked it up</Button></div>
  </main>;
  return <main className="simple-page with-bottom">
    <BackHeader title="Arrange a handoff" onBack={() => go("finderStatus")} />
    <div className="verified-hero"><div className="result-icon green"><Icon name="check" size={30} /></div><Status>Verified</Status><h1>Verified</h1><p>The finder approved the private answer. First names can now be shared.</p></div>
    <section className="handoff-choice"><h2>How do you want to return it?</h2>
      <div className="method-cards">
        <button aria-pressed={handoffMethod === "meet"} className={handoffMethod === "meet" ? "selected" : ""} onClick={() => setHandoffMethod("meet")}><span className="method-icon"><Icon name="user" size={27} /></span><span><strong>Meet in person</strong><small>Choose a public campus meeting spot</small></span><span className="radio-dot">{handoffMethod === "meet" && <span />}</span></button>
        <button aria-pressed={handoffMethod === "drop"} className={handoffMethod === "drop" ? "selected" : ""} onClick={() => setHandoffMethod("drop")}><span className="method-icon"><Icon name="bag" size={27} /></span><span><strong>Drop it off</strong><small>Leave it at a staffed pickup location</small></span><span className="radio-dot">{handoffMethod === "drop" && <span />}</span></button>
      </div>
    </section>
    {recommendDropOff && <div className="warning-banner"><strong>For your safety, we recommend dropping this at an official lost and found.</strong></div>}
    <section className="identity-card"><p className="eyebrow">FIRST NAMES REVEALED</p><div className="people"><div><span className="person-avatar scarlet">M</span><strong>Maya</strong><small>Owner</small></div><span className="meet-line"><Icon name="chevron" /><Icon name="chevron" /></span><div><span className="person-avatar blue">J</span><strong>Jordan</strong><small>Finder</small></div></div></section>
    {handoffMethod === "meet" ? <>
      <section className="meeting-section"><h2>Choose a public meeting spot</h2><p>Meet in a staffed, well-lit campus location.</p>
        <button className={`meeting-card ${meeting === "College Ave Student Center" ? "selected" : ""}`} aria-pressed={meeting === "College Ave Student Center"} onClick={() => setMeeting("College Ave Student Center")}><span><Icon name="map" /></span><div><strong>College Ave Student Center</strong><p>Information desk · Open until 11 PM</p></div>{meeting === "College Ave Student Center" ? <Icon name="check" size={18} /> : <Icon name="chevron" size={18} />}</button>
        <button className={`meeting-card ${meeting === "Alexander Library" ? "selected" : ""}`} aria-pressed={meeting === "Alexander Library"} onClick={() => setMeeting("Alexander Library")}><span><Icon name="map" /></span><div><strong>Alexander Library</strong><p>Security desk · Open until 2 AM</p></div>{meeting === "Alexander Library" ? <Icon name="check" size={18} /> : <Icon name="chevron" size={18} />}</button>
      </section>
      <div className="message-preview"><span className="person-avatar scarlet">M</span><div><small>Maya · just now</small><p>Hi! I can meet at {meeting === "Alexander Library" ? "the Alexander Library security desk" : "the student center info desk"} at 3:30.</p></div></div>
      <div className="bottom-action dual"><Button onClick={() => setReturned(true)}>Mark as returned</Button><Button variant="ghost" onClick={() => setProblemReported(true)} className={problemReported ? "reported" : ""}>Report a problem</Button></div>
    </> : <>
      <section className="meeting-section"><h2>Choose a drop-off location</h2><p>Leave the item with staff and keep the receipt.</p>
        <button className={`meeting-card ${dropLocation === "Student Center information desk" ? "selected" : ""}`} aria-pressed={dropLocation === "Student Center information desk"} onClick={() => setDropLocation("Student Center information desk")}><span><Icon name="map" /></span><div><strong>Student Center information desk</strong><p>Staffed campus pickup location</p></div>{dropLocation === "Student Center information desk" ? <Icon name="check" size={18} /> : <Icon name="chevron" size={18} />}</button>
        <button className={`meeting-card ${dropLocation === "Official Rutgers lost and found" ? "selected" : ""}`} aria-pressed={dropLocation === "Official Rutgers lost and found"} onClick={() => setDropLocation("Official Rutgers lost and found")}><span><Icon name="shield" /></span><div><strong>Official Rutgers lost and found</strong><p>Recommended for valuable or sensitive items</p></div>{dropLocation === "Official Rutgers lost and found" ? <Icon name="check" size={18} /> : <Icon name="chevron" size={18} />}</button>
        <button className="meeting-card" disabled><span><Icon name="lock" /></span><div><strong>Where RU? Locker (coming soon)</strong><p>Secure self-service pickup</p></div></button>
      </section>
      <div className="bottom-action"><Button onClick={() => setReadyForPickup(true)}>I dropped it off</Button></div>
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

function Lost({ go, sensitiveItems }: { go: (screen: Screen) => void; sensitiveItems: SensitiveItem[] }) {
  const [step, setStep] = useState(1);
  const [posted, setPosted] = useState(false);
  const [photoAdded, setPhotoAdded] = useState(false);
  const [itemName, setItemName] = useState("Blue water bottle");
  const [itemDescription, setItemDescription] = useState("");
  const [category, setCategory] = useState("Water bottle");
  const [color, setColor] = useState("Navy blue");
  const [rememberedAt, setRememberedAt] = useState("Today, around 12:10 PM");
  const [value, setValue] = useState("Everyday item");
  const [timer, setTimer] = useState("24h");
  const [timerEnd, setTimerEnd] = useState("Delete the listing");
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
  const [locationHistory, setLocationHistory] = useState(true);
  const [places, setPlaces] = useState<TimelinePlace[]>([
    { id: 1, time: "11:00 AM", sortMinutes: 660, name: "Alexander Library", source: "Location", high: false },
    { id: 2, time: "12:10 PM", sortMinutes: 730, name: "Hardenbergh Hall, A2", source: "Class", high: true },
    { id: 3, time: "1:30 PM", sortMinutes: 810, name: "Busch Dining Hall", source: "Location", high: true },
  ]);
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
  const timerStatus = `Trusted helpers only, ${timer} left`;
  const selectRegisteredItem = (item: SensitiveItem) => {
    setItemName(item.name);
    setItemDescription(item.description);
    setPhotoAdded(item.photoAdded);
    setValue("Valuable or sensitive");
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

  if (posted) return <main className="simple-page with-nav"><BackHeader title="Possible matches" onBack={() => setPosted(false)} /><div className="match-heading"><p className="eyebrow">LISTING POSTED · 2 POSSIBLE MATCHES</p>{value === "Valuable or sensitive" && <Status>{timerStatus}</Status>}<h1>We found a few similar items</h1><p>Review the details carefully. A match doesn't mean the item is yours.</p></div>
    <article className="match-card"><div className="match-image bottle-bg"><div className="mini-bottle" /></div><div className="match-info"><span className="confidence high">High match</span><h3>Blue water bottle</h3><p><Icon name="map" size={15} /> Hardenbergh Hall · Today</p><Button onClick={() => go("ownership")}>Check if it's mine</Button></div></article>
    <article className="match-card"><div className="match-image umbrella-bg">⌁</div><div className="match-info"><span className="confidence medium">Medium match</span><h3>Navy insulated bottle</h3><p><Icon name="map" size={15} /> Alexander Library · Yesterday</p><Button variant="secondary" onClick={() => go("ownership")}>View details</Button></div></article>
    <div className="tip-card"><Icon name="shield" /><div><strong>Matches are suggestions</strong><p>We never label an item “yours” until ownership is verified.</p></div></div>
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
        <label className="result-field"><span>Category</span><select value={category} onChange={(event) => setCategory(event.target.value)}><option>Water bottle</option><option>Electronics</option><option>Clothing</option><option>School supplies</option><option>Keys</option><option>Wallet or ID</option></select></label>
        <label className="result-field"><span>Color</span><input value={color} onChange={(event) => setColor(event.target.value)} /></label>
        <label className="result-field"><span>When do you last remember having it?</span><input value={rememberedAt} onChange={(event) => setRememberedAt(event.target.value)} /></label>
        <button className={`photo-upload ${photoAdded ? "added" : ""}`} onClick={() => setPhotoAdded(!photoAdded)}>
          <span><Icon name={photoAdded ? "check" : "camera"} /></span>
          <div><strong>{photoAdded ? "Sample photo added" : "Add a photo"}</strong><small>Optional, helps improve matches</small></div>
          <span className="photo-action">{photoAdded ? "Remove" : "Choose"}</span>
        </button>
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
      {value === "Valuable or sensitive" && <div className="sensitive-note"><Icon name="shield" /><div><strong>Sensitive listings stay private at first.</strong><p>Only limited details appear until a potential match is safely verified.</p></div></div>}
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
        <div className="location-toggle"><Toggle on={locationHistory} setOn={setLocationHistory} label="Use my location history" /><p>Only stored on your account. Delete anytime.</p></div>
        <div className="source-note"><Icon name="shield" size={17} /><p>Class schedule details are used only for this lost listing.</p></div>
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
      <p className="eyebrow">STEP 5 · VISIBILITY TIMER</p>
      <h1>Give trusted helpers a head start.</h1>
      <p className="subtext">Trusted helpers see this first. High-reputation users get priority.</p>
      <div className="timer-hero"><span><Icon name="lock" size={27} /></span><div><strong>Private release window</strong><p>Your sensitive details stay hidden throughout.</p></div></div>
      <p className="field-label">Visibility timer</p>
      <div className="timer-options">{["1h", "3h", "6h", "12h", "24h", "48h", "72h", "1 week"].map((option) => <button aria-pressed={timer === option} className={timer === option ? "selected" : ""} onClick={() => setTimer(option)} key={option}>{option}<span className="radio-dot">{timer === option && <span />}</span></button>)}</div>
      <p className="field-label timer-end-label">When the timer ends:</p>
      <div className="timer-end-options">
        {[
          ["Delete the listing", "Remove it automatically from Where RU?"],
          ["Open it to the public", "Sensitive details stay hidden"],
        ].map(([option, note]) => <button aria-pressed={timerEnd === option} className={timerEnd === option ? "selected" : ""} onClick={() => setTimerEnd(option)} key={option}><span><strong>{option}</strong><small>{note}</small></span><span className="radio-dot">{timerEnd === option && <span />}</span></button>)}
      </div>
      <div className="timer-preview"><Status>{timerStatus}</Status><p>This status appears on your listing during the private window.</p></div>
    </section>}

    {step === reviewStep && <section className="flow-step">
      <p className="eyebrow">STEP {reviewStep} · REVIEW</p>
      <h1>Ready to post?</h1>
      <p className="subtext">Check your listing. You can edit it anytime.</p>
      <article className="review-card">
        <div className="review-item"><div className="review-thumb">{category === "Water bottle" ? <div className="mini-bottle" /> : <Icon name="lock" size={28} />}</div><div><span className="review-badge">{value}</span><h2>{itemName}</h2><p>{color} · {category}</p></div></div>
        <div className="review-row"><span><Icon name="clock" size={18} /> Last remembered</span><strong>{rememberedAt}</strong></div>
        <div className="review-row"><span><Icon name="map" size={18} /> Search method</span><strong>{method === "room" ? (lostLocation ? `${formatLocation(lostLocation)} · ${sourceLabel[lostLocation.source]}` : "Known room") : "Retraced steps"}</strong></div>
        {value === "Valuable or sensitive" && <div className="review-row"><span><Icon name="lock" size={18} /> Visibility</span><strong>Trusted helpers · {timer}</strong></div>}
      </article>
      <section className="review-priority"><h2>High priority spots</h2>{places.filter((place) => place.high).map((place) => <div key={place.id}><span><Icon name="map" size={16} /></span><p><strong>{place.name}</strong><small>{place.time}</small></p></div>)}</section>
      <div className="safe-card"><Icon name="shield" /><p><strong>Your exact timeline stays private.</strong><br />Finders only see the details needed to identify a possible match.</p></div>
    </section>}

    <div className="bottom-action">
      {step === 3 && !method && <p className="action-hint">Choose an option to continue.</p>}
      {step === 3 && method === "room" && !lostLocation && <p className="action-hint">Confirm a room to continue.</p>}
      {step < totalSteps ? <Button onClick={next} disabled={step === 3 && (!method || (method === "room" && !lostLocation))}>Continue <Icon name="chevron" size={18} /></Button> : <Button onClick={() => setPosted(true)}><Icon name="search" size={19} /> Post lost listing</Button>}
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

function Items({ go }: { go: (screen: Screen) => void }) {
  const [tab, setTab] = useState("Found by me");
  const lists: Record<string, typeof activeItems> = {
    "Found by me": activeItems,
    "Lost by me": [
      { emoji: "▰", title: "Space gray MacBook Air", place: "Hardenbergh Hall · Today", status: "Trusted helpers only, 18h left" },
      { emoji: "⌁", title: "Black umbrella", place: "Livingston Student Center · Mar 12", status: "Returned" },
    ],
    "Claims": [{ emoji: "◒", title: "Blue water bottle", place: "Hardenbergh Hall · Today", status: "Verified" }],
  };
  const itemAction = (item: ItemData) => {
    if (item.status === "Verified") return () => go("handoff");
    if (item.status === "Claim pending") return () => go("finderStatus");
    if (item.status === "Pinging" || item.status.startsWith("Trusted helpers")) return () => go("map");
    return undefined;
  };
  return <main className="tab-page"><header className="title-header"><h1>My items</h1><p>Track finds, reports, and claims</p></header>
    <div className="tabs">{Object.keys(lists).map((name) => <button aria-pressed={tab === name} className={tab === name ? "active" : ""} onClick={() => setTab(name)} key={name}>{name}</button>)}</div>
    <div className="stack item-list">{lists[tab].map((item) => <ItemCard item={item} large key={item.title} onClick={itemAction(item)} />)}</div>
    <div className="empty-note"><Icon name="bag" /><p>Nothing lost yet. Keep it that way.</p></div>
  </main>;
}

function CampusMapScreen({ go, firstName, lastName, dark }: { go: (screen: Screen) => void; firstName: string; lastName: string; dark: boolean }) {
  const [campus, setCampus] = useState<CampusName>("College Ave");
  const [visibleListings, setVisibleListings] = useState<ListingProperties[]>([]);
  const initials = `${firstName[0] || ""}${lastName[0] || ""}`.toUpperCase();
  return <main className="tab-page map-page">
    <header className="title-header map-title"><div><h1>Campus map</h1><p>Potential lost-item activity nearby</p></div><button className="map-profile" aria-label={`Open ${firstName}'s profile`} onClick={() => go("profile")}>{initials}</button></header>
    <div className="campus-filter" aria-label="Choose campus">{(Object.keys(campusViews) as CampusName[]).map((name) => <button aria-pressed={campus === name} className={campus === name ? "active" : ""} onClick={() => setCampus(name)} key={name}>{name}</button>)}</div>
    <CampusMap campus={campus} dark={dark} onVisibleListingsChange={setVisibleListings} />
    <div className="map-summary"><span><Icon name="sparkles" size={18} /></span><p><strong>{visibleListings.length} possible items in this area</strong><small>Based on recent finds and active lost listings</small></p></div>
    <section className="section nearby-items">
      <div className="section-heading"><h2>Potential matches nearby</h2><button onClick={() => go("lost")}>Refine search</button></div>
      {visibleListings.slice(0, 2).map((listing) => <article className="map-result-card" key={listing.id}><span className="map-result-icon">{listing.title.includes("AirPods") ? "◉" : "⌁"}</span><span><strong>{listing.title}</strong><small>Near a {listing.placeType.replace("_", " ")} · {listing.hoursAgo}h ago</small><em>{listing.weight >= 0.8 ? "High" : "Medium"} activity area</em></span><span className="distance">{listing.type === "lost" ? "Lost" : "Found"}</span></article>)}
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
  const [addingItem, setAddingItem] = useState(false);
  const [registerPhotoAdded, setRegisterPhotoAdded] = useState(false);
  const [registerName, setRegisterName] = useState("");
  const [registerDescription, setRegisterDescription] = useState("");
  const [registerSerial, setRegisterSerial] = useState("");
  const campuses = ["College Avenue", "Busch", "Livingston", "Cook/Douglass"];
  const isRutgersEmail = /@(rutgers\.edu|scarletmail\.rutgers\.edu)$/i.test(email);
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
    <section className="profile-card"><span className="profile-avatar">{initials}</span><div><h2>{firstName} {lastName}</h2><p>{email}</p>{isRutgersEmail && <span>Rutgers verified</span>}</div></section>
    <section className="reputation-card">
      <div className="reputation-top"><span className="reputation-shield"><Icon name="shield" size={25} /></span><div><p className="eyebrow">CAMPUS REPUTATION</p><h2>Trusted Helper</h2></div><strong>860 <small>pts</small></strong></div>
      <div className="reputation-progress"><span /></div>
      <div className="reputation-stats"><div><strong>12</strong><small>Successful returns</small></div><div><strong>140</strong><small>Points to Champion</small></div></div>
      <div className="level-path"><span>New Member</span><span>Community Helper</span><span className="active">Trusted Helper</span><span>Campus Champion</span></div>
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
    <button className="signout" onClick={() => go("signin")}><Icon name="logout" /> Sign out</button>
    <p className="project-note">Where RU? is an independent student project.<br />Not affiliated with or endorsed by Rutgers University.</p>
  </main>;
}

function BottomNav({ screen, go }: { screen: Screen; go: (screen: Screen) => void }) {
  const items: [IconName, string, Screen][] = [["home", "Home", "home"], ["camera", "Found", "capture"], ["map", "Map", "map"], ["user", "Profile", "profile"]];
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

const initialSensitiveItems: SensitiveItem[] = [
  { id: "macbook-air", name: "MacBook Air", description: "Small scratch beside the left USB port", serial: "C02SAMPLE123", photoAdded: true },
  { id: "airpods-pro", name: "AirPods Pro", description: "Blue silicone case with initials AJ", serial: "", photoAdded: true },
];

export default function App() {
  const [screen, setScreen] = useState<Screen>("signin");
  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [theme, setTheme] = useState<ThemePreference>("system");
  const [systemDark, setSystemDark] = useState(() => typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  const [foundReport, setFoundReportState] = useState<FoundReport>(emptyFoundReport);
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
    if (next === "capture" && !["locate", "confirm"].includes(screen)) setFoundReportState(emptyFoundReport);
    setScreen(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const completeEmailVerification = () => {
    const names = nameFromEmail(email);
    setFirstName(names.first);
    setLastName(names.last);
    go("name");
  };
  const screens: Record<Screen, ReactNode> = {
    signin: <SignIn go={go} email={email} setEmail={setEmail} />, code: <CodeScreen go={go} email={email} onVerified={completeEmailVerification} />, name: <NameScreen go={go} firstName={firstName} setFirstName={setFirstName} lastName={lastName} setLastName={setLastName} />, home: <Home go={go} firstName={firstName} lastName={lastName} />,
    capture: <Capture go={go} report={foundReport} setReport={setFoundReport} />, locate: <Locate go={go} report={foundReport} setReport={setFoundReport} />, confirm: <Confirm go={go} report={foundReport} setReport={setFoundReport} />, finderStatus: <FinderStatus go={go} report={foundReport} />, ownerNotice: <OwnerNotice go={go} report={foundReport} />,
    ownership: <Ownership go={go} />, handoff: <Handoff go={go} itemValue="Valuable or sensitive" />, lost: <Lost go={go} sensitiveItems={sensitiveItems} />, items: <Items go={go} />,
    map: <CampusMapScreen go={go} firstName={firstName} lastName={lastName} dark={dark} />, profile: <Profile go={go} email={email} firstName={firstName} lastName={lastName} theme={theme} setTheme={setTheme} demo={demo} setDemo={setDemo} notifications={notifications} setNotifications={setNotifications} sensitiveItems={sensitiveItems} addSensitiveItem={addSensitiveItem} deleteSensitiveItem={deleteSensitiveItem} homeCampus={homeCampus} setHomeCampus={setHomeCampus} />,
  };
  const navScreens: Screen[] = ["home", "items", "map", "profile", "finderStatus"];
  return <div className={dark ? "app-root dark" : "app-root"}><div className="app-shell">{screens[screen]}{navScreens.includes(screen) && <BottomNav screen={screen} go={go} />}</div></div>;
}
