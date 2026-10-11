import {useState} from "react";
import LocationPicker from "./LocationPicker";
import {Icon} from "./ui";
import type {RoomLocation} from "./roomRecognition";

export default function RoomTest({go}:{go:(screen:"home")=>void}){
 const [room,setRoom]=useState<RoomLocation|null>(null);
 return <main className="tab-page"><header className="page-header"><button className="icon-button" aria-label="Go back" onClick={()=>go('home')}><Icon name="arrow"/></button><h1>Test a classroom</h1><span/></header><p className="subtext">Upload a room photo and review the suggestion. This test does not publish a listing.</p><LocationPicker value={room} onChange={setRoom} context="found"/>{room&&<p className="form-hint left">You selected this room. Use Change to compare another photo.</p>}</main>;
}
