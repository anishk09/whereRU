import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { Button, Icon } from "./ui";
import {
  activeRecognizer,
  buildings,
  campuses,
  formatLocation,
  nearestCampus,
  sourceLabel,
  validateImage,
  type CampusId,
  type RoomCandidate,
  type RoomLocation,
} from "./roomRecognition";

type Method = "scan" | "placard" | "manual";

export function DemoTag({ children = "Demo result" }: { children?: string }) {
  return <span className="demo-tag"><Icon name="sparkles" size={12} />{children}</span>;
}

/** Hidden file inputs for camera capture and library upload, with validation. */
export function PhotoButtons({ onPhoto, onError, cameraLabel, uploadLabel = "Upload", compact = false }: {
  onPhoto: (file: File, url: string) => void;
  onError: (message: string) => void;
  cameraLabel: string;
  uploadLabel?: string;
  compact?: boolean;
}) {
  const cameraRef = useRef<HTMLInputElement>(null);
  const uploadRef = useRef<HTMLInputElement>(null);
  const handle = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    const problem = validateImage(file);
    if (problem || !file) {
      onError(problem ?? "No photo was selected.");
      return;
    }
    onPhoto(file, URL.createObjectURL(file));
  };
  return <div className={`photo-buttons ${compact ? "compact" : ""}`}>
    <input ref={cameraRef} type="file" accept="image/*" capture="environment" hidden onChange={handle} data-testid="camera-input" />
    <input ref={uploadRef} type="file" accept="image/*" hidden onChange={handle} data-testid="upload-input" />
    <Button onClick={() => cameraRef.current?.click()}><Icon name="camera" size={19} /> {cameraLabel}</Button>
    <Button variant="secondary" onClick={() => uploadRef.current?.click()}><Icon name="image" size={19} /> {uploadLabel}</Button>
  </div>;
}

export function LocationSummary({ location, onChange }: { location: RoomLocation; onChange?: () => void }) {
  return <div className="location-summary">
    <span className="location-summary-icon"><Icon name="door" size={22} /></span>
    <div><small>{sourceLabel[location.source]} · {location.campus}</small><strong>{formatLocation(location)}</strong></div>
    {onChange && <button type="button" className="text-button" onClick={onChange}>Change</button>}
  </div>;
}

export default function LocationPicker({ value, onChange, context }: {
  value: RoomLocation | null;
  onChange: (location: RoomLocation | null) => void;
  context: "found" | "lost";
}) {
  const [method, setMethod] = useState<Method>("scan");
  const [phase, setPhase] = useState<"idle" | "analyzing" | "results" | "none">("idle");
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [candidates, setCandidates] = useState<RoomCandidate[]>([]);
  const [campusHint, setCampusHint] = useState<CampusId | null>(null);
  const [geoMessage, setGeoMessage] = useState("");
  const [manualCampus, setManualCampus] = useState<CampusId>(value?.campus ?? "College Ave");
  const [manualCode, setManualCode] = useState(value?.code ?? "");
  const [manualRoom, setManualRoom] = useState(value?.room ?? "");
  const [placardRead, setPlacardRead] = useState(false);
  const runId = useRef(0);

  useEffect(() => () => { if (photoUrl) URL.revokeObjectURL(photoUrl); }, [photoUrl]);

  const reset = (next: Method) => {
    runId.current += 1;
    setMethod(next);
    setPhase("idle");
    setPhotoUrl(null);
    setError("");
    setCandidates([]);
    setPlacardRead(false);
  };

  const scanRoom = async (file: File | null, url: string | null) => {
    const id = ++runId.current;
    setPhotoUrl(url);
    setError("");
    setPhase("analyzing");
    const results = await activeRecognizer.recognizeRoom(file, campusHint);
    if (id !== runId.current) return;
    setCandidates(results);
    setPhase(results.length ? "results" : "none");
  };

  const readPlacard = async (file: File | null, url: string | null) => {
    const id = ++runId.current;
    setPhotoUrl(url);
    setError("");
    setPhase("analyzing");
    const result = await activeRecognizer.readPlacard(file);
    if (id !== runId.current) return;
    if (!result) {
      setPhase("none");
      return;
    }
    setManualCampus(result.campus);
    setManualCode(result.code);
    setManualRoom(result.room);
    setPlacardRead(true);
    setPhase("results");
  };

  const useLocation = () => {
    if (!navigator.geolocation) {
      setGeoMessage("Location isn't available in this browser. Results will cover College Ave.");
      return;
    }
    setGeoMessage("Finding your campus…");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const campus = nearestCampus(position.coords.longitude, position.coords.latitude);
        setCampusHint(campus);
        setGeoMessage(`Narrowing results to ${campus}.`);
      },
      () => setGeoMessage("Location permission was denied. You can still scan, or choose a campus below."),
      { timeout: 8000 },
    );
  };

  const saveTyped = (source: "placard" | "manual") => {
    const building = buildings.find((item) => item.code === manualCode);
    if (!building || !manualRoom.trim()) return;
    onChange({ campus: building.campus, code: building.code, building: building.name, room: manualRoom.trim().toUpperCase(), source });
  };

  if (value) return <div className="location-picker"><LocationSummary location={value} onChange={() => { onChange(null); reset(value.source === "placard" ? "placard" : value.source === "manual" ? "manual" : "scan"); }} /></div>;

  const campusBuildings = buildings.filter((item) => item.campus === manualCampus);
  const typedFields = (source: "placard" | "manual") => <div className="typed-room">
    <label className="result-field"><span>Campus</span><select value={manualCampus} onChange={(event) => { setManualCampus(event.target.value as CampusId); setManualCode(""); }}>{campuses.map((campus) => <option key={campus}>{campus}</option>)}</select></label>
    <div className="field-row">
      <label className="result-field half"><span>Building</span><select value={manualCode} onChange={(event) => setManualCode(event.target.value)}><option value="">Choose…</option>{campusBuildings.map((item) => <option value={item.code} key={item.code}>{item.name} ({item.code})</option>)}</select></label>
      <label className="result-field half"><span>Room</span><input value={manualRoom} onChange={(event) => setManualRoom(event.target.value)} placeholder="e.g. A2" /></label>
    </div>
    {(!manualCode || !manualRoom.trim()) && <p className="form-hint">Choose a building and enter a room number.</p>}
    <Button variant="secondary" disabled={!manualCode || !manualRoom.trim()} onClick={() => saveTyped(source)}>Use this room</Button>
  </div>;

  return <div className="location-picker">
    <div className="picker-tabs" role="tablist" aria-label="How to identify the room">
      {([["scan", "Scan room"], ["placard", "Placard"], ["manual", "Choose"]] as [Method, string][]).map(([key, label]) => <button key={key} role="tab" aria-selected={method === key} className={method === key ? "active" : ""} onClick={() => reset(key)}>{label}</button>)}
    </div>

    {error && <div className="picker-error" role="alert"><strong>{error}</strong><div><button type="button" onClick={() => setError("")}>Try again</button><button type="button" onClick={() => reset("manual")}>Choose manually</button></div></div>}

    {method === "scan" && <div className="picker-panel">
      {phase === "idle" && <>
        <div className="scan-explainer">
          <div className="scan-visual" aria-hidden="true"><span className="board" /><span className="row r1" /><span className="row r2" /><span className="row r3" /><span className="scan-line" /></div>
          <div><span className="recommended">Recommended</span><strong>{context === "found" ? "Photograph the room where you found it" : "Photograph the room you think you lost it in"}</strong><p>Stand near the back and capture the front wall, boards, and seating. We compare the layout against known classrooms.</p></div>
        </div>
        <button type="button" className="geo-chip" onClick={useLocation}><Icon name="locate" size={16} /> {campusHint ? `Near ${campusHint}` : "Use my location to narrow buildings"}</button>
        {geoMessage && <p className="location-message" role="status">{geoMessage}</p>}
        {context === "lost" && <p className="form-hint left">Not there anymore? Use Choose to pick the room from a list.</p>}
        <PhotoButtons cameraLabel="Scan the room" onPhoto={(file, url) => scanRoom(file, url)} onError={setError} />
        <button type="button" className="text-button sample" onClick={() => scanRoom(null, null)}>Use a sample room photo</button>
      </>}
      {phase === "analyzing" && <div className="picker-analyzing" aria-live="polite" aria-busy="true">
        {photoUrl ? <img src={photoUrl} alt="Room photo being analyzed" /> : <div className="sample-room" aria-hidden="true" />}
        <div><span className="spinner" /> Comparing seating, boards, and windows…</div>
      </div>}
      {phase === "results" && <div className="candidate-list">
        <div className="candidate-head"><h3>Possible classroom matches</h3>{candidates.some((candidate) => candidate.demo !== false) ? <DemoTag /> : <span className="demo-tag live"><Icon name="check" size={12} />On-device match</span>}</div>
        {candidates.some((candidate) => candidate.demo !== false)
          ? <p className="form-hint left">These are sample rooms because the room-recognition server isn't running. Pick the one that matches what you see.</p>
          : <p className="form-hint left">Matched against reference photos of campus classrooms. Confirm the room before continuing.</p>}
        {candidates.map((candidate, index) => <button type="button" className="candidate-card" key={`${candidate.location.code}-${candidate.location.room}`} onClick={() => onChange(candidate.location)}>
          <span className="candidate-rank">{index + 1}</span>
          <span><strong>{formatLocation(candidate.location)}</strong><small>{candidate.location.campus} · {candidate.location.code}</small><span className="feature-chips">{candidate.features.map((feature) => <em key={feature}>{feature}</em>)}</span></span>
          <Icon name="chevron" size={18} />
        </button>)}
        <div className="none-match"><p>None of these?</p><div><button type="button" onClick={() => reset("placard")}>Scan the placard</button><button type="button" onClick={() => reset("manual")}>Choose manually</button><button type="button" onClick={() => reset("scan")}>Retake</button></div></div>
      </div>}
      {phase === "none" && <div className="none-match solo"><p><strong>We couldn't match this room.</strong> It may not be in our classroom index yet.</p><div><button type="button" onClick={() => reset("placard")}>Scan the placard</button><button type="button" onClick={() => reset("manual")}>Choose manually</button></div></div>}
    </div>}

    {method === "placard" && <div className="picker-panel">
      {phase === "idle" && <>
        <div className="scan-explainer placard"><div className="placard-visual" aria-hidden="true"><small>BUILDING</small><strong>A2</strong></div><div><strong>Photograph the room number sign</strong><p>Usually beside the door. Make sure the building and room number are readable.</p></div></div>
        <PhotoButtons cameraLabel="Scan placard" onPhoto={(file, url) => readPlacard(file, url)} onError={setError} />
        <button type="button" className="text-button sample" onClick={() => readPlacard(null, null)}>Use a sample placard photo</button>
      </>}
      {phase === "analyzing" && <div className="picker-analyzing" aria-live="polite" aria-busy="true">{photoUrl ? <img src={photoUrl} alt="Placard photo being read" /> : <div className="sample-placard" aria-hidden="true">A2</div>}<div><span className="spinner" /> Reading the sign…</div></div>}
      {phase === "results" && placardRead && <><div className="candidate-head"><h3>Check what we read</h3><DemoTag /></div>{typedFields("placard")}</>}
      {phase === "none" && <div className="none-match solo"><p><strong>We couldn't read the sign.</strong> Try again with less glare, or choose the room.</p><div><button type="button" onClick={() => reset("placard")}>Retake</button><button type="button" onClick={() => reset("manual")}>Choose manually</button></div></div>}
    </div>}

    {method === "manual" && <div className="picker-panel">{typedFields("manual")}</div>}
  </div>;
}
