import {createContext,useContext,useEffect,useRef,useState,type ReactNode} from "react";
import {api,ApiError,type User,type Listing,type Match,type Claim,type Handoff} from "./api";
import {campusPlaces} from "./mapData";
export const categoryCode=(name:string)=> /bottle|flask/i.test(name)?"bottle":/electronic|tablet|airpod|laptop|phone/i.test(name)?"electronics":/cloth|scarf|hoodie/i.test(name)?"clothing":/keys/i.test(name)?"keys":/wallet/i.test(name)?"wallet":/id|card/i.test(name)?"id_card":/bag|sleeve/i.test(name)?"bag":"other";
export const categoryLabel=(code:string)=>(({bottle:"Water bottle",electronics:"Electronics",clothing:"Clothing",keys:"Keys",wallet:"Wallet",id_card:"ID card",bag:"Bag"} as Record<string,string>)[code]||"Other");
export const sensitiveCategory=(c:string)=>["keys","wallet","id_card","financial_card","cash"].includes(c);
const ConnectedContext=createContext<ReturnType<typeof useData>|null>(null);
export function useConnected(){const data=useContext(ConnectedContext);if(!data)throw new Error("ConnectedProvider missing");return data;}
function useData(){
 const [user,setUser]=useState<User|null>(null),[mine,setMine]=useState<Listing[]>([]),[feed,setFeed]=useState<Listing[]>([]),[matches,setMatches]=useState<Match[]>([]),[claims,setClaims]=useState<Claim[]>([]),[notifications,setNotifications]=useState<any[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState(""),[selected,setSelected]=useState<Listing|null>(null),[match,setMatch]=useState<Match|null>(null),[claim,setClaim]=useState<Claim|null>(null),[handoff,setHandoff]=useState<Handoff|null>(null),[messages,setMessages]=useState<any[]>([]),[density,setDensity]=useState<any>({type:"FeatureCollection",features:[]}),[activity,setActivity]=useState<any>({confirmed_returns:0}),[nearby,setNearby]=useState<any>(null),[toast,setToast]=useState<any>(null);
 const [demoRole,setDemoRole]=useState<"owner"|"finder"|"helper">(()=>{const role=new URLSearchParams(location.search).get("role");return role==="finder"||role==="helper"?role:"owner";});
 const working=useRef(false),seen=useRef<Set<number>|null>(null),epoch=useRef(0),refreshRef=useRef<()=>Promise<void>>(async()=>{});
 async function refresh(){
  const generation=epoch.current;
  const [a,b,c,d,e,f,h,i,j]=await Promise.all([api("/auth/me"),api("/me/listings?limit=100"),api("/listings?limit=100"),api("/matches?limit=100"),api("/claims?limit=100"),api("/notifications?limit=100"),api("/maps/density"),api("/me/activity"),api("/me/nearby-location")]);
  if(generation!==epoch.current)return;
  setUser(a.user);setMine(b.listings);setFeed(c.listings);setMatches(d.matches.filter((m:Match)=>m.active));setClaims(e.claims);setNotifications(f.notifications);setDensity(h);setActivity(i);setNearby(j.location);
  if(seen.current){const incoming=f.notifications.find((n:any)=>!n.is_read&&!seen.current!.has(n.id));if(incoming)setToast(incoming);}
  seen.current=new Set(f.notifications.map((n:any)=>n.id));
  if(claim){const updated=e.claims.find((c:Claim)=>c.id===claim.id);if(updated)setClaim(updated);const [h,m]=await Promise.all([api(`/claims/${claim.id}/handoff`).catch(()=>null),api(`/claims/${claim.id}/messages`).catch(()=>({messages:[]}))]);if(generation===epoch.current){setHandoff(h);setMessages(m.messages);}}
 }
 refreshRef.current=refresh;
 async function run(task:()=>Promise<void>){if(working.current)return false;working.current=true;setBusy(true);setError("");try{await task();return true;}catch(e){setError(e instanceof Error?e.message:"Please try again.");return false;}finally{working.current=false;setBusy(false);}}
 useEffect(()=>{api("/auth/me").then(()=>refreshRef.current()).catch(()=>{});},[]);
 useEffect(()=>{if(!user)return;const t=setInterval(()=>{const generation=epoch.current;if(!working.current)refreshRef.current().catch(e=>{if(generation!==epoch.current)return;if(e instanceof ApiError&&e.status===401){clear();setUser(null);}else setError(e.message||"Connection interrupted; retry shortly.");});},2000);return()=>clearInterval(t);},[user?.id]);
 function clear(){epoch.current++;seen.current=null;setToast(null);setSelected(null);setMatch(null);setClaim(null);setHandoff(null);setMessages([]);}
 async function login(role=demoRole){clear();await api("/demo/session",{role});await refresh();}
 async function start(){clear();await api("/demo/reset",{});await refresh();}
 async function role(value:"finder"|"owner"|"helper"){clear();await api("/demo/switch",{role:value});setDemoRole(value);await refresh();}
 async function openListing(id:number){setSelected(await api(`/listings/${id}`));setClaim(null);setHandoff(null);}
 async function openClaim(id:number){const c=await api(`/claims/${id}`);setClaim(c);setHandoff(await api(`/claims/${id}/handoff`).catch(()=>null));setMessages((await api(`/claims/${id}/messages`)).messages);setSelected(await api(`/listings/${c.found_id}`).catch(()=>null));return c;}
 async function updatedClaim(id:number){await openClaim(id);await refresh();}
 async function upload(id:number,file:File){const d=new FormData();d.append("image",file);await api(`/listings/${id}/images`,d);}
 async function postFound(report:any){
  const c=categoryCode(report.category);const loc=report.location;
  const listing:Listing=await api("/listings",{type:"FOUND",title:report.title,category:c,attributes:{...report.attributes,color:report.color},description:report.hideDetails?(report.publicDescription||`${report.color} ${report.category}`):report.description,private_description:report.hideDetails?report.description:"",campus:loc.campus,location:loc.building,private_location:loc.room,visibility:sensitiveCategory(c)?"PRIVATE":"PUBLIC",occurred_at:new Date().toISOString()});
  setSelected(listing);
  if(report.file){try{await upload(listing.id,report.file);}catch(e){await refresh();throw new Error("Report saved, but the photo failed. Open My items to retry it. "+(e instanceof Error?e.message:""));}}
  setSelected(await api(`/listings/${listing.id}`));await refresh();
 }
 async function postLost(input:any){
  const c=categoryCode(input.category),known=input.location,best=input.places.find((p:any)=>p.high)||input.places[0];
  const area=known?.building||best?.name?.split(",")[0]||"";
  const campus=known?.campus||(/busch|hill|wright|allison|richard|weeks/i.test(area)?"Busch":/livingston|beck|tillett/i.test(area)?"Livingston":/cook|douglass|hickman/i.test(area)?"Cook/Douglass":"College Ave");
  const listing:Listing=await api("/listings",{type:"LOST",title:input.title,category:c,attributes:{...input.attributes,color:input.color},description:input.publicDescription||input.color+" "+input.category,private_description:input.description,campus,location:area,private_location:known?.room||input.places.map((p:any)=>`${p.time}: ${p.name}`).join("; ").slice(0,300),visibility:sensitiveCategory(c)||input.sensitive?"PRIVATE":"PUBLIC",occurred_at:new Date(input.lastSeen).toISOString()});
  setSelected(listing);
  const selectedPlaces=[...input.places];
  if(known){const place=campusPlaces.find(p=>p.name===known.building);if(place&&!selectedPlaces.some((p:any)=>p.name.startsWith(place.name)))selectedPlaces.push({name:place.name,high:true});}
  const areas=selectedPlaces.map((p:any)=>{const loc=campusPlaces.find(x=>p.name.startsWith(x.name));return loc?{label:loc.name,latitude:loc.coordinates[1],longitude:loc.coordinates[0],priority:p.high?3:1,share_public:input.sharePublic&&!sensitiveCategory(c)&&!input.sensitive}:null;}).filter(Boolean).slice(0,20);
  if(areas.length)await api(`/listings/${listing.id}/potential-locations`,{locations:areas});
  if(input.file)await upload(listing.id,input.file);
  await refresh();
 }
 return {user,mine,feed,matches,claims,notifications,busy,error,setError,selected,setSelected,match,setMatch,claim,setClaim,handoff,messages,density,activity,nearby,toast,setToast,demoRole,setDemoRole,aiMode:"local",run,refresh,start,login,role,openListing,openClaim,updatedClaim,postFound,postLost,upload};
}
export function ConnectedProvider({children}:{children:ReactNode}){const value=useData();return <ConnectedContext.Provider value={value}>{children}</ConnectedContext.Provider>;}
