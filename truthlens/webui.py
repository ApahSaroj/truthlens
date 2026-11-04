"""The single-page web app served at "/": start, checking and results states, no build step, no CDN.

Vanilla HTML/CSS/JS. Every string that comes from the user's draft or from evidence is written with
textContent / createTextNode (never innerHTML); the only innerHTML is for the constant SVG icons below.
Design guidance: UI UX Pro Max (MIT), Minimalism & Swiss style, trust palette, academic type pairing.
"""

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 32 32%27 fill=%27none%27 stroke=%27%231E3A5F%27 stroke-width=%272.6%27 stroke-linecap=%27round%27 stroke-linejoin=%27round%27%3E%3Ccircle cx=%2714%27 cy=%2714%27 r=%279.5%27/%3E%3Cpath d=%27m21 21 7 7M10 14.2l3 3 5.5-6%27/%3E%3C/svg%3E">
<title>TruthLens · Check every fact in your draft</title>
<style>
:root{
 --bg:#F5F4F0;--surface:#FFFFFF;--raised:#EFEDE7;--line:#DCD8CE;--line2:#C9C4B8;
 --ink:#0F172A;--ink2:#334155;--muted:#52606F;
 --primary:#1E3A5F;--primary-h:#152C49;--on-primary:#FFFFFF;--ring:#1E3A5F;
 --con:#B42318;--conbg:#FCE4DF;--part:#8A4B00;--partbg:#FBEBCF;--unv:#475569;--unvbg:#E6E9EE;
 --sup:#166534;--supbg:#DCEFE1;--dat:#3D5A80;--datbg:#E3E9F2;--meter:#16A34A;--fixed:#0F5132;
 --sans:"Atkinson Hyperlegible",system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
 --serif:"Crimson Pro",Charter,"Bitstream Charter","Iowan Old Style","Source Serif 4",Georgia,"Noto Serif","DejaVu Serif",serif;
 --mono:ui-monospace,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace;
 --ease:cubic-bezier(.23,1,.32,1);--ease-io:cubic-bezier(.77,0,.175,1);--ease-drawer:cubic-bezier(.32,.72,0,1);--shadow-sheet:0 -8px 32px rgba(15,23,42,.16)}
*{box-sizing:border-box}html,body{margin:0}
body{font:16px/1.5 var(--sans);background:var(--bg);color:var(--ink);font-variant-numeric:tabular-nums;-webkit-font-smoothing:antialiased}
a{color:var(--primary);text-underline-offset:3px}
button,[role=button],[role=tab],summary,label.btn{cursor:pointer}
button{font:inherit;color:inherit}
:focus-visible{outline:3px solid var(--ring);outline-offset:2px;border-radius:6px}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
svg.i{width:20px;height:20px;flex:none;stroke:currentColor;fill:none;stroke-width:1.75;stroke-linecap:round;stroke-linejoin:round}
[hidden]{display:none!important}

/* header */
.top{display:flex;align-items:center;justify-content:space-between;gap:16px;max-width:1240px;margin:0 auto;padding:20px 32px}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:18px;color:var(--ink);text-decoration:none;letter-spacing:-.01em}
.brand svg{width:28px;height:28px;color:var(--primary)}
.top nav{display:flex;align-items:center;gap:8px}
.link{font-size:15px;color:var(--ink2);text-decoration:none;padding:10px 12px;border-radius:8px}
.link:hover{background:var(--raised);color:var(--ink)}

/* buttons */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:44px;padding:0 18px;border-radius:10px;border:1px solid transparent;
 font:600 15px/1 var(--sans);text-decoration:none;transition:background-color .15s ease,border-color .15s ease,transform .16s var(--ease),color .15s ease}
.btn:active,.chip:active:not([disabled]),.iconbtn:active,.tab:active{transform:scale(.97)}
.btn.primary{background:var(--primary);color:var(--on-primary)}.btn.primary:hover{background:var(--primary-h)}
.btn.ghost{background:var(--surface);border-color:var(--line2);color:var(--ink)}.btn.ghost:hover{background:var(--raised);border-color:var(--muted)}
.btn.quiet{background:transparent;color:var(--ink2);padding:0 12px}.btn.quiet:hover{background:var(--raised);color:var(--ink)}
.btn svg.i{width:18px;height:18px}
.btn[disabled]{opacity:.5;cursor:not-allowed}

/* START */
.view{max-width:1240px;margin:0 auto;padding:0 32px 64px}
#start{max-width:1140px;padding-top:40px}
.startgrid{display:grid;grid-template-columns:300px minmax(0,1fr);gap:32px;align-items:start}
.startgrid>.side{position:sticky;top:16px;order:0}.startgrid>.startmain{order:1;min-width:0}
.side details.key{margin-top:0;border-top:0;padding:16px;background:var(--surface);border:1px solid var(--line);border-radius:16px}
.side .keyrow{grid-template-columns:minmax(0,1fr)}

h1{font:600 44px/1.1 var(--serif);letter-spacing:-.015em;margin:0;text-wrap:balance}
.lede{font-size:18px;line-height:1.55;color:var(--ink2);margin:14px 0 32px;max-width:36em}
.card{background:var(--surface);border:1px solid var(--line);border-radius:16px}
.tabs{display:flex;gap:4px;padding:6px;border-bottom:1px solid var(--line)}
.tab{flex:1;display:flex;align-items:center;justify-content:center;gap:8px;min-height:44px;border:0;background:transparent;border-radius:10px;font-weight:600;color:var(--muted);transition:background-color .18s var(--ease),color .18s var(--ease)}
.tab:hover{color:var(--ink);background:var(--raised)}
.tab[aria-selected=true]{background:var(--raised);color:var(--ink)}
.pane{padding:20px}
#drop{display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;gap:6px;min-height:240px;padding:28px;border:2px dashed var(--line2);border-radius:12px;background:#FBFAF7;transition:border-color .18s var(--ease),background-color .18s var(--ease)}
#drop:hover{border-color:var(--primary);background:#F3F5F8}
#drop.over{border-color:var(--primary);background:#E9EEF5}
#drop .ic{display:grid;place-items:center;width:56px;height:56px;border-radius:50%;background:#E9EEF5;color:var(--primary);margin-bottom:8px}
#drop .ic svg{width:26px;height:26px}
#drop b{font-size:18px}#drop span{color:var(--muted);font-size:15px}
#drop .btn{margin-top:14px;color:var(--ink);font-size:15px}
textarea{display:block;width:100%;min-height:220px;padding:14px 16px;border:1px solid var(--line2);border-radius:12px;background:#FBFAF7;color:var(--ink);font:17px/1.6 var(--serif);resize:vertical;transition:border-color .18s var(--ease),box-shadow .18s var(--ease)}
textarea:focus{outline:none;border-color:var(--primary);box-shadow:0 0 0 3px rgba(30,58,95,.18)}
.row{display:flex;flex-wrap:wrap;align-items:center;gap:12px;margin-top:14px}
.row .hint{color:var(--muted);font-size:14px}
.or{display:flex;align-items:center;gap:16px;margin:24px 0 0;color:var(--muted);font-size:15px}
.or::before,.or::after{content:"";flex:1;height:1px;background:var(--line)}
.sample{display:flex;justify-content:center;margin-top:16px}
.err{display:flex;gap:10px;align-items:flex-start;margin-top:16px;padding:12px 14px;border-radius:10px;background:var(--conbg);color:#7A1A10;font-size:15px}
.err svg{margin-top:1px}
details.key{margin-top:28px;border-top:1px solid var(--line);padding-top:16px}
details.key summary{display:inline-flex;align-items:center;gap:8px;min-height:44px;color:var(--ink2);font-size:15px;list-style:none;border-radius:8px;padding:0 4px}
details.key summary::-webkit-details-marker{display:none}
details.key summary:hover{color:var(--ink)}
details.key summary .chev{transition:transform .2s var(--ease)}details.key[open] summary .chev{transform:rotate(90deg)}
.keybody{padding:4px 4px 0}
.keybody p{font-size:14px;line-height:1.55;color:var(--muted);margin:4px 0 12px;max-width:44em}
.keyrow{display:grid;grid-template-columns:180px minmax(0,1fr);gap:12px}
.keyrow label{display:block;font-size:14px;font-weight:600;color:var(--ink2);margin-bottom:6px}
select,input#key,input#dgkey,input#llmmodel,input#llmbase{width:100%;height:44px;padding:0 12px;border:1px solid var(--line2);border-radius:10px;background:var(--surface);color:var(--ink);font:inherit}
select:focus,input#key:focus,input#dgkey:focus,input#llmmodel:focus,input#llmbase:focus{outline:none;border-color:var(--primary);box-shadow:0 0 0 3px rgba(30,58,95,.18)}
.foot{font-size:14px;color:var(--muted);margin:20px 0 0;text-align:center}
.live{font-size:13px;color:var(--muted);margin:6px 0 0;text-align:center;text-wrap:balance}
.keyrow+.keyrow{margin-top:12px}
.keyrow.one{grid-template-columns:minmax(0,1fr)}.keyrow.two{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
.cmpout{margin-top:16px}.cmptab{border-collapse:collapse;font-size:13px;margin:6px 0 10px}.cmptab td,.cmptab th{border-top:1px solid #e3ddd2;padding:3px 8px;text-align:left}.cmpsec details{margin:4px 0}.cmpsec summary{cursor:pointer;font-size:14px}.cmphead{font-weight:600;margin:0 0 8px}.cmpsec h3{font-size:15px;margin:14px 0 6px}.cmpsec ul{margin:0;padding-left:20px}.cmpsec li{font-size:14px;line-height:21px;margin:4px 0}
#pane-cmp>.hint{color:var(--muted);font-size:14px;margin:0 0 14px}

/* CHECKING */
#checking{max-width:560px;padding-top:72px}
#checking .card{padding:32px}
#checking h2{font:600 30px/1.2 var(--serif);margin:0 0 6px}
#checking .what{color:var(--muted);margin:0 0 28px;overflow-wrap:anywhere}
.steps{list-style:none;margin:0;padding:0;display:grid;gap:4px}
.steps li{display:flex;align-items:center;gap:14px;min-height:48px;padding:0 12px;border-radius:10px;color:var(--muted);transition:background-color .22s ease,color .22s ease}
.steps .dot{display:grid;place-items:center;width:28px;height:28px;border-radius:50%;border:2px solid var(--line2);flex:none;transition:background-color .2s ease,border-color .2s ease}
.steps .dot svg{width:16px;height:16px;stroke-width:2.5;opacity:0;transform:scale(.6);transition:opacity .18s var(--ease),transform .22s var(--ease)}
.steps li.active{background:#EEF2F7;color:var(--ink);font-weight:600}
.steps li.active .dot{border-color:var(--primary);border-top-color:transparent;animation:spin .8s linear infinite}
.steps li.done{color:var(--ink2)}
.steps li.done .dot{background:var(--primary);border-color:var(--primary);color:#fff}.steps li.done .dot svg{opacity:1;transform:none}
@keyframes spin{to{transform:rotate(360deg)}}
.elapsed{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:24px;padding-top:16px;border-top:1px solid var(--line);color:var(--muted);font-size:14px}

/* RESULTS */
#results{padding-top:8px}
.summary{display:grid;grid-template-columns:auto minmax(0,1fr) auto;grid-template-areas:"m h a" "m c a";column-gap:28px;row-gap:14px;align-items:center;padding:24px 28px}
.meter{grid-area:m}.headline{grid-area:h;align-self:end}.chips{grid-area:c;align-self:start}.actions{grid-area:a}
.meter{position:relative;width:128px;height:128px}
.meter svg{width:128px;height:128px;transform:rotate(-90deg)}
.meter circle{fill:none;stroke-width:10}
.meter .track{stroke:#E7E4DC}.meter .val{stroke:var(--meter);stroke-linecap:round;transition:stroke-dashoffset .9s var(--ease)}
.meter .num{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}
.meter .num b{font:700 34px/1 var(--sans);letter-spacing:-.02em}.meter .num span{font-size:12px;color:var(--muted);margin-top:4px;text-transform:uppercase;letter-spacing:.06em}
.headline h2{font:600 26px/1.25 var(--serif);margin:0;text-wrap:balance}
.headline p{margin:6px 0 0;color:var(--ink2)}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{display:inline-flex;align-items:center;gap:7px;min-height:44px;white-space:nowrap;padding:0 12px 0 10px;border-radius:999px;border:1px solid var(--line2);background:var(--surface);font-size:15px;font-weight:600;transition:background-color .15s ease,border-color .15s ease,box-shadow .15s ease,transform .16s var(--ease)}
.chip .sw{width:12px;height:12px;border-radius:3px;flex:none}
.chip b{font-variant-numeric:tabular-nums}
.chip:hover:not([disabled]){border-color:var(--ink2)}
.chip[aria-pressed=true]{border-color:var(--ink);box-shadow:inset 0 0 0 1px var(--ink);background:var(--raised)}
.chip[disabled]{opacity:.55;cursor:default}
.chip.con .sw{background:var(--con)}.chip.part .sw{background:#C27A00}.chip.unv .sw{background:var(--unv)}.chip.dat .sw{background:var(--dat)}.chip.unvr .sw{background:transparent;border:2px solid var(--unv)}.chip.sup .sw{background:var(--sup)}
.actions{display:flex;flex-direction:column;gap:8px;min-width:200px}
.actions .btn{white-space:nowrap}.opt{margin-left:-3px}
.actions .btn{justify-content:flex-start}
.work{display:grid;grid-template-columns:minmax(0,1fr) 420px;gap:24px;margin-top:24px;align-items:start}
.doc{padding:36px 44px 40px}
.doc .dochead{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:8px 16px;margin-bottom:20px;padding-bottom:14px;border-bottom:1px solid var(--line)}
.doc .dochead h3{margin:0;font-size:15px;font-weight:600;color:var(--ink2);overflow-wrap:anywhere}
.doc .dochead span{font-size:14px;color:var(--muted)}
.draft{font:19px/1.75 var(--serif);color:var(--ink);max-width:68ch;overflow-wrap:anywhere}
.draft p{margin:0 0 1em}
.draft p.trow{font-family:var(--sans);font-size:15px;line-height:1.6;margin:0;padding:8px 10px;border-top:1px solid var(--line);color:var(--ink2)}
.draft p.trow+p:not(.trow){margin-top:1em}
.s{border-radius:3px;padding:1px 1px;-webkit-box-decoration-break:clone;box-decoration-break:clone;cursor:pointer;transition:background-color .15s ease,box-shadow .15s ease,opacity .15s ease;text-underline-offset:5px;text-decoration-skip-ink:none}
.s.con{background:var(--conbg);text-decoration:underline wavy var(--con) 1.5px}
.s.part{background:var(--partbg);text-decoration:underline dotted #C27A00 2px}
.s.unv{background:var(--unvbg);text-decoration:underline dashed var(--unv) 1px}
.s.dat{background:var(--datbg);text-decoration:underline dotted var(--dat) 1px}
.s.sup{background:var(--supbg)}
.s:hover{box-shadow:0 0 0 2px var(--line2)}
.s.sel{box-shadow:0 0 0 2px var(--ink)}
.s.fixed{background:#D3EFE0;text-decoration:none;box-shadow:inset 0 -2px 0 var(--sup)}
.s.fixed.sel{box-shadow:0 0 0 2px var(--ink)}
.s:focus-visible{outline:3px solid var(--ring);outline-offset:2px}
.mk{font:700 11px/1 var(--mono);vertical-align:super;margin-left:2px;color:var(--muted)}
.mk.con{color:var(--con)}.mk.part{color:var(--part)}.mk.unv{color:var(--unv)}.mk.dat{color:var(--dat)}.mk.sup{color:var(--sup)}
.draft[data-filter] .s:not(.match){background:transparent;text-decoration:none;box-shadow:none;opacity:.55}
.draft[data-filter] .mk:not(.match){opacity:.4}
.tip{font-size:14px;color:var(--muted);margin:24px 0 0;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
kbd{font:600 12px/1 var(--mono);padding:3px 6px;border:1px solid var(--line2);border-bottom-width:2px;border-radius:5px;background:var(--surface);color:var(--ink2)}

/* panel */
.panel{position:sticky;top:16px;max-height:calc(100vh - 32px);overflow:auto;overscroll-behavior:contain}
.panel .inner{padding:22px 24px 24px}
.ph{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:14px}
.ph .pos{font-size:14px;color:var(--muted)}
.ph .nav{display:flex;gap:4px}
.iconbtn{display:grid;place-items:center;width:44px;height:44px;border-radius:10px;border:1px solid var(--line);background:var(--surface);color:var(--ink2);transition:background-color .18s var(--ease),border-color .18s var(--ease)}
.iconbtn:hover{background:var(--raised);border-color:var(--line2);color:var(--ink)}
.iconbtn svg.i{width:18px;height:18px}
.close{display:none}
.finding+.finding{margin-top:24px;padding-top:20px;border-top:1px solid var(--line)}
.verdict{display:inline-flex;align-items:center;gap:8px;padding:6px 12px 6px 8px;border-radius:999px;font-weight:700;font-size:15px}
.verdict.con{background:var(--conbg);color:var(--con)}.verdict.part{background:var(--partbg);color:var(--part)}
.verdict.unv{background:var(--unvbg);color:var(--unv)}.verdict.dat{background:var(--datbg);color:var(--dat)}.verdict.sup{background:var(--supbg);color:var(--sup)}.verdict.op{background:var(--raised);color:var(--ink2)}
.meta{font-size:13px;color:var(--muted);margin:10px 0 0}
.plain{font-size:15px;color:var(--ink2);margin:12px 0 0}
.why{font-size:16px;line-height:1.55;margin:10px 0 0;color:var(--ink)}
.blockh{font-size:12px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);margin:22px 0 8px}
.warns{list-style:none;margin:0;padding:0;display:grid;gap:8px}
.warns li span{min-width:0;overflow-wrap:anywhere}
.warns li{display:flex;gap:10px;font-size:14px;line-height:1.5;color:var(--ink2);padding:10px 12px;border-radius:10px;background:#FBF6EA;border:1px solid #EFE2C2}
.warns li svg{color:var(--part);width:18px;height:18px;margin-top:1px}
blockquote{margin:0 0 10px;padding:12px 14px;background:#F6F5F1;border-radius:10px;font:16px/1.55 var(--serif);color:var(--ink);overflow-wrap:anywhere}
blockquote.q{background:#EEF2F7}
.src{display:flex;flex-wrap:wrap;align-items:center;gap:4px 10px;margin-top:8px;font:13px/1.45 var(--sans);color:var(--muted)}
.src a{display:inline-flex;align-items:center;gap:4px;font-weight:600;min-height:32px}
.src a svg.i{width:14px;height:14px}
.stype{display:inline-flex;align-items:center;min-height:22px;padding:0 8px;border-radius:999px;background:var(--surface);border:1px solid var(--line2);color:var(--ink2);font:700 12px/1 var(--sans);letter-spacing:.02em;white-space:nowrap}
.asof{color:var(--ink2)}
.cite{display:inline-flex;align-items:center;gap:4px;min-height:32px;padding:0 8px;margin-left:-8px;border:0;border-radius:8px;background:transparent;color:var(--primary);font:600 13px/1 var(--sans);transition:background-color .15s ease}
.cite:hover{background:var(--raised)}.cite svg.i{width:14px;height:14px}
.banner{margin:10px 0 0;padding:8px 12px;border-radius:10px;background:var(--partbg);color:var(--ink);font-size:14px;line-height:1.45}
.modeline{margin:8px 0 0;font-size:14px;color:var(--ink2);display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.modeline .tag{font-weight:600;color:var(--ink)}
.bdetails{margin:6px 0 0;font-size:13px;color:var(--ink2)}.bdetails summary{cursor:pointer}.bdetails ul{margin:4px 0 0 18px;padding:0}
.stype.nlv{color:var(--part);border-color:var(--part);font-weight:600}.tagx{display:inline-block;padding:0 8px;border-radius:999px;background:var(--surface);border:1px solid var(--line2);font:600 12px/22px var(--sans);color:var(--ink2)}
.failp b{color:var(--con)}
.super{display:flex;gap:10px;font-size:14px;line-height:1.5;color:var(--ink);padding:12px 14px;border-radius:10px;background:var(--partbg);margin-top:14px}
.super svg{color:var(--part);width:18px;height:18px;margin-top:1px}.super b{font-weight:700}
.super span{min-width:0;overflow-wrap:anywhere}
.cites{list-style:none;margin:0;padding:0;font-size:14px;color:var(--ink2);display:grid;gap:6px;overflow-wrap:anywhere}
.cites b.bad{color:var(--con)}.cites b.ok{color:var(--sup)}
.fix{border:1px solid var(--line2);border-radius:12px;overflow:hidden}
.fix .ft{padding:14px 16px;font:17px/1.6 var(--serif);overflow-wrap:anywhere}
.fix del{color:var(--con);text-decoration:line-through 1.5px;background:var(--conbg);border-radius:2px}
.fix del+ins{margin-left:.3em}
.fix ins{color:var(--sup);text-decoration:none;font-weight:700;background:var(--supbg);border-radius:2px;padding:0 1px}
.fix .fa{display:flex;flex-wrap:wrap;gap:8px;padding:12px 16px;background:#FBFAF7;border-top:1px solid var(--line)}
.fix .fa .btn{min-height:40px;padding:0 14px;font-size:14px}
.fix .ok{display:inline-flex;align-items:center;gap:6px;color:var(--sup);font-weight:700;font-size:14px;margin-right:auto}
.empty{padding:28px 24px;text-align:center;color:var(--muted)}
.empty .ic{display:grid;place-items:center;width:48px;height:48px;border-radius:50%;background:var(--raised);margin:0 auto 12px;color:var(--ink2)}
.empty b{display:block;color:var(--ink);font-size:17px;margin-bottom:4px}
.scrim{display:none}
.toast{position:fixed;left:50%;bottom:24px;transform:translate(-50%,16px);opacity:0;pointer-events:none;background:var(--ink);color:#fff;padding:12px 18px;border-radius:10px;font-size:15px;font-weight:600;white-space:nowrap;max-width:calc(100% - 32px);overflow:hidden;text-overflow:ellipsis;transition:opacity .2s var(--ease),transform .2s var(--ease);z-index:60}
.toast.on{opacity:1;transform:translate(-50%,0)}
.note{font-size:14px;color:var(--muted);margin:28px 0 0;text-align:center}
.mobilehint{display:none}

/* view transitions */
.view.enter{animation:rise .24s var(--ease)}
@keyframes rise{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.finding.in{animation:fadein .16s var(--ease)}@keyframes fadein{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}

@media (max-width:1100px){
 .summary{grid-template-columns:auto minmax(0,1fr);grid-template-areas:"m h" "m c" "a a"}
 .actions{flex-direction:row;flex-wrap:wrap;min-width:0}
 .work{grid-template-columns:minmax(0,1fr) 360px}
 .doc{padding:28px 28px 32px}
}
@media (max-width:860px){
 .top{padding:14px 16px}.view{padding:0 16px 48px}
 #start{padding-top:16px}h1{font-size:34px}.lede{font-size:17px;margin-bottom:24px}
 #checking{padding-top:24px}#checking .card{padding:24px 20px}
 .summary{grid-template-columns:88px minmax(0,1fr);grid-template-areas:"m h" "c c" "a a";gap:16px;padding:18px}
 .headline{align-self:center}
 .meter,.meter svg{width:88px;height:88px}.meter .num b{font-size:24px}.meter .num span{font-size:10px;letter-spacing:.04em}
 .headline h2{font-size:19px}.headline p{font-size:14px;line-height:1.45}
 .chip{min-height:40px;padding:0 12px 0 9px;font-size:14px}
 .actions .btn{flex:1 1 auto;justify-content:center}.actions #copyall{flex-basis:100%}
 .work{grid-template-columns:minmax(0,1fr);margin-top:16px}
 .doc{padding:20px 18px 24px}.draft{font-size:18px;line-height:1.7}
 .tip{display:none}
 .mobilehint{display:flex;align-items:center;gap:8px;font-size:14px;color:var(--ink2);background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:0 0 14px}
 .panel{position:fixed;left:0;right:0;bottom:0;top:auto;z-index:50;max-height:82vh;border-radius:18px 18px 0 0;border-bottom:0;transform:translateY(105%);transition:transform .28s var(--ease-drawer),visibility 0s .28s;visibility:hidden;box-shadow:var(--shadow-sheet)}
 .panel.open{transform:none;visibility:visible;transition:transform .32s var(--ease-drawer),visibility 0s}
 .panel .inner{padding:8px 18px 28px}
 .panel .grab{display:block;width:40px;height:4px;border-radius:2px;background:var(--line2);margin:8px auto 10px}
 .close{display:grid}
 .scrim{display:block;position:fixed;inset:0;background:rgba(15,23,42,.38);z-index:40;opacity:0;pointer-events:none;transition:opacity .25s ease}
 .scrim.on{opacity:1;pointer-events:auto}
 .keyrow{grid-template-columns:minmax(0,1fr)}
 .startgrid{grid-template-columns:minmax(0,1fr);gap:24px}.startgrid>.side{position:static;order:2}
 #drop{min-height:200px}
}
@media (min-width:861px){.panel .grab{display:none}}
@media (max-width:420px){.opt{display:none}h1{font-size:30px}.tab{font-size:15px}.btn{padding:0 14px}}
@media (prefers-reduced-motion:reduce){
 *,*::before,*::after{animation-duration:.001ms!important;animation-iteration-count:1!important;transition-duration:.001ms!important;scroll-behavior:auto!important}
 .steps li.active .dot{border-top-color:var(--primary);background:#DCE5F0}
}
@media print{.top nav,.actions,.panel,.tip,.mobilehint,.chips{display:none!important}.work{grid-template-columns:1fr}.card{box-shadow:none}}
.fresh{font-size:14px;color:var(--ink2);padding:0 4px}.fresh.stale{color:#9a3b00;font-weight:600}
.wrong{margin-top:14px;border-top:1px solid #e3e3e3;padding-top:10px}.wrong form{display:grid;gap:8px;margin-top:8px}
.wrong label{font-size:14px}.wrong select,.wrong input,.wrong textarea{font:inherit;padding:6px 8px;border:1px solid #c9c9c9;border-radius:6px;width:100%;box-sizing:border-box}
</style></head>
<body data-state="start">
<header class="top">
 <a class="brand" href="./" aria-label="TruthLens home"><svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="14" cy="14" r="9.5"/><path d="m21 21 7 7"/><path d="m10 14.2 3 3 5.5-6"/></svg>TruthLens</a>
 <nav><span class="fresh" id="fresh" aria-live="polite"></span><button class="btn quiet" id="updnow" type="button" title="Refresh official data (PIB, reports, Parliament, MoSPI, NDAP, RBI, your plug-ins) in the background">Update official data</button><a class="link" href="docs">API</a></nav>
</header>

<main>
<!-- STATE 1: start -->
<section id="start" class="view" aria-labelledby="start-h">
 <div class="startgrid">
 <aside class="side" aria-label="Optional keys">
 <details class="key" id="keybox" open><summary><svg class="i chev" data-i="chev"></svg>Optional: your own AI key or data.gov.in key</summary>
  <form class="keybody" onsubmit="return false">
   <p>TruthLens works without any key. With an AI key it also judges non-numeric claims and writes better fixes. Your key is used for this one check only. It is never stored, logged or shown in the report. Providers marked “untested” have only been tried against simulated answers, never a live account.</p>
   <div class="keyrow"><div><label for="prov">Provider</label><select id="prov"><option value="anthropic">Anthropic Claude</option><option value="openai">OpenAI</option>
    <option value="deepseek">DeepSeek (untested)</option><option value="mistral">Mistral (untested)</option><option value="xai">xAI Grok (untested)</option>
    <option value="gemini">Google Gemini (untested)</option><option value="moonshot">Moonshot Kimi (untested)</option><option value="qwen">Alibaba Qwen (untested)</option>
    <option value="zhipu">Z.ai GLM (untested)</option><option value="openrouter">OpenRouter (untested)</option><option value="custom">Custom OpenAI-compatible URL (untested)</option></select></div>
   <div><label for="key">API key</label><input id="key" type="password" autocomplete="off" spellcheck="false" placeholder="Paste your key (optional)"></div></div>
   <div class="keyrow"><div><label for="llmmodel">Model (optional)</label><input id="llmmodel" type="text" autocomplete="off" spellcheck="false" placeholder="Provider default"></div>
   <div id="baserow" hidden><label for="llmbase">Base URL (custom only)</label><input id="llmbase" type="url" autocomplete="off" spellcheck="false" placeholder="https://your-host/v1"></div></div>
   <p>A data.gov.in key (optional) is accepted for data.gov.in resources you map yourself. Untested: data.gov.in has never answered our test network, so this path has only been tested on made-up sample data.</p>
   <div class="keyrow one"><div><label for="dgkey">data.gov.in key</label><input id="dgkey" type="password" autocomplete="off" spellcheck="false" placeholder="Paste your data.gov.in key (optional)"></div></div>
  </form>
 </details>
 </aside>
 <div class="startmain">
 <h1 id="start-h" tabindex="-1">Check every fact in your draft</h1>
 <p class="lede">TruthLens reads your document, tests each number, claim and citation against official sources, and shows you exactly what to fix.</p>
 <div class="card">
  <div class="tabs" role="tablist" aria-label="How to add your draft">
   <button class="tab" role="tab" id="tab-file" aria-selected="true" aria-controls="pane-file" type="button"><svg class="i" data-i="upload"></svg>Upload a file</button>
   <button class="tab" role="tab" id="tab-text" aria-selected="false" aria-controls="pane-text" tabindex="-1" type="button"><svg class="i" data-i="type"></svg>Paste text</button>
   <button class="tab" role="tab" id="tab-cmp" aria-selected="false" aria-controls="pane-cmp" tabindex="-1" type="button"><svg class="i" data-i="file"></svg>Compare two versions</button>
  </div>
  <div class="pane" id="pane-file" role="tabpanel" aria-labelledby="tab-file">
   <div id="drop" tabindex="0" role="button" aria-label="Choose a file to check: .docx, .pdf, .txt or .md, up to 15 MB">
    <div class="ic"><svg class="i" data-i="file"></svg></div>
    <b>Drop a .docx, .pdf, .txt or .md file here</b>
    <span>Word, PDF or plain text · up to 15&nbsp;MB</span>
    <span class="btn ghost" aria-hidden="true">Choose a file</span>
   </div>
   <input id="file" type="file" accept=".docx,.pdf,.txt,.md" hidden>
  </div>
  <div class="pane" id="pane-text" role="tabpanel" aria-labelledby="tab-text" hidden>
   <label for="txt" class="sr">Paste your draft</label>
   <textarea id="txt" placeholder="Paste a paragraph or a whole draft here"></textarea>
   <div class="row"><button class="btn primary" id="go" type="button"><svg class="i" data-i="search"></svg>Check text</button><span class="hint" id="count"></span></div>
  </div>
  <div class="pane" id="pane-cmp" role="tabpanel" aria-labelledby="tab-cmp" hidden>
   <p class="hint">Upload an older and a newer version of a document (.docx, .pdf, .txt or .md). TruthLens lists sentences copied almost word for word, figures that changed between matching sentences, old sentences and commitments that are gone, and new section headings. With <b>Match by meaning</b> it also pairs sentences that say the same thing in other words and labels each change (kept, strengthened, weakened, changed figure, new, dropped) by topic, quoting both versions. Meaning matching is similarity, not understanding: check the quotes. Nothing is sent to any outside source and the files are not kept.</p>
   <div class="keyrow two"><div><label for="cmpold">Older version</label><input id="cmpold" type="file" accept=".docx,.pdf,.txt,.md"></div>
   <div><label for="cmpnew">Newer version</label><input id="cmpnew" type="file" accept=".docx,.pdf,.txt,.md"></div></div>
   <div class="row"><label class="hint"><input type="checkbox" id="cmpmeaning"> Match by meaning</label><span class="hint" id="cmpmstate"></span></div>
   <div class="row"><button class="btn primary" id="cmpgo" type="button"><svg class="i" data-i="search"></svg>Compare</button>
    <button class="btn ghost" id="cmpdl" type="button" hidden><svg class="i" data-i="download"></svg>Download comparison<span class="opt">(HTML)</span></button><span class="hint" id="cmpstate" role="status"></span></div>
   <div id="cmpout" class="cmpout"></div>
  </div>
 </div>
 <div id="err" class="err" role="alert" hidden><svg class="i" data-i="alert"></svg><span id="errtext"></span></div>
 <div class="or">No draft to hand?</div>
 <div class="sample"><button class="btn ghost" id="sample" type="button"><svg class="i" data-i="play"></svg>Try the sample policy note</button>
  <a class="btn quiet" id="samplereport" href="sample-report" target="_blank" rel="noopener">Open sample report</a></div>
 <p class="foot">“Open sample report” shows a finished report straight away, with no internet needed.</p>
 <p class="foot">No sign-up. Your draft is checked and not kept.</p>
 <p class="live">Deep check asks: MoSPI, RBI, CEA, PPAC, Jal Jeevan Mission, PIB, Lok Sabha, Rajya Sabha, Economic Survey and World Bank; research: OpenAlex, arXiv and Crossref; the NDAP catalogue only names a dataset to cite. Quick check uses the official figures bundled with TruthLens (including Census 2011, CGWB 2025 and NFHS-5 Karnataka). Untested (never answered our test network; tested only on made-up sample data, marked “unverified source”): data.gov.in, Semantic Scholar and Shodhganga.</p>
 </div>
 </div>
</section>

<!-- STATE 2: checking -->
<section id="checking" class="view" aria-labelledby="checking-h" hidden>
 <div class="card" aria-busy="true">
  <h2 id="checking-h" tabindex="-1">Checking your draft</h2>
  <p class="what" id="what"></p>
  <ol class="steps" id="steps">
   <li data-step="0"><span class="dot"><svg class="i" data-i="check"></svg></span><span>Reading the document</span></li>
   <li data-step="1"><span class="dot"><svg class="i" data-i="check"></svg></span><span>Finding claims</span></li>
   <li data-step="2"><span class="dot"><svg class="i" data-i="check"></svg></span><span id="claimstep">Checking claims</span></li>
   <li data-step="3"><span class="dot"><svg class="i" data-i="check"></svg></span><span>Writing the report</span></li>
  </ol>
  <p class="sr" id="steplive" role="status" aria-live="polite"></p>
  <div class="elapsed"><span id="elapsed">Quick check: a few seconds</span><button class="btn quiet" id="cancel" type="button">Cancel</button></div>
 </div>
</section>

<!-- STATE 3: results -->
<section id="results" class="view" aria-labelledby="results-h" hidden>
 <div class="card summary">
  <div class="meter" id="meter" role="img" aria-label="">
   <svg viewBox="0 0 128 128" aria-hidden="true"><circle class="track" cx="64" cy="64" r="54"/><circle class="val" id="meterval" cx="64" cy="64" r="54" stroke-dasharray="339.29" stroke-dashoffset="339.29"/></svg>
   <div class="num" aria-hidden="true"><b id="score">0%</b><span>of checked</span></div>
  </div>
  <div class="headline">
   <h2 id="results-h" tabindex="-1"></h2>
   <p id="subline"></p>
   <p class="modeline" id="modeline" hidden><span class="tag" id="modetag"></span><span id="modetext"></span><button class="btn ghost" id="deepbtn" type="button" hidden>Deep check</button></p>
   <p class="banner" id="banner" role="note" hidden></p>
   <details class="bdetails" id="bdetails" hidden><summary>Details</summary><ul id="bdlist"></ul></details>
  </div>
  <div class="chips" id="chips" role="group" aria-label="Show only one kind of finding"></div>
  <div class="actions">
   <button class="btn primary" id="copyall" type="button"><svg class="i" data-i="copy"></svg>Copy corrected text</button>
   <button class="btn ghost" id="download" type="button"><svg class="i" data-i="download"></svg>Download report<span class="opt">(HTML)</span></button>
   <button class="btn ghost" id="citebtn" type="button" hidden><svg class="i" data-i="download"></svg>Claims to cite<span class="opt">(CSV)</span></button>
   <button class="btn quiet" id="again" type="button"><svg class="i" data-i="rotate"></svg>Check another</button>
  </div>
 </div>
 <div class="work">
  <article class="card doc" aria-labelledby="dochead">
   <div class="dochead"><h3 id="dochead"></h3><span id="docmeta"></span></div>
   <p class="mobilehint"><svg class="i" data-i="pointer"></svg>Tap a highlighted sentence to see why.</p>
   <div class="draft" id="draft"></div>
   <p class="tip"><svg class="i" data-i="keyboard"></svg>Click a highlighted sentence, or press <kbd>J</kbd> and <kbd>K</kbd> to move between findings.</p>
  </article>
  <aside class="card panel" id="panel" aria-label="Finding" tabindex="-1"><span class="grab" aria-hidden="true"></span><div class="inner" id="panelbody"></div></aside>
 </div>
 <p class="note">TruthLens is a checking aid, not an authority. Open the source before you rely on a verdict.</p>
</section>
</main>
<div class="scrim" id="scrim"></div>
<div class="toast" id="toast" role="status" aria-live="polite"></div>

<script>
(function(){
"use strict";
/* ---------- constant SVG icons (Lucide, ISC) ---------- */
var ICON={
 upload:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/>',
 type:'<path d="M4 7V4h16v3"/><path d="M9 20h6"/><path d="M12 4v16"/>',
 file:'<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M12 18v-6"/><path d="m9 15 3-3 3 3"/>',
 search:'<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
 play:'<path d="M6 3l14 9-14 9V3z"/>',
 alert:'<circle cx="12" cy="12" r="10"/><path d="M12 8v4"/><path d="M12 16h.01"/>',
 chev:'<path d="m9 18 6-6-6-6"/>',
 check:'<path d="M20 6 9 17l-5-5"/>',
 copy:'<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
 download:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
 rotate:'<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
 pointer:'<path d="M9 9l5 12 1.8-5.2L21 14Z"/><path d="M7.2 2.2 8 5.1"/><path d="m5.1 8-2.9-.8"/><path d="M14 4.1 12 6"/><path d="m6 12-1.9 2"/>',
 keyboard:'<rect x="2" y="4" width="20" height="16" rx="2"/><path d="M6 8h.01M10 8h.01M14 8h.01M18 8h.01M8 12h.01M12 12h.01M16 12h.01M7 16h10"/>',
 up:'<path d="m18 15-6-6-6 6"/>',down:'<path d="m6 9 6 6 6-6"/>',x:'<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
 ext:'<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
 warn:'<path d="m21.7 18-8-14a2 2 0 0 0-3.4 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
 xc:'<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
 half:'<circle cx="12" cy="12" r="10"/><path d="M12 2a10 10 0 0 1 0 20Z" fill="currentColor"/>',
 help:'<circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
 okc:'<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
 quote:'<path d="M17 6H3"/><path d="M21 12H8"/><path d="M21 18H8"/><path d="M3 12v6"/>',
 undo:'<path d="M9 14 4 9l5-5"/><path d="M4 9h11a5 5 0 0 1 0 10h-3"/>'
};
function svg(name){var s=document.createElementNS("http://www.w3.org/2000/svg","svg");s.setAttribute("class","i");s.setAttribute("viewBox","0 0 24 24");s.setAttribute("aria-hidden","true");s.innerHTML=ICON[name]||"";return s;}
function paintIcons(root){(root||document).querySelectorAll("svg[data-i]").forEach(function(s){s.setAttribute("viewBox","0 0 24 24");s.setAttribute("aria-hidden","true");s.innerHTML=ICON[s.getAttribute("data-i")]||"";s.removeAttribute("data-i");});}
paintIcons();

/* ---------- helpers: DOM built with textContent only ---------- */
function $(id){return document.getElementById(id);}
function el(tag,props){var n=document.createElement(tag),k,v;props=props||{};
 for(k in props){v=props[k];if(v==null||v===false)continue;
  if(k==="class")n.className=v;else if(k==="text")n.textContent=v;
  else if(k.slice(0,2)==="on")n.addEventListener(k.slice(2),v);else n.setAttribute(k,v===true?"":String(v));}
 for(var i=2;i<arguments.length;i++)add(n,arguments[i]);return n;}
function add(n,c){if(c==null||c===false)return;if(Array.isArray(c)){c.forEach(function(x){add(n,x);});return;}
 n.appendChild(c.nodeType?c:document.createTextNode(String(c)));}
function safeUrl(u){if(!u)return null;try{var x=new URL(String(u),location.href);return(x.protocol==="https:"||x.protocol==="http:")?x.href:null;}catch(e){return null;}}
function host(u){try{return new URL(u).hostname.replace(/^www\./,"");}catch(e){return "";}}
function clip(s,n){s=String(s||"");return s.length>n?s.slice(0,n-1).replace(/\s+\S*$/,"")+"…":s;}
var RM=window.matchMedia("(prefers-reduced-motion: reduce)");
var PHONE=window.matchMedia("(max-width: 860px)");
function toast(msg){var t=$("toast");t.textContent=msg;t.classList.add("on");clearTimeout(toast._t);toast._t=setTimeout(function(){t.classList.remove("on");},2200);}
function copy(text){
 if(navigator.clipboard&&window.isSecureContext)return navigator.clipboard.writeText(text);
 return new Promise(function(res,rej){var ta=el("textarea",{style:"position:fixed;opacity:0"});ta.value=text;document.body.appendChild(ta);ta.select();
  try{document.execCommand("copy")?res():rej();}catch(e){rej(e);}ta.remove();});}

var V={
 "CONTRADICTED":{c:"con",l:"Contradicted",i:"xc",p:"The evidence says something different."},
 "PARTLY SUPPORTED":{c:"part",l:"Partly supported",i:"half",p:"Part of this is backed up, or a figure is close but not exact."},
 "DATED":{c:"dat",l:"Dated: earlier year or boundary",i:"help",p:"The figure was compared with official data for another year or for the State's boundaries before a split (for example undivided Uttar Pradesh before Uttarakhand). It is not wrong, but it is not today's figure: say which year it is for, or use a current figure."},
 "UNVERIFIED":{c:"unv",l:"Needs a source",i:"help",p:"No official dataset in TruthLens covers this claim yet, or no source answered in this run. That is not a finding that it is wrong: cite a source for it, or check it by hand."},
 "SUPPORTED":{c:"sup",l:"Supported",i:"okc",p:"The evidence says the same thing."},
 "SKIPPED":{c:"op",l:"Opinion, not checked",i:"quote",p:"This reads as an opinion or recommendation, so there is nothing to check."}};
var TYPE={numeric:"Number or statistic",citation:"Cited claim",entity:"Factual claim",opinion:"Opinion"};
/* source-type badge for one evidence item (older reports carry no source_type: derive it like the server does) */
function stype(e){var t=e.source_type||"",u=String(e.source_url||"").toLowerCase(),r=e.retriever||"";
 if(t==="Parliament"||(!t&&r==="parliament"))t=/rajyasabha/.test(u)?"Rajya Sabha":(/sansad|loksabha/.test(u)?"Lok Sabha":"Parliament");
 if(t)return t;
 return r==="datagovin"||/data\.gov\.in/.test(u)?"data.gov.in":r==="mospi"||/mospi\.gov\.in/.test(u)?"MoSPI":r==="pib"||/pib\.gov\.in/.test(u)?"PIB":
  r==="worldbank"?"World Bank":r==="openalex"||r==="semanticscholar"||r==="arxiv"?"Paper":r==="shodhganga"?"Thesis":
  r==="ndap"||/ndap/.test(u)?"NDAP":r==="rbi"||/rbi\.org\.in/.test(u)?"RBI":r==="cea"||/cea\.nic\.in/.test(u)?"CEA":
  r==="ppac"||/ppac\.gov\.in/.test(u)?"PPAC":r==="jjm"||/ejalshakti/.test(u)?"JJM":r==="indiawris"?"India-WRIS":r==="hmis"?"HMIS":
  r==="reports"?"Report":r==="curated"?"Official data":r==="web"?"Web":r==="citation"?"Cited source":"Report";}
function asOf(e){return e.data_as_of||e.as_of||e.date||"";}
function citation(e){var bits=[e.publisher,e.title&&e.title!==e.publisher?e.title:"",stype(e)+(e.page?", page "+e.page:"")].filter(Boolean);
 var a=asOf(e);if(a)bits.push("Data as of "+a);var u=safeUrl(e.source_url);if(u)bits.push(u);
 return bits.join(". ").replace(/\.\./g,".");}
var ORDER=["CONTRADICTED","PARTLY SUPPORTED","DATED","UNVERIFIED","SUPPORTED"];
/* v0.6: "couldn't check" is split by reason in the chips, the same way the headline counts it */
var REASONS=[["no_data","Needs a source"],["no_response","Source didn't respond"],["quick","Not checked in Quick mode"],["deadline","Ran out of time"]];
function filterLabel(key){if(V[key])return V[key].l;var r=REASONS.filter(function(x){return "UNVERIFIED:"+x[0]===key;})[0];return r?r[1]:"";}
function fmatch(s,key){if(!key)return true;if(key.indexOf("UNVERIFIED:")!==0)return s.verdict===key;
 if(s.verdict!=="UNVERIFIED")return false;var why=key.slice(11);
 return (claimsBySid[s.id]||[]).some(function(c){return c.verdict==="UNVERIFIED"&&(c.unchecked_reason||"no_data")===why;});}

/* ---------- state switching ---------- */
function show(state){
 ["start","checking","results"].forEach(function(s){var v=$(s);var on=s===state;v.hidden=!on;if(on){v.classList.remove("enter");void v.offsetWidth;v.classList.add("enter");}});
 document.body.setAttribute("data-state",state);
 var h=$(state+"-h");if(h)h.focus({preventScroll:true});window.scrollTo(0,0);}

/* ---------- start: tabs, drop zone, paste ---------- */
var tabs=[$("tab-file"),$("tab-text"),$("tab-cmp")];
function selectTab(t){tabs.forEach(function(x){var on=x===t;x.setAttribute("aria-selected",on);x.tabIndex=on?0:-1;$(x.getAttribute("aria-controls")).hidden=!on;});t.focus();}
tabs.forEach(function(t,i){t.addEventListener("click",function(){selectTab(t);});
 t.addEventListener("keydown",function(e){if(e.key==="ArrowRight"||e.key==="ArrowLeft"){e.preventDefault();selectTab(tabs[(i+(e.key==="ArrowRight"?1:tabs.length-1))%tabs.length]);}});});
var drop=$("drop"),fileIn=$("file");
drop.addEventListener("click",function(){fileIn.click();});
drop.addEventListener("keydown",function(e){if(e.key==="Enter"||e.key===" "){e.preventDefault();fileIn.click();}});
fileIn.addEventListener("change",function(){if(fileIn.files[0])runFile(fileIn.files[0]);fileIn.value="";});
["dragenter","dragover"].forEach(function(ev){drop.addEventListener(ev,function(e){e.preventDefault();drop.classList.add("over");});});
["dragleave","dragend"].forEach(function(ev){drop.addEventListener(ev,function(){drop.classList.remove("over");});});
drop.addEventListener("drop",function(e){e.preventDefault();drop.classList.remove("over");var f=e.dataTransfer&&e.dataTransfer.files[0];if(f)runFile(f);});
document.addEventListener("dragover",function(e){if(document.body.dataset.state==="start")e.preventDefault();});
document.addEventListener("drop",function(e){if(document.body.dataset.state==="start"&&e.target!==drop&&!drop.contains(e.target)){e.preventDefault();var f=e.dataTransfer&&e.dataTransfer.files[0];if(f)runFile(f);}});
var txt=$("txt");
txt.addEventListener("input",function(){var w=(txt.value.trim().match(/\S+/g)||[]).length;$("count").textContent=w?w+(w===1?" word":" words"):"";});
$("go").addEventListener("click",function(){var t=txt.value;if(!t.trim()){showErr("Paste some text first.");txt.focus();return;}runText(t);});
txt.addEventListener("keydown",function(e){if(e.key==="Enter"&&(e.ctrlKey||e.metaKey))$("go").click();});
$("sample").addEventListener("click",runSample);
function showErr(m){$("errtext").textContent=m;$("err").hidden=false;}
/* ---------- v0.6: compare two versions ---------- */
function cmpForm(){var o=$("cmpold").files[0],n=$("cmpnew").files[0];if(!o||!n){showErr("Choose both files: the older and the newer version.");return null;}
 if(o.size>15*1024*1024||n.size>15*1024*1024){showErr("Each file can be up to 15 MB.");return null;}
 var fd=new FormData();fd.append("old",o);fd.append("new",n);return fd;}
function cmpList(title,items,fmt){var box=el("div",{class:"cmpsec"});add(box,el("h3",{text:title}));
 if(!items.length){add(box,el("p",{class:"hint",text:"None."}));return box;}var ul=el("ul");items.forEach(function(x){add(ul,el("li",{text:fmt(x)}));});add(box,ul);return box;}
function nums(ch){var b=(ch.changed||[]).map(function(c){return c.old+" → "+c.new;});(ch.removed||[]).forEach(function(x){b.push("removed "+x);});(ch.added||[]).forEach(function(x){b.push("added "+x);});return b.join("; ");}
/* v0.7: match by meaning, on by default when the optional model is installed */
(async function(){try{var r=await fetch("compare/meaning-status");if(!r.ok)return;var st=await r.json();
 $("cmpmeaning").checked=!!st.installed;$("cmpmeaning").disabled=!st.installed;
 $("cmpmstate").textContent=st.installed?(st.model_downloaded?"":"(the model downloads once on first use)"):"(not installed here: "+st.install+")";}catch(e){}})();
function cmpQ(){return $("cmpmeaning").checked?"&meaning=true":"";}
var LABS=["kept","strengthened","weakened","changed figure","new","dropped"];
function meaningBox(m){var box=el("div",{class:"cmpsec"});add(box,el("h3",{text:"Match by meaning"}));
 if(m.unavailable){add(box,el("p",{class:"hint",text:"Not run: "+m.unavailable}));return box;}
 add(box,el("p",{class:"cmphead",text:LABS.map(function(k){return m.summary[k]+" "+k;}).join(" · ")}));
 var tb=el("table",{class:"cmptab"}),hr=el("tr");add(hr,el("th",{text:"Topic"}));LABS.forEach(function(k){add(hr,el("th",{text:k}));});add(tb,hr);
 m.topics.forEach(function(t){var tr=el("tr");add(tr,el("td",{text:t.topic}));LABS.forEach(function(k){add(tr,el("td",{text:String(t.counts[k]||0)}));});add(tb,tr);});add(box,tb);
 m.topics.forEach(function(t){var d=el("details");add(d,el("summary",{text:t.topic}));
  (t.why&&t.why.length?t.why:[null]).forEach(function(w){add(d,el("p",{class:"hint",text:w?"Reason the document gives (linked by similarity, check): “"+clip(w.text,260)+"” ("+w.location+")":"Reason not stated in the document"}));});
  if(t.ai_summary)add(d,el("p",{class:"hint",text:t.ai_summary.status==="ok"?t.ai_summary.label+": "+t.ai_summary.text:t.ai_summary.label+": not shown ("+t.ai_summary.status+")"}));
  var ul=el("ul");t.items.filter(function(x){return x.label!=="new"&&x.label!=="dropped";}).concat(t.items.filter(function(x){return x.label==="dropped";}).slice(0,6)).forEach(function(x){
   var s=x.label.toUpperCase()+": ";if(x.old)s+="old “"+clip(x.old.text,200)+"” ("+x.old.location+")";if(x.new&&x.new.length)s+=" → new “"+clip(x.new[0].text,200)+"” ("+x.new[0].location+")";if(x.rule&&x.rule.length)s+=" ["+x.rule.join("; ")+"]";add(ul,el("li",{text:s}));});
  add(d,ul);add(box,d);});
 add(box,el("p",{class:"hint",text:m.caveat+" New sentences and the rest of the dropped ones are in the downloaded report."}));return box;}
$("cmpgo").addEventListener("click",async function(){clearErr();var fd=cmpForm();if(!fd)return;var b=this;b.disabled=true;$("cmpstate").textContent=$("cmpmeaning").checked?"Comparing (matching by meaning can take a minute)…":"Comparing…";$("cmpout").textContent="";$("cmpdl").hidden=true;
 try{var r=await fetch("compare/file?format=json"+cmpQ(),{method:"POST",body:fd});if(!r.ok)throw await errorOf(r);var c=await r.json(),S=c.summary,out=$("cmpout");
  if(c.meaning)add(out,meaningBox(c.meaning));
  add(out,el("p",{class:"cmphead",text:S.near_copies+" near-copied sentences · "+S.figures_changed+" figures changed · "+S.dropped_commitments+" commitments dropped ("+S.dropped+" old sentences with no match) · "+S.added+" new sentences · "+S.new_sections+" new section headings"}));
  add(out,cmpList("Near-copied sentences (first 5 of "+S.near_copies+")",c.near_copies.slice(0,5),function(x){return Math.round(x.similarity*100)+"% · "+clip(x.new,220)+(nums(x.numbers)?"  ["+nums(x.numbers)+"]":"");}));
  add(out,cmpList("Figures changed between matching sentences",c.number_changes.slice(0,8),function(x){return nums(x.numbers)+" · "+clip(x.new,180);}));
  add(out,cmpList("Commitments dropped (first 8 of "+S.dropped_commitments+")",c.dropped.filter(function(d){return d.commitment;}).slice(0,8),function(x){return clip(x.text,220);}));
  add(out,cmpList("New section headings",c.new_sections.slice(0,12),function(x){return x.heading+" · "+x.new_sentences+" of "+x.sentences+" sentences new";}));
  $("cmpstate").textContent=c.meaning&&!c.meaning.unavailable?"Done. Matches by meaning are similarity, not understanding: check the quotes.":"Done. Similarity is about wording, not meaning: check the pairs before relying on them.";$("cmpdl").hidden=false;
 }catch(e){$("cmpstate").textContent="";showErr(e.message||"The comparison failed.");}finally{b.disabled=false;}});
$("cmpdl").addEventListener("click",async function(){var fd=cmpForm();if(!fd)return;var b=this;b.disabled=true;
 try{var r=await fetch("compare/file?format=html"+cmpQ(),{method:"POST",body:fd});if(!r.ok)throw await errorOf(r);var blob=await r.blob();
  var a=el("a",{href:URL.createObjectURL(blob),download:"truthlens-compare.html"});document.body.appendChild(a);a.click();a.remove();
 }catch(e){showErr(e.message||"The download failed.");}finally{b.disabled=false;}});
function clearErr(){$("err").hidden=true;}

function keyFields(){var k=$("key").value.trim(),d=$("dgkey").value.trim(),o={};
 if(k){o.llm_key=k;o.llm_provider=$("prov").value;}if(d)o.datagovin_key=d;return (k||d)?o:null;}
/* v0.6: model and (custom) base URL travel as headers on uploads and as fields on JSON requests; never stored */
function llmExtra(){var k=$("key").value.trim(),h={};if(!k)return h;var m=$("llmmodel").value.trim(),b=$("llmbase").value.trim();
 if(m)h["X-LLM-Model"]=m;if($("prov").value==="custom"&&b)h["X-LLM-Base-URL"]=b;return h;}
$("prov").addEventListener("change",function(){$("baserow").hidden=this.value!=="custom";});

/* ---------- checking: honest step progress ---------- */
var ctl=null,timers=[],tick=null,started=0,lastInput=null,job=null,poll=null,lastJob=null,curMode="quick";
function setStep(n){var lis=$("steps").children;for(var i=0;i<lis.length;i++){lis[i].className=i<n?"done":(i===n?"active":"");}
 if(lis[n])$("steplive").textContent=lis[n].textContent;}
var STAGE={"reading the document":0,"finding claims":1,"checking claims":2,"writing report":3,"done":3,"cancelling":2};
function startChecking(label){
 clearErr();$("what").textContent=label;setStep(0);$("claimstep").textContent="Checking claims";show("checking");started=Date.now();
 /* v0.5.1: the server runs the check as a background job and reports real progress (stage, claims done of total);
    nothing here is an estimate. v0.5.2: Quick check (default) takes seconds; Deep check about a minute. */
 var hint=curMode==="deep"?"Deep check: about a minute":"Quick check: a few seconds";
 $("elapsed").textContent=hint;
 tick=setInterval(function(){var s=Math.round((Date.now()-started)/1000);$("elapsed").textContent=s+" s elapsed · "+hint;},1000);}
function stopChecking(){timers.forEach(clearTimeout);timers=[];clearInterval(tick);clearTimeout(poll);poll=null;}
function showProgress(p){
 var n=STAGE[p.stage];if(n==null)n=2;setStep(n);
 if(p.claims_total){var t="Checking claims: "+p.claims_done+" of "+p.claims_total;
  if($("claimstep").textContent!==t){$("claimstep").textContent=t;if(n===2)$("steplive").textContent=t;}}}
$("cancel").addEventListener("click",function(){
 if(ctl)ctl.abort();
 if(job){fetch("jobs/"+job+"/cancel",{method:"POST"}).catch(function(){});job=null;}
 stopChecking();show("start");});

function sleep(ms){return new Promise(function(res){poll=setTimeout(res,ms);});}
async function errorOf(r){var msg="";try{var j=await r.json();msg=typeof j.detail==="string"?j.detail:(j.detail&&j.detail[0]&&j.detail[0].msg)||"";}catch(e){}
 return new Error(msg||("The check failed (error "+r.status+")."));}
async function request(url,opts,label){
 ctl=new AbortController();opts.signal=ctl.signal;startChecking(label);
 var mine=null;
 try{
  var r=await fetch(url,opts);
  if(!r.ok)throw await errorOf(r);
  mine=job=(await r.json()).job_id;
  /* poll real progress until the job finishes */
  for(;;){
   await sleep(800);
   if(job!==mine)return;                       /* cancelled or replaced */
   var p=await fetch("jobs/"+mine,{signal:ctl.signal});
   if(!p.ok)throw await errorOf(p);
   var st=await p.json();
   showProgress(st);
   if(st.status==="running")continue;
   if(st.status==="cancelled")return;
   break;}
  var res=await fetch("jobs/"+mine+"/result?format=json",{signal:ctl.signal});
  if(!res.ok)throw await errorOf(res);
  var report=await res.json();
  if(job!==mine)return;
  lastJob=mine;job=null;stopChecking();setStep(3);
  await new Promise(function(res){setTimeout(res,RM.matches?0:450);});
  $("steps").lastElementChild.className="done";
  renderResults(report);show("results");
  if(!PHONE.matches){var fs=findings(),first=null;ORDER.some(function(k){first=fs.filter(function(x){return x.verdict===k;})[0];return !!first;});if(first)select(first.id,false);} /* open the most serious finding first */
 }catch(e){if(job===mine)job=null;stopChecking();if(e.name==="AbortError")return;show("start");showErr(e.message||"Something went wrong. Please try again.");}
}
var OK=[".docx",".pdf",".txt",".md"];
/* v0.5.2: Deep check of the claims Quick mode left unchecked (the server still holds the document in memory) */
function runDeep(){if(!lastJob)return;curMode="deep";var fd=new FormData();var k=keyFields();if(k)Object.keys(k).forEach(function(n){fd.append(n,k[n]);});
 request("jobs/"+lastJob+"/deep",{method:"POST",body:fd,headers:llmExtra()},(lastInput&&lastInput.name||"Your draft")+" · Deep check");}
function runFile(f){curMode="quick";
 var ext=(f.name.match(/\.[^.]+$/)||[""])[0].toLowerCase();
 if(OK.indexOf(ext)<0){showErr("TruthLens reads .docx, .pdf, .txt and .md files. Try saving your draft in one of those.");return;}
 if(f.size>15*1024*1024){showErr("That file is over 15 MB. Try a shorter version or paste the text.");return;}
 var fd=new FormData();fd.append("file",f);var k=keyFields();if(k)Object.keys(k).forEach(function(n){fd.append(n,k[n]);});
 lastInput={kind:"file",name:f.name};
 request("jobs/file",{method:"POST",body:fd,headers:llmExtra()},f.name);}
function runText(t){curMode="quick";var body={type:"text",content:t,format:"json"};var k=keyFields();if(k)Object.keys(k).forEach(function(n){body[n]=k[n];});
 var ex=llmExtra();if(ex["X-LLM-Model"])body.llm_model=ex["X-LLM-Model"];if(ex["X-LLM-Base-URL"])body.llm_base_url=ex["X-LLM-Base-URL"];
 lastInput={kind:"text",name:"Pasted text"};
 request("jobs",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(body)},"Pasted text, "+(t.trim().match(/\S+/g)||[]).length+" words");}
async function runSample(){
 try{var r=await fetch("sample");if(!r.ok)throw new Error();var b=await r.blob();
  runFile(new File([b],"sample_policy_note.docx",{type:b.type}));}
 catch(e){showErr("The sample file is not available on this server.");}}

/* ---------- results ---------- */
var R=null,claimsBySid={},sentById={},fixes={},filter=null,current=null,openerEl=null;
function findings(){return R.sentences.filter(function(s){return V[s.verdict]&&s.verdict!=="SKIPPED"&&(claimsBySid[s.id]||[]).length;})
 .filter(function(s){return fmatch(s,filter);});}
function sentText(s){return fixes[s.id]!=null?fixes[s.id]:s.text;}

function renderResults(report){
 R=report;claimsBySid={};sentById={};fixes={};filter=null;current=null;
 (R.claims||[]).forEach(function(c){(claimsBySid[c.claim.sentence_id]=claimsBySid[c.claim.sentence_id]||[]).push(c);});
 (R.sentences||[]).forEach(function(s){sentById[s.id]=s;});
 var S=R.summary||{},v=S.verdicts||{},checkable=S.checkable_claims||0;
 var score=S.verified_score;
 /* headline */
 var sup=v.SUPPORTED||0,con=v.CONTRADICTED||0,part=v["PARTLY SUPPORTED"]||0,unv=v.UNVERIFIED||0,dat=v.DATED||0;
 var skp=S.skipped!=null?S.skipped:(S.skipped_opinions||0),checked=S.checked_claims!=null?S.checked_claims:sup+part+con;
 /* v0.4.1: split headline, e.g. "8 wrong · 7 supported · 3 couldn't check · 1 skipped" */
 var head=S.headline||[con+" wrong"].concat(part?[part+" partly supported"]:[]).concat([sup+" supported",unv+" couldn't check",skp+" skipped"]).join(" · ");
 $("results-h").textContent=checkable||skp?head:"No checkable claims found";
 var bits=[],low=S.low_confidence_supported||0;
 /* v0.5.3: what was checked against data, what is wrong, what needs a source (not a failure: cite it) */
 var needs=S.needs_source!=null?S.needs_source:unv,other=Math.max(0,unv-needs);
 bits.push(S.score_note?S.score_note:"Score: "+sup+" of "+checked+" checked claims supported");
 if(needs)bits.push(needs+(needs===1?" claim needs":" claims need")+" a source: no official dataset in TruthLens covers "+(needs===1?"it":"them")+" yet. That is not wrong; download the list and cite a source");
 if(other)bits.push(other+" not checked this run (a source didn't answer, Quick mode or time limit)");
 if(dat)bits.push(dat+(dat===1?" figure is":" figures are")+" dated: compared with official data for another year or for the State before a boundary change. Not wrong, but not today's figure");
 $("citebtn").hidden=!((R.claims_to_cite||[]).length||unv);
 if(S.suggested_fixes)bits.push(S.suggested_fixes+(S.suggested_fixes===1?" suggested fix":" suggested fixes")+" ready");
 if(S.hedged_factual)bits.push(S.hedged_factual+(S.hedged_factual===1?" opinion-worded sentence contains a factual claim and was checked":" opinion-worded sentences contain factual claims and were checked"));
 if(low)bits.push(low===sup?(low===1?"the supported claim rests":"all supported claims rest")+" on a word match only (low confidence)":low+" of the supported rest on a word match only (low confidence)");
 $("subline").textContent=checkable?(bits.length?bits.join(" · ")+".":"Nothing contradicts the sources."):"Try a draft with numbers, named facts or citations.";
 /* v0.5.2: which mode ran, and a Deep check button for the claims Quick mode left unchecked */
 var rs=S.couldnt_check_reasons||{},nq=(rs.quick||{}).claims||0;
 $("modeline").hidden=!S.mode;$("modetag").textContent=S.mode==="deep"?"Deep check":"Quick check";
 $("modetext").textContent=S.mode==="quick"?(nq?nq+(nq===1?" claim":" claims")+" not checked in Quick mode":"Every claim was checked from saved official data")
   :(S.statements!=null?S.statements+" statements · "+(S.checkable||0)+" checkable claims":"");
 $("deepbtn").hidden=!(S.mode==="quick"&&nq&&lastJob);$("deepbtn").textContent="Deep check (about 1 min)";
 /* v0.4.1 banner, v0.5.2 short: the top reasons in one line, the per-source detail collapsed */
 var bn=[],un=S.unreachable_sources||[];
 if(S.offline)bn.push("Offline run: live sources were not consulted, so more claims show as couldn't check.");
 var det=[];Object.keys(rs).forEach(function(k){if(rs[k].claims)det.push(rs[k].label+": "+rs[k].claims);});
 un.forEach(function(u){if(u.claims_affected)det.push(u.source+": didn't respond ("+u.claims_affected+(u.claims_affected===1?" claim":" claims")+")");});
 $("bdlist").textContent="";det.forEach(function(d){add($("bdlist"),el("li",{text:d}));});$("bdetails").hidden=!det.length;
 if(S.banner){if(S.banner.text)bn.push(S.banner.text);}
 else if(un.length)bn.push("Unreachable this run: "+un.map(function(u){return u.source+(u.claims_affected?" ("+u.claims_affected+(u.claims_affected===1?" claim":" claims")+" affected)":" (error during the run; "+(u.claims_asked||0)+" asked it)");}).join("; ")+".");
 var dl=S.live_deadline||{};if(dl.claims_hit_deadline&&!S.banner)bn.push(dl.claims_hit_deadline+(dl.claims_hit_deadline===1?" claim":" claims")+" ran out of time ("+Math.round(dl.budget_s||0)+" s limit for live checks); "+(dl.claims_hit_deadline_unverified||0)+" of them show as couldn't check. A timeout never counts as supported or wrong.");
 var bne=$("banner");bne.textContent=bn.join(" ");bne.hidden=!bn.length;
 /* meter */
 var pct=score==null?0:Math.max(0,Math.min(100,score));var C=339.29;
 $("meter").setAttribute("aria-label",score==null?"Verified score not available":"Verified score "+Math.round(pct)+" percent");
 var mv=$("meterval");mv.style.transition="none";mv.setAttribute("stroke-dashoffset",C);void mv.getBoundingClientRect();mv.style.transition="";
 requestAnimationFrame(function(){mv.setAttribute("stroke-dashoffset",C*(1-pct/100));});
 var sc=$("score");
 if(S.score_note){score=null;pct=0;$("meter").setAttribute("aria-label",S.score_note);mv.setAttribute("stroke-dashoffset",C);}
 if(score==null){sc.textContent="—";}
 else if(RM.matches){sc.textContent=Math.round(pct)+"%";}
 else{var t0=performance.now();(function step(t){var k=Math.min(1,(t-t0)/1100);k=1-Math.pow(1-k,3);sc.textContent=Math.round(pct*k)+"%";if(k<1)requestAnimationFrame(step);})(t0);}
 /* chips */
 var chips=$("chips");chips.textContent="";
 var chipList=[];ORDER.forEach(function(key){
  if(key==="UNVERIFIED"){var rsn=S.couldnt_check_reasons;
   if(rsn){REASONS.forEach(function(r,i){var n=(rsn[r[0]]||{}).claims||0;if(n)chipList.push({key:"UNVERIFIED:"+r[0],n:n,l:r[1],c:i?"unvr":"unv"});});return;}}
  var n=v[key]||0,m=V[key];if(n&&m)chipList.push({key:key,n:n,l:m.l,c:m.c});});
 chipList.forEach(function(ch){ /* a chip that filters to nothing is noise */
  var b=el("button",{class:"chip "+ch.c,type:"button","aria-pressed":"false","data-v":ch.key,
   "aria-label":"Show only "+ch.l.toLowerCase()+": "+ch.n},el("span",{class:"sw","aria-hidden":"true"}),el("b",{text:ch.n}),ch.l);
  b.addEventListener("click",function(){setFilter(filter===ch.key?null:ch.key);});chips.appendChild(b);});
 /* doc head */
 function pl(n,one,many){return n+" "+(n===1?one:many);}
 $("dochead").textContent=(!R.input||R.input==="text input")?"Pasted text":R.input;
 $("docmeta").textContent=pl(S.sentences||0,"sentence","sentences")+" · "+pl(S.claims||0,"claim","claims")+(skp?" · "+pl(skp,"opinion skipped","opinions skipped"):"");
 drawDraft();
 emptyPanel();
}
function drawDraft(){
 var d=$("draft");d.textContent="";var by={};
 R.sentences.forEach(function(s){(by[s.block]=by[s.block]||[]).push(s);});
 var n=0,num={};R.sentences.forEach(function(s){if(V[s.verdict]&&s.verdict!=="SKIPPED"&&(claimsBySid[s.id]||[]).length)num[s.id]=++n;});
 (R.blocks||[]).forEach(function(b,bi){
  var p=el("p",{class:String(b.location||"").indexOf("table")===0?"trow":null});var ss=by[bi]||[];
  if(!ss.length)add(p,b.text);
  ss.forEach(function(s,i){if(i)add(p," ");
   var m=V[s.verdict];
   if(num[s.id]){
    var sp=el("span",{class:"s "+m.c+(fixes[s.id]!=null?" fixed":"")+(filter&&fmatch(s,filter)?" match":"")+(current===s.id?" sel":""),
     tabindex:"0",role:"button","data-sid":s.id,"aria-pressed":current===s.id?"true":"false"},sentText(s),
     el("span",{class:"sr",text:" ("+(fixes[s.id]!=null?"fix accepted, was ":"")+m.l+", finding "+num[s.id]+")"}));
    sp.addEventListener("click",function(){select(s.id,true);});
    sp.addEventListener("keydown",function(e){if(e.key==="Enter"||e.key===" "){e.preventDefault();select(s.id,true);}});
    add(p,sp);add(p,el("span",{class:"mk "+m.c+(filter&&fmatch(s,filter)?" match":""),"aria-hidden":"true",text:num[s.id]}));
   }else add(p,sentText(s));});
  d.appendChild(p);});
 if(filter)d.setAttribute("data-filter",filter);else d.removeAttribute("data-filter");
}
function setFilter(key){filter=key;
 $("chips").querySelectorAll(".chip").forEach(function(c){c.setAttribute("aria-pressed",c.getAttribute("data-v")===key?"true":"false");});
 drawDraft();
 var f=findings();
 if(key&&f.length&&(!current||!fmatch(sentById[current],key))){if(!PHONE.matches)select(f[0].id,false);}
 else if(current)markSel();}
function markSel(){$("draft").querySelectorAll(".s").forEach(function(x){var on=x.getAttribute("data-sid")===current;x.classList.toggle("sel",on);x.setAttribute("aria-pressed",on?"true":"false");});}

function emptyPanel(){var pb=$("panelbody");pb.textContent="";
 pb.appendChild(el("div",{class:"empty"},el("div",{class:"ic"},svg("pointer")),el("b",{text:"Select a highlighted sentence"}),"Its verdict, the evidence and any suggested fix will appear here."));}

function select(sid,fromUser){
 current=sid;markSel();renderPanel(fromUser===true&&!PHONE.matches);
 var sp=$("draft").querySelector('[data-sid="'+sid+'"]');
 if(PHONE.matches){openSheet(sp);}
 else if(sp&&fromUser!==false){sp.scrollIntoView({block:"nearest",behavior:(RM.matches||fromUser==="key")?"auto":"smooth"});}
 if(fromUser==="key"&&sp&&!PHONE.matches)sp.focus({preventScroll:true});}
function move(dir){var f=findings();if(!f.length)return;var i=f.findIndex(function(s){return s.id===current;});
 i=i<0?(dir>0?0:f.length-1):(i+dir+f.length)%f.length;select(f[i].id,"key");}

function renderPanel(anim){
 var pb=$("panelbody");pb.textContent="";var s=sentById[current];if(!s){emptyPanel();return;}
 var f=findings(),idx=f.findIndex(function(x){return x.id===current;});
 var head=el("div",{class:"ph"},
  el("span",{class:"pos",text:idx>=0?("Finding "+(idx+1)+" of "+f.length+(filter?" "+filterLabel(filter).toLowerCase():"")):""}),
  el("div",{class:"nav"},
   el("button",{class:"iconbtn",type:"button","aria-label":"Previous finding",title:"Previous (K)",onclick:function(){move(-1);}},svg("up")),
   el("button",{class:"iconbtn",type:"button","aria-label":"Next finding",title:"Next (J)",onclick:function(){move(1);}},svg("down")),
   el("button",{class:"iconbtn close",type:"button","aria-label":"Close",onclick:closeSheet},svg("x"))));
 pb.appendChild(head);
 var cs=(claimsBySid[s.id]||[]).slice().sort(function(a,b){return ORDER.indexOf(a.verdict)-ORDER.indexOf(b.verdict);});
 cs.forEach(function(c){var v=findingView(c,s);if(anim&&!RM.matches)v.classList.add("in");pb.appendChild(v);});
}
function findingView(c,s){
 var m=V[c.verdict]||V.UNVERIFIED,cl=c.claim||{},box=el("div",{class:"finding"});
 var lowsup=c.verdict==="SUPPORTED"&&c.confidence==="low";
 add(box,el("span",{class:"verdict "+m.c},svg(m.i),m.l+(lowsup?" · low confidence":"")));
 var meta=[TYPE[cl.type]||cl.type,cl.location];if(c.confidence&&c.confidence!=="n/a")meta.push(c.confidence+" confidence");
 add(box,el("p",{class:"meta",text:meta.filter(Boolean).join(" · ")}));
 add(box,el("p",{class:"plain",text:lowsup?"A source uses the same words and figures, but only a word match decided this (no AI judge). Read the evidence before you rely on it.":m.p}));
 if(cl.hedged)add(box,el("p",{class:"meta"},el("span",{class:"tagx",text:"contains a factual claim"})," Opinion wording set aside; the factual part was checked."));
 if(c.failed_part)add(box,el("p",{class:"why failp"},el("b",{text:"Failed part: "}),c.failed_part));
 if(c.rationale)add(box,el("p",{class:"why",text:c.rationale}));
 if(cl.text&&cl.sentence&&cl.text!==cl.sentence)add(box,el("p",{class:"meta",text:"Claim checked: “"+clip(cl.text,240)+"”"}));
 /* superseded: the draft's figure was right for an older release or period */
 var sup=(c.warnings||[]).filter(function(w){return w.code==="superseded";})[0];
 if(sup)add(box,el("p",{class:"super",role:"note"},svg("warn"),el("span",{},el("b",{text:"Superseded. "}),String(sup.message||"").replace(/^Superseded:\s*/,""))));
 /* suggested fix first: it's the action */
 if(c.suggested_fix){
  add(box,el("h4",{class:"blockh",text:"Suggested fix"}));
  var accepted=fixes[s.id]===c.suggested_fix;
  var ft=el("div",{class:"ft"});diffInto(ft,s.text,c.suggested_fix);
  var fa=el("div",{class:"fa"});
  if(accepted){add(fa,el("span",{class:"ok"},svg("check"),"Applied"));
   add(fa,el("button",{class:"btn ghost",type:"button",onclick:function(){delete fixes[s.id];drawDraft();renderPanel();toast("Fix undone");}},svg("undo"),"Undo"));}
  else{add(fa,el("button",{class:"btn primary",type:"button",onclick:function(){fixes[s.id]=c.suggested_fix;drawDraft();renderPanel();toast("Fix applied to your text");}},svg("check"),"Accept fix"));}
  add(fa,el("button",{class:"btn ghost",type:"button",onclick:function(){copy(c.suggested_fix).then(function(){toast("Fix copied");},function(){toast("Could not copy");});}},svg("copy"),"Copy fix"));
  add(box,el("div",{class:"fix"},ft,fa));
  if(c.fix_source)add(box,el("p",{class:"meta",text:"Source for the fix: "+String(c.fix_source).replace(/^\s*source:\s*/i,"")}));}
 /* warnings */
 var ws=(c.warnings||[]).filter(function(w){return w.code!=="superseded";}).slice(0,3);
 if(ws.length){add(box,el("h4",{class:"blockh",text:"Worth knowing"}));
  add(box,el("ul",{class:"warns"},ws.map(function(w){return el("li",{},svg("warn"),el("span",{text:w.message||""}));})));}
 /* evidence */
 var quoted={};(c.quotes||[]).forEach(function(q){quoted[q.evidence_id]=q.quote;});
 var ev=(c.evidence||[]).slice().sort(function(a,b){return (quoted[b.id]?1:0)-(quoted[a.id]?1:0)||((b.kind==="datapoint")-(a.kind==="datapoint"));}).slice(0,c.verdict==="UNVERIFIED"?2:3);
 if(ev.length){add(box,el("h4",{class:"blockh",text:ev.length===1?"Evidence":"Evidence ("+ev.length+")"}));
  ev.forEach(function(e){var text=quoted[e.id]||e.quote||e.snippet||"";var url=safeUrl(e.source_url),a=asOf(e);
   var src=el("span",{class:"src"},el("span",{class:"stype",text:stype(e)}),
    e.not_live_verified?el("span",{class:"stype nlv",title:"Not live-verified: this source was tested only on synthetic or rate-limited fixtures",text:"unverified source"}):null,
    el("span",{text:[e.publisher,e.page?"page "+e.page:""].filter(Boolean).join(" · ")}),
    a?el("span",{class:"asof",text:"Data as of "+a}):null,
    e.kind==="catalogue"?el("span",{class:"asof",text:"Dataset to cite; not used as evidence"}):null);
   var acts=el("span",{class:"src"},
    url?el("a",{href:url,target:"_blank",rel:"noopener noreferrer"},"Open source"+(host(url)?" ("+host(url)+")":""),svg("ext")):null,
    el("button",{class:"cite",type:"button","aria-label":"Copy citation for this source",onclick:function(){copy(citation(e)).then(function(){toast("Citation copied");},function(){toast("Could not copy");});}},svg("copy"),"Copy citation"));
   add(box,el("blockquote",{class:quoted[e.id]?"q":null},"“"+clip(text,420)+"”",src,acts));});}
 /* citations */
 var cc=c.citation_checks||[];
 if(cc.length){add(box,el("h4",{class:"blockh",text:"Citations in this sentence"}));
  var ST={found:["found","ok"],not_found:["does not exist","bad"],unreachable:["could not be opened",""],unresolved:["could not be resolved",""],empty:["has no readable text",""]};
  var SUP={supports:"and contains the claim",partial:"and partly matches",number_missing:"but does not contain the figure",not_in_source:"but does not mention the claim"};
  add(box,el("ul",{class:"cites"},cc.map(function(x){var st=ST[x.status]||[x.status||"",""];
   return el("li",{},clip(x.citation,70)+" ",el("b",{class:st[1],text:st[0]}),SUP[x.support]?" "+SUP[x.support]:"",x.title?" · "+clip(x.title,90):"");})));}
 add(box,wrongBox(c,s));
 return box;}

/* v0.5: "This verdict is wrong" -> a pending correction stored locally for review (never applied automatically) */
var PUBLICMODE=false;fetch("health").then(function(r){return r.json();}).then(function(d){PUBLICMODE=!!(d&&d.public&&!d.corrections);}).catch(function(){});
function wrongBox(c,s){var cl=c.claim||{},wrap=el("div",{class:"wrong"}),opened=false;
 if(PUBLICMODE)return wrap;   /* v0.5.2: a shared public server does not store user-submitted corrections */
 var btn=el("button",{class:"btn quiet",type:"button","aria-expanded":"false"},"This verdict is wrong");
 btn.addEventListener("click",function(){if(opened)return;opened=true;btn.setAttribute("aria-expanded","true");
  var sel=el("select",{"aria-label":"Correct verdict"});
  ["CONTRADICTED","PARTLY SUPPORTED","DATED","UNVERIFIED","SUPPORTED"].filter(function(v){return v!==c.verdict;}).forEach(function(v){add(sel,el("option",{value:v,text:(V[v]||{}).l||v}));});
  var note=el("textarea",{rows:"2",maxlength:"1000","aria-label":"Note (optional)",placeholder:"What is wrong? (optional)"});
  var url=el("input",{type:"url",maxlength:"500","aria-label":"Source link (optional)",placeholder:"https://… source that shows the right answer (optional)"});
  var send=el("button",{class:"btn primary",type:"submit"},"Send for review");
  var f=el("form",{},el("label",{text:"The correct verdict is"}),sel,note,url,send,
   el("p",{class:"meta",text:"Saved on this computer for review with `truthlens corrections review`. Nothing changes until a person accepts it."}));
  f.addEventListener("submit",async function(ev){ev.preventDefault();send.disabled=true;
   try{var r=await fetch("corrections",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({
     claim_text:cl.text||s.text,sentence:cl.sentence||s.text,claim_type:cl.type||"numeric",reported_verdict:c.verdict,
     correct_verdict:sel.value,note:note.value,source_url:url.value.trim(),document:(R&&R.input)||""})});
    if(!r.ok){var d=await r.json().catch(function(){return {};});throw new Error(typeof d.detail==="string"?d.detail:"could not save");}
    wrap.textContent="";add(wrap,el("p",{class:"meta",text:"Thanks. Saved for review."}));toast("Correction saved for review");}
   catch(e){send.disabled=false;toast("Not saved: "+String(e.message||e).slice(0,120));}});
  add(wrap,f);});
 add(wrap,btn);return wrap;}

/* v0.5: "Last updated" and "Update now" */
var freshT=null;
async function freshness(){try{var r=await fetch("sync/status");if(!r.ok)return;var d=await r.json();
  var f=$("fresh"),b=$("updnow");f.className="fresh"+(d.stale&&d.last_synced?" stale":"");
  f.textContent=d.running?"Updating official data…":(d.last_synced?("Last updated "+new Date(d.last_synced).toLocaleDateString(undefined,{day:"numeric",month:"short",year:"numeric"})+(d.stale?" (more than 7 days ago)":"")):"Using the official data bundled with TruthLens");
  b.disabled=!!(d.running||d.offline);b.hidden=!!d.offline;
  clearTimeout(freshT);if(d.running)freshT=setTimeout(freshness,4000);}catch(e){}}
$("deepbtn").addEventListener("click",runDeep);
$("updnow").addEventListener("click",async function(){this.disabled=true;
 try{var r=await fetch("sync",{method:"POST"});var d=await r.json().catch(function(){return {};});
  toast(r.ok?"Updating official data in the background":String(d.detail||"Could not start the update"));}catch(e){toast("Could not start the update");}
 freshness();});
freshness();

/* word diff (LCS) -> del/ins nodes, text only */
function diffInto(node,a,b){
 var A=a.match(/\S+|\s+/g)||[],B=b.match(/\S+|\s+/g)||[],n=A.length,m=B.length;
 if(n*m>250000){add(node,el("del",{text:a}));add(node," ");add(node,el("ins",{text:b}));return;}
 var L=[];for(var i=0;i<=n;i++){L.push(new Uint16Array(m+1));}
 for(i=n-1;i>=0;i--)for(var j=m-1;j>=0;j--)L[i][j]=A[i]===B[j]?L[i+1][j+1]+1:Math.max(L[i+1][j],L[i][j+1]);
 var out=[],x=0,y=0;function push(t,s){var l=out[out.length-1];if(l&&l[0]===t)l[1]+=s;else out.push([t,s]);}
 while(x<n&&y<m){if(A[x]===B[y]){push("=",A[x]);x++;y++;}else if(L[x+1][y]>=L[x][y+1]){push("-",A[x]);x++;}else{push("+",B[y]);y++;}}
 while(x<n)push("-",A[x++]);while(y<m)push("+",B[y++]);
 out.forEach(function(o){if(o[0]==="=")add(node,o[1]);else if(o[0]==="-"){if(o[1].trim())add(node,el("del",{text:o[1]}));}else add(node,el("ins",{text:o[1]}));});}

/* bottom sheet on phone */
function openSheet(from){openerEl=from||openerEl;$("panel").classList.add("open");$("scrim").classList.add("on");$("panel").setAttribute("aria-modal","true");$("panel").setAttribute("role","dialog");
 $("panel").scrollTop=0;setTimeout(function(){$("panel").focus({preventScroll:true});},RM.matches?0:60);}
function closeSheet(){var p=$("panel");if(!p.classList.contains("open"))return;p.classList.remove("open");$("scrim").classList.remove("on");p.removeAttribute("aria-modal");p.removeAttribute("role");
 if(openerEl)openerEl.focus({preventScroll:true});}
$("scrim").addEventListener("click",closeSheet);
PHONE.addEventListener&&PHONE.addEventListener("change",function(e){if(!e.matches)closeSheet();});

/* keyboard: J/K between findings, Esc closes */
document.addEventListener("keydown",function(e){
 if(document.body.dataset.state!=="results")return;
 var t=e.target;if(t&&(t.tagName==="INPUT"||t.tagName==="TEXTAREA"||t.tagName==="SELECT"||t.isContentEditable))return;
 if(e.metaKey||e.ctrlKey||e.altKey)return;
 if(e.key==="j"||e.key==="J"){e.preventDefault();move(1);}
 else if(e.key==="k"||e.key==="K"){e.preventDefault();move(-1);}
 else if(e.key==="Escape"){if(PHONE.matches)closeSheet();}});

/* actions */
function correctedText(){var by={};R.sentences.forEach(function(s){(by[s.block]=by[s.block]||[]).push(s);});
 return (R.blocks||[]).map(function(b,bi){var ss=by[bi]||[];return ss.length?ss.map(sentText).join(" "):b.text;}).join("\n\n");}
$("copyall").addEventListener("click",function(){var n=Object.keys(fixes).length;
 copy(correctedText()).then(function(){toast(n?"Copied with "+n+(n===1?" fix":" fixes")+" applied":"Copied. Accept fixes to include them");},function(){toast("Could not copy");});});
$("download").addEventListener("click",async function(){var b=this;b.disabled=true;
 try{var r=await fetch("render?format=html",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(R)});
  if(!r.ok)throw new Error();var blob=await r.blob();var a=el("a",{href:URL.createObjectURL(blob),download:"truthlens-report.html"});
  document.body.appendChild(a);a.click();setTimeout(function(){URL.revokeObjectURL(a.href);a.remove();},1000);toast("Report downloaded");}
 catch(e){toast("Could not build the report");}finally{b.disabled=false;}});
$("citebtn").addEventListener("click",async function(){var b=this;b.disabled=true;
 try{var r=await fetch("render?format=cite",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(R)});
  if(!r.ok)throw new Error();var blob=await r.blob();var a=el("a",{href:URL.createObjectURL(blob),download:"claims-to-cite.csv"});
  document.body.appendChild(a);a.click();setTimeout(function(){URL.revokeObjectURL(a.href);a.remove();},1000);toast("List of claims to cite downloaded");}
 catch(e){toast("Could not build the list");}finally{b.disabled=false;}});
function again(){closeSheet();R=null;show("start");}
$("again").addEventListener("click",again);
})();
</script>
</body></html>"""
