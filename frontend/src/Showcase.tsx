import { useState } from "react";
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

export default function Showcase() {
  const [active, setActive] = useState<PhoneId>("jordan");
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
          <div className="phone-frame"><iframe title={`${phone.name}'s phone`} src={`?as=${phone.id}&embed=1`} /></div>
        </figure>)}
      </div>
    </section>
  </div>;
}
