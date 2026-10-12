import { useEffect, useState, type CSSProperties } from "react";
import { Wordmark } from "./ui";

// Desktop landing page: what Where RU? is, how to try it, and the finder's and owner's phones side
// by side. Each phone is the real app in a frame; they share this browser's storage, so a report
// posted on one phone shows up (with its alert) on the other.

const phones = [
  { id: "jordan", name: "Jordan", role: "Found a water bottle" },
  { id: "maya", name: "Maya", role: "Lost her water bottle" },
] as const;

type PhoneId = (typeof phones)[number]["id"];

function resetDemo() {
  for (const store of [localStorage, sessionStorage]) {
    try {
      Object.keys(store).filter((key) => key.startsWith("where-ru")).forEach((key) => store.removeItem(key));
    } catch {
      // Storage unavailable: a reload already starts fresh.
    }
  }
  window.location.reload();
}

// Real iPhone 17 size (402 x 874 pt screen, 12 pt frame); the phones shrink together to fit the window.
const PHONE_W = 426, PHONE_H = 898, TWO_UP = 1440;

function phoneScale() {
  const twoUp = window.innerWidth >= TWO_UP;
  const byHeight = (window.innerHeight - 150) / PHONE_H;
  const byWidth = (window.innerWidth - 96 - 480 - 64) / (twoUp ? PHONE_W * 2 + 40 : PHONE_W);
  return Math.max(0.55, Math.min(1, byHeight, byWidth));
}

function StatusBar() {
  return <div className="phone-status" aria-hidden="true">
    <span>9:41</span>
    <span className="phone-status-icons">
      <svg width="18" height="12" viewBox="0 0 18 12" fill="currentColor"><rect x="0" y="8" width="3" height="4" rx="1" /><rect x="5" y="5.5" width="3" height="6.5" rx="1" /><rect x="10" y="3" width="3" height="9" rx="1" /><rect x="15" y="0" width="3" height="12" rx="1" /></svg>
      <svg width="16" height="12" viewBox="0 0 16 12" fill="currentColor"><path d="M8 2.2c2.3 0 4.4.9 6 2.4l1.2-1.3A10.4 10.4 0 0 0 8 .4 10.4 10.4 0 0 0 .8 3.3L2 4.6a8.6 8.6 0 0 1 6-2.4Zm0 3.6c1.3 0 2.5.5 3.4 1.3l1.2-1.3A6.6 6.6 0 0 0 8 4a6.6 6.6 0 0 0-4.6 1.8l1.2 1.3c.9-.8 2.1-1.3 3.4-1.3Zm0 3.6c.4 0 .8.1 1.1.4L8 11.6 6.9 9.8c.3-.3.7-.4 1.1-.4Z" /></svg>
      <svg width="27" height="13" viewBox="0 0 27 13" fill="none"><rect x=".5" y=".5" width="23" height="12" rx="3.8" stroke="currentColor" opacity=".4" /><rect x="2" y="2" width="20" height="9" rx="2.5" fill="currentColor" /><path d="M25 4.5v4c.8-.3 1.3-1.1 1.3-2s-.5-1.7-1.3-2Z" fill="currentColor" opacity=".45" /></svg>
    </span>
  </div>;
}

export default function Showcase() {
  const [active, setActive] = useState<PhoneId>("jordan");
  const [scale, setScale] = useState(phoneScale);
  useEffect(() => {
    const update = () => setScale(phoneScale());
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);
  const link = `${window.location.origin}${window.location.pathname}`;
  return <div className="showcase">
    <section className="showcase-copy">
      <Wordmark size="welcome" className="showcase-wordmark" />
      <p className="showcase-kicker">Student-to-student lost &amp; found</p>
      <h1>Help it find its way home.</h1>
      <p className="showcase-lede">A finder photographs the item and scans the room. Where RU? figures out which classroom it was, then privately alerts the student who lost it there. The owner proves it's theirs before anyone's identity is shared.</p>

      <h2>Try it</h2>
      <ol className="showcase-steps">
        <li><strong>As Jordan,</strong> tap <em>I found something</em>, use the sample photo, then <em>Choose</em> Busch · Hill Center · room 114.</li>
        <li><strong><span className="only-two">Watch Maya's phone.</span><span className="only-one">Switch to Maya.</span></strong> She gets a match alert for the bottle she lost there. Tap it and claim it with a private detail.</li>
        <li><strong>Back on Jordan's phone,</strong> review her answer, approve it, and mark the bottle returned.</li>
      </ol>

      <div className="showcase-actions">
        <button type="button" onClick={resetDemo}>Reset demo</button>
        <span>Open <a href={link}>{link.replace(/^https?:\/\//, "").replace(/\/$/, "")}</a> on your phone for the full-screen app.</span>
      </div>
      <p className="showcase-note">Built at HackRU Fall 2026 · Fictional students and reports · Room scan and photo analysis are simulated in this online demo · Not affiliated with or endorsed by Rutgers University.</p>
    </section>

    <section className="showcase-phones" aria-label="Live demo">
      <div className="showcase-switch" role="tablist" aria-label="Choose a phone">
        {phones.map((phone) => <button key={phone.id} role="tab" aria-selected={active === phone.id} className={active === phone.id ? "active" : ""} onClick={() => setActive(phone.id)}>{phone.name}</button>)}
      </div>
      <div className="showcase-row">
        {phones.map((phone) => <figure key={phone.id} className={`showcase-phone ${active === phone.id ? "is-active" : ""}`}>
          <figcaption><strong>{phone.name}</strong><span>{phone.role}</span></figcaption>
          <div className="phone-slot" style={{ "--phone-scale": scale } as CSSProperties}>
            <div className="phone-frame">
              <div className="phone-screen">
                <iframe title={`${phone.name}'s phone`} src={`?as=${phone.id}&embed=1`} />
                <StatusBar />
                <span className="phone-island" aria-hidden="true" />
                <span className="phone-home" aria-hidden="true" />
              </div>
            </div>
          </div>
        </figure>)}
      </div>
    </section>
  </div>;
}
