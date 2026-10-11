import {useEffect,useState} from "react";
import {api} from "./api";
import {useConnected,categoryLabel} from "./connected";
import {Button,Icon} from "./ui";
import {campusPlaces} from "./mapData";

export async function analyzePhoto(file:File){const form=new FormData();form.append("image",file);return api("/vision/items",form);}
export async function browserPhoto(file:File){
 if(!/heic|heif/i.test(file.type+file.name))return file;
 const form=new FormData();form.append("image",file);const normalized=await api("/vision/normalize",form);
 const blob=await fetch(normalized.image).then(r=>r.blob());return new File([blob],file.name.replace(/\.hei[cf]$/i,".jpg"),{type:"image/jpeg"});
}

export function PhotoExamples({onSelect,rooms=false}:{onSelect:(file:File,url:string)=>void;rooms?:boolean}){
 const [examples,setExamples]=useState<any[]>([]),[error,setError]=useState("");
 useEffect(()=>{api(rooms?"/vision/room-examples":"/demo/examples").then(r=>setExamples(r.examples)).catch(e=>setError(e.message));},[rooms]);
 return <details className="example-picker"><summary>Use your example photos</summary><p>{rooms?"Supplied room photos and reviewed location labels":"Seven supplied item photos"} · processed locally · confirm every detail.</p>{error&&<p role="alert">{error}</p>}<div className="example-gallery">{examples.map(e=><button type="button" key={e.id} aria-label={`Use example ${e.id}`} onClick={async()=>{try{const r=await fetch(e.url);if(!r.ok)throw new Error("Example photo unavailable");const file=new File([await r.blob()],e.id+".jpg",{type:"image/jpeg"});onSelect(file,e.url);}catch(err){setError(err instanceof Error?err.message:"Photo unavailable");}}}><img src={e.url} alt={e.title}/><small>{e.title}</small></button>)}</div></details>;
}

export function NearbySettings(){
 const data=useConnected(),[place,setPlace]=useState("Richard Weeks Hall");
 return <section className="demo-next"><p className="eyebrow">HELP A STUDENT NEARBY</p><h3>Where are you now?</h3><p>Choose a campus place to receive requests within 350 m. Your choice is private and expires in 24 hours.</p><label className="result-field"><span>Current area</span><select value={place} onChange={e=>setPlace(e.target.value)}>{campusPlaces.map(p=><option key={p.name}>{p.name}</option>)}</select></label><Button variant="secondary" disabled={data.busy} onClick={()=>data.run(async()=>{const p=campusPlaces.find(p=>p.name===place)!;await api("/me/nearby-location",{consent:true,label:p.name,longitude:p.coordinates[0],latitude:p.coordinates[1],radius_meters:350});await data.refresh();})}>Enable nearby alerts</Button>{data.nearby&&<><p className="form-hint left">Receiving alerts near {data.nearby.label}.</p><button className="text-button" onClick={()=>data.run(async()=>{await api("/me/nearby-location",{},"DELETE");await data.refresh();})}>Stop nearby alerts</button></>}</section>;
}

export function Notifications({go}:{go:(screen:any)=>void}){
 const data=useConnected(),[nearby,setNearby]=useState<any>(null);
 const open=(n:any)=>data.run(async()=>{
  await api(`/notifications/${n.id}/read`,{});data.setToast(null);
  if(n.kind==="MATCH"){const match=await api(`/matches/${n.resource_id}`);if(!match.active)throw new Error("This candidate is no longer active.");data.setMatch(match);go("ownerNotice");}
  else if(n.kind==="NEARBY")setNearby(await api(`/nearby-alerts/${n.resource_id}`));
  else if(["CLAIM","CLAIM_UPDATED","CLAIM_REVIEWED","HANDOFF","MESSAGE","RETURN"].includes(n.kind)){const claim=await data.openClaim(n.resource_id);go(["ACCEPTED","COMPLETED"].includes(claim.status)?"handoff":"ownership");}
  else go("items");
  await data.refresh();
 });
 return <main className="tab-page"><header className="title-header"><h1>Notifications</h1><p>Live updates for {data.user?.display_name.split(" ")[0]}</p></header><div className="safe-card"><Icon name="bell"/><p>The app checks for new alerts every 2 seconds while open. Each device has its own signed-in account.</p></div>{nearby&&<section className="demo-next"><p className="eyebrow">POTENTIAL ITEM NEARBY</p><h3>{nearby.title}</h3><p>{nearby.description}</p><p>Search near: {nearby.areas.join(", ")}</p><p className="form-hint left">{nearby.message}</p><Button onClick={()=>go("capture")}>I found something</Button><button className="text-button" onClick={()=>setNearby(null)}>Close request</button></section>}<button className="text-button" disabled={data.busy||!data.notifications.some(n=>!n.is_read)} onClick={()=>data.run(async()=>{for(const n of data.notifications.filter(n=>!n.is_read))await api(`/notifications/${n.id}/read`,{});data.setToast(null);await data.refresh();})}>Mark all read</button><div className="settings-card notification-list">{data.notifications.map(n=><button key={n.id} onClick={()=>open(n)}><span className="setting-icon"><Icon name={n.kind==="NEARBY"?"map":"bell"}/></span><span><strong>{n.kind==="MATCH"?"Potential match found":n.kind==="NEARBY"?"Potential item nearby":"Recovery update"}{!n.is_read&&<em className="unread-dot"/>}</strong><small>{n.message}</small></span><Icon name="chevron" size={17}/></button>)}{!data.notifications.length&&<p className="empty-note">No alerts yet. Keep this device open while another student posts.</p>}</div><Button variant="secondary" onClick={()=>go("home")}>Back home</Button></main>;
}

export function NotificationToast({go}:{go:(screen:any)=>void}){
 const data=useConnected();if(!data.toast)return null;
 return <aside className="live-alert" role="status"><button className="live-alert-content" onClick={()=>{data.setToast(null);go("notifications");}}><Icon name="bell" size={21}/><span><strong>{data.toast.kind==="MATCH"?"Potential match found":data.toast.kind==="NEARBY"?"Potential item nearby":"Recovery update"}</strong><small>{data.toast.message}</small></span></button><button aria-label="Dismiss notification" className="icon-button" onClick={()=>data.setToast(null)}><Icon name="x" size={16}/></button></aside>;
}

export function BrowseListings({go}:{go:(screen:any)=>void}){
 const data=useConnected(),[items,setItems]=useState<any[]>([]),[query,setQuery]=useState(""),[kind,setKind]=useState(""),[more,setMore]=useState(false),[error,setError]=useState("");
 useEffect(()=>{let active=true;api(`/listings?limit=30&type=${kind}&q=${encodeURIComponent(query)}`).then(r=>{if(active){setItems(r.listings);setMore(r.listings.length===30);setError("");}}).catch(e=>setError(e.message));return()=>{active=false;};},[query,kind]);
 return <main className="tab-page"><header className="title-header"><h1>Campus listings</h1><p>Public reports · sample data is labeled</p></header><label className="result-field"><span>Search listings</span><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Bottle, backpack, campus…"/></label><div className="tabs">{[["","All"],["LOST","Lost"],["FOUND","Found"]].map(([value,label])=><button className={kind===value?"active":""} key={value} onClick={()=>setKind(value)}>{label}</button>)}</div>{error&&<p role="alert">{error}</p>}<div className="stack item-list">{items.map(item=><article className="item-card large" key={item.id}><span className="item-emoji">{item.category==="bottle"?"◒":"⌁"}</span><div><strong>{item.title}</strong><small>{item.campus} · {item.location}</small><small>{item.type} · {categoryLabel(item.category)}</small></div>{item.type==="FOUND"&&item.status==="OPEN"&&item.creator_id!==data.user?.id&&<button className="text-button" onClick={()=>data.run(async()=>{await data.openListing(item.id);data.setMatch(null);go("ownership");})}>Claim</button>}</article>)}</div>{more&&<Button variant="secondary" onClick={()=>data.run(async()=>{const r=await api(`/listings?limit=30&offset=${items.length}&type=${kind}&q=${encodeURIComponent(query)}`);setItems([...items,...r.listings]);setMore(r.listings.length===30);})}>Load more</Button>}<Button variant="secondary" onClick={()=>go("home")}>Back home</Button></main>;
}
