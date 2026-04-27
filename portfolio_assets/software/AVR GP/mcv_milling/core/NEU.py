import { useState, useEffect, useRef } from "react";

const K = {
  orange:"#FF6600", orangeGlow:"#FF6600", orangeDim:"#7a3000", orangePale:"#FF660022",
  dark:"#0a0c0f", panel:"#0e1117", panelBord:"#1c2333", steel:"#1e2a3a", steelLight:"#2e3f55",
  dim:"#334155", mid:"#64748b", text:"#c8d6e5", textDim:"#4a5c70", white:"#f0f4f8",
  green:"#22c55e", greenDim:"#14532d", red:"#ef4444", redDim:"#450a0a",
  blue:"#3b82f6", blueDim:"#1e3a8a", cyan:"#06b6d4", cyanDim:"#164e63", yellow:"#eab308",
};

const PHASES = {
  FEED:    { color:K.green,  dim:K.greenDim,  label:"FEED" },
  CUT:     { color:K.red,    dim:K.redDim,    label:"CUT" },
  TRANSFER:{ color:K.blue,   dim:K.blueDim,   label:"TRANSFER" },
  MACHINE: { color:K.orange, dim:K.orangeDim, label:"MACHINE" },
  ROTATE:  { color:K.yellow, dim:"#422006",   label:"ROTATE" },
  EXIT:    { color:K.cyan,   dim:K.cyanDim,   label:"EXIT" },
};

const ROUND_STEPS = [
  { id:1, label:"Load Bar",           phase:"FEED",     active:["rail","bar","operator"],          time:"—",   desc:"Operator places 3200 mm EN AW-6063 T6 bar on V-roller rail. V-groove self-centers tube. Encoder registers bar ready." },
  { id:2, label:"Servo Feed",         phase:"FEED",     active:["rail","bar","feedaxis"],          time:"8s",  desc:"Servo-driven feed axis advances bar to programmed cut position. PLC calculates cut point based on required part length." },
  { id:3, label:"Trigger Saw",        phase:"CUT",      active:["saw","bar"],                      time:"10s", desc:"Robot sends digital I/O trigger to cold saw PLC. Carbide-tipped blade executes cut. Clean burr-free face on anodized surface." },
  { id:4, label:"Transfer to Clamp",  phase:"TRANSFER", active:["chute_in","clamp"],               time:"5s",  desc:"Cut part advances along rollers into open rotary clamp. Part slides into position. PLC confirms part-in-clamp via sensor." },
  { id:5, label:"Chamfer End 1",      phase:"MACHINE",  active:["robot","clamp","spindle","beam"], time:"15s", desc:"Robot positions spindle at 45° to clamp axis. Executes bore entry chamfer via circular interpolation. MQL active." },
  { id:6, label:"Rotate 180°",        phase:"ROTATE",   active:["clamp","robot"],                  time:"5s",  desc:"Robot signals clamp to flip 180°. Pneumatic rotary actuator indexes. Servo-locks at End 2 position." },
  { id:7, label:"Chamfer End 2",      phase:"MACHINE",  active:["robot","clamp","spindle","beam"], time:"15s", desc:"Robot repositions to End 2. Chamfer pass executed identically. Part fully complete." },
  { id:8, label:"Part Exit",          phase:"EXIT",     active:["clamp","chute_out","bin"],        time:"5s",  desc:"Clamp opens on robot I/O command. Finished part drops onto UHMW-lined gravity chute. Slides to labeled collection bin." },
];

const PROFILE_STEPS = [
  { id:1,  label:"Load Bar",               phase:"FEED",     active:["rail","bar","operator"],          time:"—",   desc:"Operator loads profile bar. V-groove geometry self-orients non-circular cross-section — 4-hole angular position is fixed and known." },
  { id:2,  label:"Servo Feed",             phase:"FEED",     active:["rail","bar","feedaxis"],          time:"8s",  desc:"Servo feed advances bar to cold saw cut position. Encoder tracks bar remainder for multi-part bar scheduling." },
  { id:3,  label:"Trigger Saw",            phase:"CUT",      active:["saw","bar"],                      time:"10s", desc:"Robot triggers cold saw. Clean cut executed. Profile tube angular orientation preserved throughout transfer." },
  { id:4,  label:"Transfer to Clamp",      phase:"TRANSFER", active:["chute_in","clamp"],               time:"5s",  desc:"Cut part enters clamp in known angular orientation. 4-hole pattern repeatable every cycle — no vision or probing needed." },
  { id:5,  label:"Chamfer 4× End 1",       phase:"MACHINE",  active:["robot","clamp","spindle","beam"], time:"20s", desc:"Robot moves to each of 4 hole positions sequentially. Countersink chamfer pass × 4 positions. (~5 sec per hole)" },
  { id:6,  label:"Thread Mill 4× End 1",   phase:"MACHINE",  active:["robot","clamp","spindle","beam"], time:"36s", desc:"Robot executes helical interpolation on each of 4 holes. Thread milled without axial wrist force. (~9 sec per hole)" },
  { id:7,  label:"Rotate 180°",            phase:"ROTATE",   active:["clamp","robot"],                  time:"5s",  desc:"Clamp flips 180°. End 2 presented to robot. Angular offset of hole pattern maintained — same coordinate frame." },
  { id:8,  label:"Chamfer 4× End 2",       phase:"MACHINE",  active:["robot","clamp","spindle","beam"], time:"20s", desc:"Robot chamfers all 4 holes on End 2. Identical sequence, mirrored axis." },
  { id:9,  label:"Thread Mill 4× End 2",   phase:"MACHINE",  active:["robot","clamp","spindle","beam"], time:"36s", desc:"Thread milling on End 2 complete. All 8 holes chamfered and threaded. Full profile cycle done." },
  { id:10, label:"Part Exit",              phase:"EXIT",     active:["clamp","chute_out","bin"],        time:"5s",  desc:"Clamp opens. Finished part (8× chamfered + threaded holes) exits via gravity chute to collection bin." },
];

function CellSVG({ active, phase, series }) {
  const ph = PHASES[phase] || PHASES.FEED;
  const on  = (el) => active.includes(el);
  const sc  = (el, yes=ph.color, no=K.dim) => on(el)?yes:no;
  const sf  = (el, yes, no="transparent") => on(el)?yes:no;
  const so  = (el, yes=1, no=0.28) => on(el)?yes:no;
  const glow= (el, col) => on(el)?`drop-shadow(0 0 5px ${col||ph.color}) drop-shadow(0 0 14px ${col||ph.color}44)`:"none";

  const rb = {x:545,y:305};
  const clampC = {x:400,y:195};
  const elbow = {x:498,y:262};
  const spTip = on("spindle") ? {x:clampC.x+36,y:clampC.y-10} : {x:elbow.x-28,y:elbow.y-38};

  return (
    <svg viewBox="0 0 760 430" style={{width:"100%",height:"100%",display:"block"}}>
      <defs>
        <pattern id="grid" width="22" height="22" patternUnits="userSpaceOnUse">
          <path d="M22 0L0 0 0 22" fill="none" stroke="#0d1520" strokeWidth="0.7"/>
        </pattern>
        <filter id="fOrange"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
        <filter id="fBlue"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
        <marker id="arrD" markerWidth="7" markerHeight="7" refX="5" refY="3.5" orient="auto">
          <polygon points="0 0,7 3.5,0 7" fill={K.dim}/>
        </marker>
        <marker id="arrA" markerWidth="7" markerHeight="7" refX="5" refY="3.5" orient="auto">
          <polygon points="0 0,7 3.5,0 7" fill={ph.color}/>
        </marker>
        <marker id="arrO" markerWidth="7" markerHeight="7" refX="5" refY="3.5" orient="auto">
          <polygon points="0 0,7 3.5,0 7" fill={K.orange}/>
        </marker>
      </defs>

      <rect width="760" height="430" fill={K.dark}/>
      <rect width="760" height="430" fill="url(#grid)"/>
      <rect x="18" y="18" width="726" height="396" rx="6" fill="none" stroke="#152215" strokeWidth="1.5" strokeDasharray="9,5"/>
      <text x="22" y="13" fill="#152215" fontSize="7.5" letterSpacing="3" fontFamily="monospace">SAFETY PERIMETER — CELL BOUNDARY</text>

      <line x1="272" y1="185" x2="298" y2="185" stroke={sc("saw",ph.color,K.textDim+"55")} strokeWidth="1.5" markerEnd={on("saw")?"url(#arrA)":"url(#arrD)"}/>
      <path d="M340 185 Q368 185 378 192" fill="none" stroke={sc("chute_in",ph.color,K.textDim+"44")} strokeWidth="1.5" markerEnd={on("chute_in")?"url(#arrA)":"url(#arrD)"} strokeDasharray={on("chute_in")?"none":"5,3"}/>
      <path d="M422 222 Q450 255 472 278" fill="none" stroke={sc("chute_out",ph.color,K.textDim+"44")} strokeWidth="1.5" markerEnd={on("chute_out")?"url(#arrA)":"url(#arrD)"} strokeDasharray={on("chute_out")?"none":"5,3"}/>

      {/* OPERATOR */}
      <g opacity={so("operator",1,0.38)}>
        <rect x="26" y="148" width="72" height="78" rx="4" fill={sf("operator","#0a1f0a","transparent")} stroke={sc("operator",K.green,K.steelLight)} strokeWidth="1.5"/>
        <circle cx="62" cy="170" r="9" fill="none" stroke={sc("operator",K.green,K.dim)} strokeWidth="1.5"/>
        <path d="M48 198 Q62 190 76 198 L76 214 L48 214 Z" fill="none" stroke={sc("operator",K.green,K.dim)} strokeWidth="1.5"/>
        <text x="62" y="227" fill={sc("operator",K.green,K.textDim)} fontSize="7.5" textAnchor="middle" fontFamily="monospace" letterSpacing="1">OPERATOR</text>
        {on("operator")&&<text x="62" y="238" fill="#86efac" fontSize="7" textAnchor="middle" fontFamily="monospace">● LOADING</text>}
      </g>

      {/* V-ROLLER RAIL */}
      <g opacity={so("rail",1,0.42)} style={{filter:glow("rail",K.green)}}>
        <rect x="100" y="174" width="200" height="24" rx="3" fill={sf("rail","#061a06",K.steel)} stroke={sc("rail",K.green,K.steelLight)} strokeWidth="1.8"/>
        <line x1="100" y1="178" x2="300" y2="178" stroke={sc("rail","#4ade8044",K.dim)} strokeWidth="1"/>
        {[114,132,150,168,186,204,222,240,258,276].map((x,i)=>(
          <g key={i}>
            <circle cx={x} cy="186" r="6" fill={sf("rail","#0d1f0d","#111827")} stroke={sc("rail","#4ade80",K.steelLight)} strokeWidth="1.2"/>
            <circle cx={x} cy="186" r="2" fill={sc("rail","#86efac",K.dim)}/>
            {on("rail")&&<circle cx={x} cy="186" r="4" fill="none" stroke={K.green+"44"} strokeWidth="1"><animate attributeName="r" values="2;6;2" dur={`${0.5+i*0.04}s`} repeatCount="indefinite"/><animate attributeName="opacity" values="0.6;0;0.6" dur={`${0.5+i*0.04}s`} repeatCount="indefinite"/></circle>}
          </g>
        ))}
        <path d="M104 175 L109 185 L114 175" fill="none" stroke={sc("rail","#4ade80",K.dim)} strokeWidth="1.2"/>
        <path d="M120 175 L125 185 L130 175" fill="none" stroke={sc("rail","#4ade80",K.dim)} strokeWidth="1.2"/>
        <text x="200" y="169" fill={sc("rail",K.green,K.textDim)} fontSize="8.5" textAnchor="middle" fontFamily="monospace" letterSpacing="2">V-ROLLER FEED RAIL</text>
        <text x="200" y="211" fill={sc("rail","#86efac",K.textDim)} fontSize="7" textAnchor="middle" fontFamily="monospace">3200 mm · SERVO ENCODER TRACKED</text>
      </g>

      {/* RAW BAR */}
      <g opacity={so("bar",1,0.15)} style={{filter:on("bar")?`drop-shadow(0 0 4px ${K.green})`:"none"}}>
        <rect x="104" y="180" width="188" height="12" rx="2" fill={sf("bar","#152615","#132030")} stroke={sc("bar","#86efac","#2a3a50")} strokeWidth="1.5"/>
        <text x="198" y="189" fill={sc("bar","#86efac","#3d5269")} fontSize="7" textAnchor="middle" fontFamily="monospace">EN AW-6063 T6 · ANODIZED · 3200 mm</text>
        {on("saw")&&<line x1="295" y1="178" x2="295" y2="194" stroke={K.red} strokeWidth="3" strokeLinecap="round"><animate attributeName="opacity" values="1;0.1;1" dur="0.25s" repeatCount="indefinite"/></line>}
      </g>

      {/* FEED AXIS */}
      <g opacity={so("feedaxis",1,0.12)}>
        <line x1="104" y1="228" x2="294" y2="228" stroke={sc("feedaxis",K.green,K.dim)} strokeWidth="1" markerEnd={on("feedaxis")?"url(#arrA)":"url(#arrD)"} markerStart={on("feedaxis")?"url(#arrA)":"url(#arrD)"}/>
        <line x1="104" y1="224" x2="104" y2="232" stroke={sc("feedaxis",K.green,K.dim)} strokeWidth="1"/>
        <text x="199" y="241" fill={sc("feedaxis",K.green,K.textDim)} fontSize="7" textAnchor="middle" fontFamily="monospace">SERVO FEED AXIS →</text>
      </g>

      {/* COLD SAW */}
      <g opacity={so("saw",1,0.42)} style={{filter:glow("saw",K.red)}}>
        <rect x="300" y="144" width="52" height="82" rx="4" fill={sf("saw","#1c0505",K.steel)} stroke={sc("saw",K.red,K.steelLight)} strokeWidth="2"/>
        <rect x="304" y="148" width="44" height="12" rx="2" fill={sf("saw","#2a0808","#111827")} stroke={sc("saw","#f8717144",K.dim)} strokeWidth="1"/>
        <text x="326" y="157" fill={sc("saw","#fca5a5",K.dim)} fontSize="6" textAnchor="middle" fontFamily="monospace">I/O CTRL</text>
        <circle cx="326" cy="194" r="24" fill={sf("saw","#2a0808","#0f1520")} stroke={sc("saw","#f87171",K.steelLight)} strokeWidth="1.5">
          {on("saw")&&<animateTransform attributeName="transform" type="rotate" from="0 326 194" to="360 326 194" dur="0.22s" repeatCount="indefinite"/>}
        </circle>
        {Array.from({length:18},(_,i)=>{
          const a=(i/18)*Math.PI*2, r1=20, r2=25;
          return <line key={i} x1={326+Math.cos(a)*r1} y1={194+Math.sin(a)*r1} x2={326+Math.cos(a)*r2} y2={194+Math.sin(a)*r2} stroke={sc("saw","#f8717188",K.steelLight)} strokeWidth="1.3"/>
        })}
        <line x1={318} y1={194} x2={334} y2={194} stroke={sc("saw","#f8717155",K.dim)} strokeWidth="1"/>
        <line x1={326} y1={186} x2={326} y2={202} stroke={sc("saw","#f8717155",K.dim)} strokeWidth="1"/>
        <circle cx="326" cy="194" r="4" fill={sc("saw",K.red,K.dim)}/>
        <text x="326" y="139" fill={sc("saw",K.red,K.textDim)} fontSize="8.5" textAnchor="middle" fontFamily="monospace" letterSpacing="1.5">COLD SAW</text>
        <text x="326" y="236" fill={sc("saw","#fca5a5",K.textDim)} fontSize="7" textAnchor="middle" fontFamily="monospace">CARBIDE · AL GRADE</text>
        {on("saw")&&<text x="326" y="247" fill={K.red} fontSize="7" textAnchor="middle" fontFamily="monospace">● CUTTING</text>}
      </g>

      {/* FEED CHUTE */}
      <g opacity={so("chute_in",1,0.28)} style={{filter:on("chute_in")?`drop-shadow(0 0 5px ${K.blue})`:"none"}}>
        <path d="M354 177 L376 177 L388 200 L366 200 Z" fill={sf("chute_in","#050f1f","#0e1420")} stroke={sc("chute_in",K.blue,K.steelLight)} strokeWidth="1.5"/>
        <text x="371" y="172" fill={sc("chute_in",K.blue,K.textDim)} fontSize="7" textAnchor="middle" fontFamily="monospace">FEED CHUTE</text>
        {on("chute_in")&&<circle r="4.5" fill={K.blue} opacity="0.85"><animate attributeName="cx" values="358;382" dur="0.55s" repeatCount="indefinite"/><animate attributeName="cy" values="180;198" dur="0.55s" repeatCount="indefinite"/><animate attributeName="opacity" values="0.85;0.2;0.85" dur="0.55s" repeatCount="indefinite"/></circle>}
      </g>

      {/* ROTARY CLAMP */}
      <g style={{filter:on("clamp")?`drop-shadow(0 0 12px ${ph.color}) drop-shadow(0 0 24px ${ph.color}33)`:"none"}}>
        <rect x="358" y="155" width="84" height="82" rx="5" fill={sf("clamp","#100a20","#0a0e16")} stroke={sc("clamp",ph.color,K.steelLight)} strokeWidth="2.2" opacity={so("clamp",1,0.38)}/>
        <circle cx="400" cy="196" r="34" fill={sf("clamp","#1a1135","#0f1421")} stroke={sc("clamp",ph.color,K.dim)} strokeWidth="1.8" opacity={so("clamp",1,0.35)}/>
        <circle cx="400" cy="196" r="24" fill={sf("clamp","#201545","#111827")} stroke={sc("clamp",ph.color+"88",K.steel)} strokeWidth="1.2" opacity={so("clamp",1,0.3)}/>
        {[90,210,330].map((deg,i)=>{
          const r=(deg*Math.PI)/180, jx=400+Math.cos(r)*18, jy=196+Math.sin(r)*18;
          return <g key={i} opacity={so("clamp",1,0.3)}>
            <rect x={jx-5} y={jy-4} width="10" height="8" rx="1" fill={sf("clamp","#2a1550","#1e293b")} stroke={sc("clamp",ph.color,K.steelLight)} strokeWidth="1.2" transform={`rotate(${deg+90} ${jx} ${jy})`}/>
          </g>
        })}
        {on("clamp")&&<>
          <circle cx="400" cy="196" r={series==="round"?10:9} fill="#1a2a3a" stroke="#4a6080" strokeWidth="1.5"/>
          {series==="profile"&&[0,90,180,270].map((a,i)=>{
            const r=(a*Math.PI)/180;
            return <circle key={i} cx={400+Math.cos(r)*6} cy={196+Math.sin(r)*6} r="2" fill={K.orange} style={{filter:`drop-shadow(0 0 3px ${K.orange})`}}/>
          })}
        </>}
        {on("clamp")&&phase==="ROTATE"&&<>
          <path d="M376 175 A30 30 0 0 1 424 175" fill="none" stroke={K.yellow} strokeWidth="2.5" markerEnd="url(#arrO)"><animate attributeName="stroke-dasharray" values="0,100;60,40" dur="0.7s" repeatCount="indefinite"/></path>
          <text x="400" y="162" fill={K.yellow} fontSize="9" textAnchor="middle" fontFamily="monospace" fontWeight="bold">↻ 180°</text>
        </>}
        <text x="367" y="200" fill={on("clamp")?ph.color:K.textDim} fontSize="9" fontFamily="monospace" fontWeight="bold" textAnchor="middle">E1</text>
        <text x="433" y="200" fill={on("clamp")?ph.color:K.textDim} fontSize="9" fontFamily="monospace" fontWeight="bold" textAnchor="middle">E2</text>
        <text x="400" y="250" fill={sc("clamp",ph.color,K.textDim)} fontSize="9" textAnchor="middle" fontFamily="monospace" letterSpacing="1.5" fontWeight="bold">ROTARY CLAMP</text>
        <text x="400" y="261" fill={sc("clamp",ph.color+"99",K.textDim)} fontSize="7" textAnchor="middle" fontFamily="monospace">PNEUMATIC · 180° INDEX · SERVO-LOCK</text>
      </g>

      {/* KUKA ROBOT */}
      <g>
        <path d={`M ${rb.x} ${rb.y} A 140 140 0 0 0 ${rb.x-115} ${rb.y-105}`} fill="none" stroke={on("robot")?K.orange+"18":"#0f1825"} strokeWidth="1.2" strokeDasharray="5,4"/>
        <path d={`M ${rb.x} ${rb.y} A 140 140 0 0 0 ${rb.x-125} ${rb.y-55}`} fill="none" stroke={on("robot")?K.orange+"18":"#0f1825"} strokeWidth="1.2" strokeDasharray="5,4"/>
        <ellipse cx={rb.x} cy={rb.y+10} rx="32" ry="10" fill="#00000055"/>
        <ellipse cx={rb.x} cy={rb.y+7} rx="30" ry="9" fill={sf("robot","#1c0e00","#0f1520")} stroke={sc("robot",K.orangeDim,K.steelLight)} strokeWidth="1.5" opacity={so("robot",1,0.45)}/>
        <rect x={rb.x-17} y={rb.y-18} width="34" height="25" rx="4" fill={sf("robot","#1c0e00","#111827")} stroke={sc("robot",K.orange,K.steelLight)} strokeWidth="2.2" opacity={so("robot",1,0.4)}/>
        <text x={rb.x} y={rb.y-5} fill={sc("robot",K.orange,K.steelLight)} fontSize="8" textAnchor="middle" fontFamily="monospace" fontWeight="900" letterSpacing="2">KUKA</text>
        <ellipse cx={rb.x} cy={rb.y-18} rx="15" ry="6" fill={sf("robot","#250f00","#0f1520")} stroke={sc("robot",K.orange,K.steelLight)} strokeWidth="1.5" opacity={so("robot",1,0.38)}/>
        <line x1={rb.x} y1={rb.y-18} x2={elbow.x} y2={elbow.y} stroke={sc("robot","#442200",K.steel)} strokeWidth="9" strokeLinecap="round" opacity={so("robot",1,0.35)}/>
        <line x1={rb.x} y1={rb.y-18} x2={elbow.x} y2={elbow.y} stroke={sc("robot",K.orange,K.steelLight)} strokeWidth="5" strokeLinecap="round" opacity={so("robot",1,0.38)}/>
        <line x1={rb.x} y1={rb.y-18} x2={elbow.x} y2={elbow.y} stroke={sc("robot","#ffaa66","#4a5c70")} strokeWidth="1.5" strokeLinecap="round" opacity={so("robot",1,0.2)}/>
        <circle cx={elbow.x} cy={elbow.y} r="9" fill={sf("robot","#250f00","#0e1520")} stroke={sc("robot",K.orange,K.steelLight)} strokeWidth="2" opacity={so("robot",1,0.4)}/>
        <circle cx={elbow.x} cy={elbow.y} r="4" fill={sc("robot",K.orange,K.dim)} opacity={so("robot")}/>
        <line x1={elbow.x} y1={elbow.y} x2={spTip.x} y2={spTip.y} stroke={sc("robot","#3a1800",K.steel)} strokeWidth="7" strokeLinecap="round" opacity={so("robot",1,0.35)}/>
        <line x1={elbow.x} y1={elbow.y} x2={spTip.x} y2={spTip.y} stroke={sc("robot",K.orange,K.steelLight)} strokeWidth="4" strokeLinecap="round" opacity={so("robot",1,0.38)}/>
        <circle cx={spTip.x} cy={spTip.y} r="10" fill={sf("robot","#2a1000","#0e1520")} stroke={sc("robot",K.orange,K.steelLight)} strokeWidth="2" opacity={so("robot",1,0.4)}/>
        {on("robot")&&[0,90,180,270].map((a,i)=>{
          const r=(a*Math.PI)/180;
          return <circle key={i} cx={spTip.x+Math.cos(r)*7} cy={spTip.y+Math.sin(r)*7} r="1.5" fill={K.orange} opacity="0.6"/>
        })}
        {on("spindle")&&<g style={{filter:`drop-shadow(0 0 8px ${K.orange})`}}>
          <rect x={spTip.x-7} y={spTip.y-22} width="14" height="22" rx="3" fill="#200f00" stroke={K.orange} strokeWidth="1.8"/>
          {[0,1,2].map(i=><line key={i} x1={spTip.x-7} y1={spTip.y-20+i*5} x2={spTip.x+7} y2={spTip.y-20+i*5} stroke={K.orange+"55"} strokeWidth="1"/>)}
          <line x1={spTip.x-4} y1={spTip.y-28} x2={spTip.x+4} y2={spTip.y-28} stroke={K.orange} strokeWidth="2.5" strokeLinecap="round">
            <animateTransform attributeName="transform" type="rotate" from={`0 ${spTip.x} ${spTip.y-22}`} to={`360 ${spTip.x} ${spTip.y-22}`} dur="0.12s" repeatCount="indefinite"/>
          </line>
          <path d={`M${spTip.x+7} ${spTip.y-12} L${spTip.x+16} ${spTip.y-22}`} fill="none" stroke="#60a5fa" strokeWidth="1.8" strokeLinecap="round"/>
          <circle cx={spTip.x+16} cy={spTip.y-22} r="2.5" fill="#60a5fa"><animate attributeName="opacity" values="0.8;0.2;0.8" dur="0.4s" repeatCount="indefinite"/></circle>
          {on("beam")&&<line x1={spTip.x} y1={spTip.y-28} x2={clampC.x+12} y2={clampC.y-2} stroke={K.orange} strokeWidth="2" strokeDasharray="4,3" opacity="0.7"><animate attributeName="opacity" values="0.7;0.15;0.7" dur="0.35s" repeatCount="indefinite"/></line>}
        </g>}
        <g opacity={so("robot",0.5,0.1)}>
          <path d={`M ${rb.x-22} ${rb.y-18} A 22 22 0 0 0 ${rb.x} ${rb.y-40}`} fill="none" stroke={K.orange+"55"} strokeWidth="1.2"/>
          <text x={rb.x-24} y={rb.y-36} fill={K.orange+"99"} fontSize="8" fontFamily="monospace">45°</text>
        </g>
        <text x={rb.x} y={rb.y+30} fill={sc("robot",K.orange,K.textDim)} fontSize="9.5" textAnchor="middle" fontFamily="monospace" fontWeight="bold" letterSpacing="1.5">KR IONTEC</text>
        <text x={rb.x} y={rb.y+43} fill={sc("robot","#ffaa55",K.textDim)} fontSize="8.5" textAnchor="middle" fontFamily="monospace">KR 70 R2100</text>
        <text x={rb.x} y={rb.y+55} fill={sc("robot",K.orange+"88",K.textDim)} fontSize="7" textAnchor="middle" fontFamily="monospace">±0.05mm · 70kg · 2100mm REACH</text>
      </g>

      {/* EXIT CHUTE */}
      <g opacity={so("chute_out",1,0.28)} style={{filter:on("chute_out")?`drop-shadow(0 0 5px ${K.cyan})`:"none"}}>
        <path d="M426 228 L452 228 L486 298 L460 298 Z" fill={sf("chute_out","#041519","#0a0e16")} stroke={sc("chute_out",K.cyan,K.steelLight)} strokeWidth="1.8"/>
        {[[432,228,464,298],[442,228,476,298]].map(([x1,y1,x2,y2],i)=><line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke={sc("chute_out",K.cyan+"44",K.dim)} strokeWidth="1" strokeDasharray="4,3"/>)}
        <text x="456" y="270" fill={sc("chute_out",K.cyan,K.textDim)} fontSize="8" textAnchor="middle" fontFamily="monospace">GRAVITY</text>
        <text x="456" y="281" fill={sc("chute_out",K.cyan,K.textDim)} fontSize="8" textAnchor="middle" fontFamily="monospace">CHUTE</text>
        <text x="456" y="311" fill={sc("chute_out","#67e8f9",K.textDim)} fontSize="7" textAnchor="middle" fontFamily="monospace">UHMW-LINED · ~25°</text>
        {on("chute_out")&&<circle r="5" fill={K.cyan} opacity="0.85"><animate attributeName="cx" values="432;474" dur="0.65s" repeatCount="indefinite"/><animate attributeName="cy" values="232;294" dur="0.65s" repeatCount="indefinite"/><animate attributeName="opacity" values="0.85;0.2;0.85" dur="0.65s" repeatCount="indefinite"/></circle>}
      </g>

      {/* BIN */}
      <g opacity={so("bin",1,0.32)} style={{filter:on("bin")?`drop-shadow(0 0 7px ${K.cyan})`:"none"}}>
        <path d="M460 300 L516 300 L508 360 L468 360 Z" fill={sf("bin","#041519","#090e14")} stroke={sc("bin",K.cyan,K.steelLight)} strokeWidth="2"/>
        <path d="M468 300 L468 292 L508 292 L508 300" fill="none" stroke={sc("bin",K.cyan,K.steelLight)} strokeWidth="1.5"/>
        <text x="488" y="332" fill={sc("bin",K.cyan,K.textDim)} fontSize="10" textAnchor="middle" fontFamily="monospace" letterSpacing="1" fontWeight="bold">BIN</text>
        <text x="488" y="344" fill={sc("bin","#67e8f9",K.textDim)} fontSize="7" textAnchor="middle" fontFamily="monospace">LABELED / VARIANT</text>
        {on("bin")&&<>
          <text x="488" y="374" fill={K.cyan} fontSize="9" textAnchor="middle" fontFamily="monospace" fontWeight="bold">✓ PART COMPLETE</text>
          <rect x="460" y="300" width="56" height="60" rx="0" fill="none" stroke={K.cyan} strokeWidth="1" opacity="0.3"><animate attributeName="opacity" values="0.3;0.8;0.3" dur="1s" repeatCount="indefinite"/></rect>
        </>}
      </g>

      {/* SPINDLE CALLOUT */}
      {on("spindle")&&<g>
        <rect x="595" y="135" width="148" height="80" rx="3" fill="#120800" stroke={K.orange} strokeWidth="1.5" style={{filter:`drop-shadow(0 0 6px ${K.orange}44)`}}/>
        <text x="605" y="151" fill={K.orange} fontSize="8" fontFamily="monospace" letterSpacing="2" fontWeight="bold">ELECTRO SPINDLE</text>
        <line x1="605" y1="156" x2="737" y2="156" stroke={K.orange+"44"} strokeWidth="1"/>
        {[["SPEED","20 – 40k RPM"],["TOOL","ER COLLET QUICK-SWAP"],["MQL","ACTIVE  💧"],["OP",series==="round"?"CHAMFER MILL":"CHAMFER + THREAD MILL"]].map(([l,v],i)=><g key={l}><text x="605" y={168+i*13} fill={K.textDim} fontSize="7" fontFamily="monospace">{l}:</text><text x="648" y={168+i*13} fill={l==="MQL"?K.blue:K.text} fontSize="7" fontFamily="monospace">{v}</text></g>)}
        <line x1="595" y1="176" x2={spTip.x+10} y2={spTip.y} stroke={K.orange+"55"} strokeWidth="1" strokeDasharray="4,3"/>
      </g>}

      <g opacity="0.35">
        <line x1="100" y1="272" x2="300" y2="272" stroke={K.mid} strokeWidth="1" markerEnd="url(#arrD)" markerStart="url(#arrD)"/>
        <text x="200" y="284" fill={K.textDim} fontSize="7" textAnchor="middle" fontFamily="monospace">3200 mm BAR FEED RANGE</text>
      </g>
      <text x="668" y="408" fill={K.dim} fontSize="7.5" fontFamily="monospace" textAnchor="middle">TOP-DOWN PLAN VIEW · NOT TO SCALE</text>
    </svg>
  );
}

export default function App() {
  const [series,  setSeries]  = useState("round");
  const [step,    setStep]    = useState(0);
  const [playing, setPlaying] = useState(false);
  const timer = useRef(null);

  const steps = series==="round" ? ROUND_STEPS : PROFILE_STEPS;
  const cur   = steps[step];
  const ph    = PHASES[cur.phase];

  useEffect(()=>{
    if(playing){
      timer.current = setInterval(()=>{
        setStep(s=>{ if(s>=steps.length-1){setPlaying(false);return s;} return s+1; });
      },2700);
    }
    return ()=>clearInterval(timer.current);
  },[playing,steps.length]);

  useEffect(()=>{ setStep(0); setPlaying(false); },[series]);

  const Btn = ({label,onClick,bc=K.steelLight,bg=K.steel,disabled=false,accent=false})=>(
    <button onClick={onClick} disabled={disabled} style={{
      padding:"6px 14px", background:bg, border:`1px solid ${bc}`,
      color:disabled?K.textDim:bc, fontSize:"9px", letterSpacing:"1.5px",
      cursor:disabled?"not-allowed":"pointer", borderRadius:"2px",
      fontFamily:"monospace", transition:"all 0.15s", opacity:disabled?0.38:1,
      boxShadow:accent&&!disabled?`0 0 8px ${bc}44`:"none",
    }}>{label}</button>
  );

  return (
    <div style={{background:K.dark,height:"100vh",display:"flex",flexDirection:"column",fontFamily:"monospace",color:K.text,overflow:"hidden"}}>
      {/* Header */}
      <div style={{background:K.panel,borderBottom:`2px solid ${K.panelBord}`,padding:"9px 20px",display:"flex",alignItems:"center",justifyContent:"space-between",flexShrink:0}}>
        <div style={{display:"flex",alignItems:"center",gap:"16px"}}>
          <div style={{background:K.orange,padding:"5px 12px",borderRadius:"2px",boxShadow:`0 0 12px ${K.orange}55`}}>
            <span style={{fontSize:"16px",fontWeight:"900",color:"#000",letterSpacing:"4px"}}>KUKA</span>
          </div>
          <div style={{width:"1px",height:"32px",background:K.steelLight}}/>
          <div>
            <div style={{fontSize:"7.5px",letterSpacing:"3px",color:K.mid,marginBottom:"2px"}}>NEUPRESS PNEUMATIC SYSTEMS · SS KUKA TEAM</div>
            <div style={{fontSize:"13px",fontWeight:"700",color:K.white,letterSpacing:"2px"}}>ROBOTIC MILLING CELL — PROCESS VISUALIZATION</div>
          </div>
        </div>
        <div style={{textAlign:"right",fontSize:"8px",color:K.textDim,letterSpacing:"1px",lineHeight:"1.9"}}>
          <div style={{color:K.mid}}>KR IONTEC · KR 70 R2100 · KRC5 COMPACT</div>
          <div>EN AW-6063 T6 · 17 VARIANTS · REV 2.0</div>
        </div>
      </div>

      {/* Series selector */}
      <div style={{background:"#0b0e14",borderBottom:`1px solid ${K.panelBord}`,padding:"7px 20px",display:"flex",alignItems:"center",gap:"10px",flexShrink:0}}>
        <span style={{fontSize:"8px",letterSpacing:"2px",color:K.textDim}}>PRODUCT SERIES:</span>
        {[{key:"round",color:K.cyan,label:"ROUND SERIES",sub:"CHAMFER ONLY · 9 VARIANTS · ~63 SEC · ~57 PCS/HR"},{key:"profile",color:K.orange,label:"PROFILE SERIES",sub:"CHAMFER + THREAD MILL · 8 VARIANTS · ~145 SEC · ~25 PCS/HR"}].map(s=>(
          <button key={s.key} onClick={()=>setSeries(s.key)} style={{padding:"7px 18px",cursor:"pointer",borderRadius:"2px",fontFamily:"monospace",background:series===s.key?s.color+"18":"transparent",border:`1.5px solid ${series===s.key?s.color:K.steelLight}`,color:series===s.key?s.color:K.mid,boxShadow:series===s.key?`0 0 10px ${s.color}33`:"none",transition:"all 0.2s"}}>
            <div style={{fontSize:"9px",fontWeight:"700",letterSpacing:"2px"}}>{s.label}</div>
            <div style={{fontSize:"6.5px",opacity:0.8,marginTop:"2px"}}>{s.sub}</div>
          </button>
        ))}
        <div style={{marginLeft:"auto",display:"flex",alignItems:"center",gap:"10px"}}>
          <div style={{fontSize:"8px",color:K.textDim}}>STEP {step+1} / {steps.length}</div>
          <div style={{width:"130px",height:"4px",background:K.steel,borderRadius:"2px"}}>
            <div style={{height:"100%",borderRadius:"2px",background:ph.color,width:`${((step+1)/steps.length)*100}%`,transition:"width 0.3s ease",boxShadow:`0 0 7px ${ph.color}`}}/>
          </div>
          <div style={{fontSize:"8px",padding:"3px 8px",background:ph.dim,border:`1px solid ${ph.color}`,color:ph.color,borderRadius:"2px",letterSpacing:"1.5px"}}>{ph.label}</div>
        </div>
      </div>

      {/* Body */}
      <div style={{flex:1,display:"grid",gridTemplateColumns:"1fr 284px",overflow:"hidden",minHeight:0}}>
        {/* LEFT */}
        <div style={{display:"flex",flexDirection:"column",overflow:"hidden"}}>
          <div style={{flex:1,padding:"10px 14px 4px",overflow:"hidden",minHeight:0}}>
            <CellSVG active={cur.active} phase={cur.phase} series={series}/>
          </div>
          <div style={{margin:"0 14px 8px",padding:"10px 14px",background:ph.dim,border:`1px solid ${ph.color}`,borderRadius:"3px",flexShrink:0}}>
            <div style={{display:"flex",alignItems:"center",gap:"10px",marginBottom:"5px"}}>
              <div style={{width:"8px",height:"8px",borderRadius:"50%",background:ph.color,boxShadow:`0 0 8px ${ph.color}`,flexShrink:0,animation:playing?"kpulse 0.8s ease-in-out infinite":"none"}}/>
              <span style={{fontSize:"11px",color:K.white,fontWeight:"700",flex:1,letterSpacing:"1px"}}>{cur.label}</span>
              <span style={{fontSize:"8px",color:K.mid,background:K.steel,padding:"2px 8px",borderRadius:"2px",flexShrink:0}}>{cur.time!=="—"?`EST. ${cur.time}`:"MANUAL STEP"}</span>
            </div>
            <div style={{fontSize:"10px",color:ph.color,lineHeight:"1.65",opacity:0.92}}>{cur.desc}</div>
          </div>
          <div style={{padding:"0 14px 10px",display:"flex",gap:"6px",alignItems:"center",flexShrink:0}}>
            <Btn label="⏮ RESET" onClick={()=>{setStep(0);setPlaying(false);}}/>
            <Btn label="◀ PREV" onClick={()=>setStep(s=>Math.max(0,s-1))} disabled={step===0}/>
            {playing?<Btn label="⏸ PAUSE" onClick={()=>setPlaying(false)} bc={K.red} bg={K.redDim}/>:<Btn label={step>=steps.length-1?"↺ REPLAY":"▶ PLAY"} onClick={()=>{if(step>=steps.length-1)setStep(0);setPlaying(true);}} bc={K.green} bg={K.greenDim} accent/>}
            <Btn label="NEXT ▶" onClick={()=>setStep(s=>Math.min(steps.length-1,s+1))} disabled={step===steps.length-1}/>
            <span style={{marginLeft:"6px",fontSize:"7.5px",color:K.textDim}}>AUTO: 2.7s/step</span>
          </div>
        </div>

        {/* RIGHT */}
        <div style={{display:"flex",flexDirection:"column",overflowY:"auto",background:K.panel,borderLeft:`1px solid ${K.panelBord}`}}>
          <div style={{padding:"12px 12px 6px"}}>
            <div style={{fontSize:"8px",letterSpacing:"3px",color:K.textDim,marginBottom:"8px",paddingBottom:"6px",borderBottom:`1px solid ${K.panelBord}`}}>OPERATION SEQUENCE</div>
            <div style={{display:"flex",flexDirection:"column",gap:"3px"}}>
              {steps.map((s,i)=>{
                const sph=PHASES[s.phase],isC=i===step,isDone=i<step;
                return <button key={s.id} onClick={()=>{setStep(i);setPlaying(false);}} style={{background:isC?sph.dim:isDone?"#06090f":"transparent",border:`1px solid ${isC?sph.color:isDone?K.panelBord:"#0f1520"}`,color:isC?sph.color:isDone?K.textDim+"88":K.textDim,padding:"7px 9px",textAlign:"left",cursor:"pointer",borderRadius:"2px",fontFamily:"monospace",fontSize:"8.5px",display:"flex",alignItems:"center",gap:"8px",transition:"all 0.12s",boxShadow:isC?`inset 2px 0 0 ${sph.color}`:"none"}}>
                  <div style={{width:"17px",height:"17px",borderRadius:"50%",flexShrink:0,display:"flex",alignItems:"center",justifyContent:"center",fontSize:"7px",fontWeight:"bold",background:isC?sph.color:isDone?K.steelLight:K.steel,color:isC?"#000":isDone?K.green:K.textDim,boxShadow:isC?`0 0 7px ${sph.color}`:"none"}}>{isDone?"✓":s.id}</div>
                  <span style={{flex:1,lineHeight:"1.35"}}>{s.label}</span>
                  <span style={{fontSize:"6px",letterSpacing:"1px",padding:"1px 4px",border:`1px solid ${sph.color}33`,color:sph.color+"77",borderRadius:"2px",flexShrink:0}}>{s.phase}</span>
                </button>
              })}
            </div>
          </div>
          <div style={{padding:"10px 12px",borderTop:`1px solid ${K.panelBord}`,marginTop:"auto"}}>
            <div style={{fontSize:"8px",letterSpacing:"3px",color:K.textDim,marginBottom:"8px"}}>PHASE LEGEND</div>
            {Object.entries(PHASES).map(([k,p])=>(
              <div key={k} style={{display:"flex",alignItems:"center",gap:"8px",marginBottom:"5px"}}>
                <div style={{width:"8px",height:"8px",borderRadius:"50%",background:p.color,flexShrink:0,boxShadow:cur.phase===k?`0 0 7px ${p.color}`:"none"}}/>
                <span style={{fontSize:"8px",letterSpacing:"1.5px",color:cur.phase===k?p.color:K.textDim,width:"72px"}}>{k}</span>
                <div style={{flex:1,height:"1px",background:p.color+(cur.phase===k?"66":"1a")}}/>
              </div>
            ))}
          </div>
          <div style={{padding:"10px 12px",borderTop:`1px solid ${K.panelBord}`}}>
            <div style={{fontSize:"8px",letterSpacing:"3px",color:K.textDim,marginBottom:"8px"}}>CELL COMPONENTS</div>
            {[[K.green,"V-ROLLER RAIL","3200mm · servo encoder"],[K.red,"COLD SAW","carbide blade · I/O trigger"],[K.blue,"FEED CHUTE","saw → clamp passive guide"],[ph.color,"ROTARY CLAMP","pneumatic · 180° · servo-lock"],[K.orange,"KR 70 R2100","45° offset · spindle on flange"],[K.cyan,"GRAVITY CHUTE","UHMW-lined · ~25° · bin exit"]].map(([c,name,detail])=>(
              <div key={name} style={{marginBottom:"7px",display:"flex",gap:"8px",alignItems:"flex-start"}}>
                <div style={{width:"3px",minHeight:"28px",background:c,flexShrink:0,borderRadius:"2px",opacity:0.75}}/>
                <div><div style={{fontSize:"8px",letterSpacing:"0.8px",color:K.text,marginBottom:"1px"}}>{name}</div><div style={{fontSize:"7px",color:K.textDim,lineHeight:"1.4"}}>{detail}</div></div>
              </div>
            ))}
          </div>
        </div>
      </div>
      <style>{`@keyframes kpulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:0.25;transform:scale(1.5)}} *{box-sizing:border-box;margin:0;padding:0} button:hover:not(:disabled){filter:brightness(1.2)} ::-webkit-scrollbar{width:4px} ::-webkit-scrollbar-track{background:#0a0c0f} ::-webkit-scrollbar-thumb{background:#1c2333;border-radius:2px}`}</style>
    </div>
  );
}