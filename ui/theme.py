"""Visual theme for the Streamlit app (Person E).

Direction: a first-party Apple/Stripe-grade web app. System type (SF Pro on
Apple devices, Inter elsewhere), a neutral grey canvas with white cards and
soft layered shadows, pill buttons, a segmented control for navigation, and a
frosted top bar. The one signature element is the degree *route*: semesters
as grouped lists hung on a timeline (solid dot = completed, ring = planned).

Streamlit's default chrome (sidebar, header, avatars, borders) is restyled or
hidden here. Contrast figures for every token pair: deliverables/design_review.md.
"""

import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
  --font: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", "Helvetica Neue", system-ui, sans-serif;
  --font-display: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Inter", "Helvetica Neue", system-ui, sans-serif;
  --page: #F5F5F7;
  --card: #FFFFFF;
  --text: #1D1D1F;
  --text-2: #6E6E73;           /* 4.66:1 on page, 5.07:1 on card */
  --hairline: rgba(0, 0, 0, .08);
  --fill: rgba(0, 0, 0, .05);  /* secondary buttons, segmented track */
  --edge: #86868B;             /* non-text outlines, 3.62:1 */
  --blue: #0071E3;             /* buttons: white text 4.70:1 */
  --blue-text: #0066CC;        /* text/links: 5.57:1 */
  --blue-tint: #E8F1FC;
  --green: #1E7B34;
  --green-tint: #E8F5EC;
  --red: #C4141F;
  --red-tint: #FDECEC;
  --orange: #A04A00;
  --orange-tint: #FFF3E3;
  --bubble-them: #E9E9EB;
  --glass: rgba(245, 245, 247, .78);
  --shadow: 0 1px 2px rgba(0,0,0,.04), 0 6px 24px rgba(0,0,0,.06);
  --shadow-pop: 0 2px 6px rgba(0,0,0,.08), 0 18px 48px rgba(0,0,0,.14);
  --radius: 18px;
  /* Apple-like curves: a soft spring for entrances, iOS sheet curve for dialogs */
  --spring: cubic-bezier(.22, 1, .36, 1);
  --sheet: cubic-bezier(.32, .72, 0, 1);
}
@media (prefers-color-scheme: dark) {
  :root {
    --page: #000000;
    --card: #1C1C1E;
    --text: #F5F5F7;
    --text-2: #A1A1A6;           /* 6.61:1 on card */
    --hairline: rgba(255, 255, 255, .10);
    --fill: rgba(255, 255, 255, .08);
    --edge: #6C6C70;
    --blue-text: #4DA3FF;
    --blue-tint: #0F2540;
    --green: #4CD07D;
    --green-tint: #12301D;
    --red: #FF6961;
    --red-tint: #3A1717;
    --orange: #FFB340;
    --orange-tint: #33240C;
    --bubble-them: #2C2C2E;
    --glass: rgba(0, 0, 0, .72);
    --shadow: 0 0 0 1px rgba(255,255,255,.06);
    --shadow-pop: 0 0 0 1px rgba(255,255,255,.08), 0 18px 48px rgba(0,0,0,.6);
  }
}
@media (prefers-contrast: more) {
  :root { --text-2: var(--text); --hairline: var(--edge); }
}

/* ---------------- base + Streamlit chrome ---------------- */
html, body, .stApp, .stMarkdown, button, input, textarea, select, label, p, li,
[data-testid="stWidgetLabel"] { font-family: var(--font) !important; }
.stApp { background: var(--page); color: var(--text); -webkit-font-smoothing: antialiased; }
h1, h2, h3, h4 { font-family: var(--font-display) !important; color: var(--text);
                 letter-spacing: -0.022em; }
[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"], footer { display: none !important; }
.block-container { max-width: 1080px; padding: 0 1.5rem 6rem; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: var(--text-2) !important; }
:focus-visible { outline: 3px solid color-mix(in srgb, var(--blue) 55%, transparent) !important;
                 outline-offset: 2px; }
hr { border-color: var(--hairline) !important; }

/* ---------------- frosted top bar ---------------- */
.st-key-topbar { position: sticky; top: 0; z-index: 100; margin: 0 -1.5rem 2.5rem;
  padding: .55rem 1.5rem; background: var(--glass);
  -webkit-backdrop-filter: saturate(180%) blur(20px); backdrop-filter: saturate(180%) blur(20px);
  /* full-bleed glass: extend the bar's background to the window edges */
  box-shadow: 0 0 0 100vmax var(--glass); clip-path: inset(0 -100vmax); }
.st-key-topbar::after { content: ""; position: absolute; left: -100vmax; right: -100vmax; bottom: 0;
  height: 1px; background: var(--hairline); }
/* The full-bleed hairline above counts as overflow; nothing here scrolls sideways. */
[data-testid="stMain"], [data-testid="stAppScrollToBottomContainer"] { overflow-x: hidden; }
[data-testid="stPopover"] button > div > div:last-child { display: none; }  /* menu chevron */
.adv-wordmark { display: flex; align-items: center; gap: .55rem; font-weight: 600;
                font-size: 1.05rem; letter-spacing: -0.01em; color: var(--text); white-space: nowrap; }
.adv-mark { position: relative; width: 12px; height: 22px; flex: none; }
.adv-mark::before { content: ""; position: absolute; left: 5px; top: 3px; bottom: 3px; width: 2px;
                    background: var(--text); opacity: .2; }
.adv-mark i { position: absolute; left: 1px; width: 10px; height: 10px; border-radius: 50%; }
.adv-mark i:first-child { top: 0; background: var(--green); }
.adv-mark i:last-child { bottom: 0; background: var(--card); box-shadow: inset 0 0 0 2px var(--blue); }
.ic { font-weight: 700; line-height: 1; font-size: .8rem; font-style: normal; }

/* ---------------- controls ---------------- */
.stButton > button, .stFormSubmitButton > button, [data-testid="stPopover"] button {
  border-radius: 980px !important; font-weight: 500; font-size: .95rem;
  padding: .45rem 1.15rem; min-height: 2.5rem; border: 0 !important;
  background: var(--fill); color: var(--text); box-shadow: none; transition: background .15s, transform .1s; }
.stButton > button:hover, [data-testid="stPopover"] button:hover {
  background: color-mix(in srgb, var(--text) 10%, transparent); color: var(--text); }
.stButton > button:active { transform: scale(.98); }
.stButton > button[kind="primary"], .stFormSubmitButton > button { background: var(--blue) !important; color: #fff !important; }
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button:hover { background: #0077ED !important; }
.stButton > button[kind="primary"] p, .stFormSubmitButton > button p { color: #fff !important; }
.stButton > button:disabled { opacity: .45; }

[data-baseweb="select"] > div, .stNumberInput [data-baseweb="input"] {
  border-radius: 12px !important; background: var(--card) !important;
  border: 1px solid var(--hairline) !important; box-shadow: none !important; }
[data-baseweb="select"] > div:hover { border-color: var(--edge) !important; }
[data-testid="stWidgetLabel"] p { font-size: .82rem !important; font-weight: 500; color: var(--text-2); }
[data-baseweb="popover"] > div { border-radius: 14px !important; }

/* segmented control (navigation) */
[data-testid="stButtonGroup"] > div { background: var(--fill); padding: 3px; border-radius: 10px;
  gap: 2px !important; width: fit-content; }
[data-testid="stButtonGroup"] button { border: 0 !important; border-radius: 8px !important;
  background: transparent !important; font-weight: 500; font-size: .9rem; min-height: 2rem;
  padding: .25rem .95rem !important; box-shadow: none !important; }
[data-testid="stButtonGroup"] button p { color: var(--text) !important; }
[data-testid="stButtonGroup"] button[aria-checked="true"] { background: var(--card) !important;
  box-shadow: 0 1px 3px rgba(0,0,0,.12), 0 0 0 .5px rgba(0,0,0,.04) !important; }

/* cards: st.container(key="card_*") */
[class*="st-key-card_"] { background: var(--card); border-radius: var(--radius);
  box-shadow: var(--shadow); padding: 1.75rem 1.9rem; margin-bottom: 1.25rem; }
[class*="st-key-card_"] h3 { font-size: 1.35rem; font-weight: 600; margin: 0 0 .25rem; padding: 0; }
.stForm { border: 0 !important; padding: 0 !important; }
[data-testid="stExpander"] details { border: 1px solid var(--hairline) !important; border-radius: 12px !important; background: var(--card); }

/* dialogs + toasts */
[role="dialog"] { border-radius: 22px !important; box-shadow: var(--shadow-pop) !important; }
[data-testid="stToast"] { border-radius: 14px !important; box-shadow: var(--shadow-pop) !important; }

/* ---------------- chat (iMessage-style) ---------------- */
[data-testid="stChatMessage"] { background: transparent !important; padding: .15rem 0 !important; gap: 0; }
[data-testid^="stChatMessageAvatar"] { display: none !important; }
[data-testid="stChatMessage"] { justify-content: flex-start; }
[data-testid="stChatMessageContent"] { background: var(--bubble-them); border-radius: 20px;
  padding: .65rem 1rem; max-width: min(78%, 640px); flex: 0 1 auto; margin: 0 !important; }
[data-testid="stChatMessageContent"] p { margin: 0 0 .4rem; line-height: 1.45; }
[data-testid="stChatMessageContent"] p:last-child { margin-bottom: 0; }
[data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] { margin-bottom: 0 !important; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { justify-content: flex-end; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] {
  background: var(--blue); margin-left: auto !important; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] * { color: #fff !important; }
[data-testid="stChatInput"] { border-radius: 24px !important; background: var(--card) !important;
  box-shadow: var(--shadow-pop) !important; border: 1px solid var(--hairline) !important; }
[data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] { background: transparent !important; }
[data-testid="stBottomBlockContainer"] { max-width: 1080px; margin: 0 auto; padding: 1rem 1.5rem 1.75rem !important; }
.st-key-suggestions .stButton > button { background: var(--card); box-shadow: var(--shadow);
  font-size: .88rem; min-height: 2.25rem; }

/* ---------------- hero ---------------- */
.adv-hero { margin: 0 0 2.25rem; }
.adv-hero h1 { font-size: clamp(2.2rem, 4.5vw, 3.25rem); font-weight: 700; line-height: 1.05;
               letter-spacing: -0.03em; margin: 0 0 .4rem; padding: 0; }
.adv-hero .sub { font-size: 1.2rem; color: var(--text-2); margin: 0 0 1.6rem; letter-spacing: -0.01em; }
.adv-progress { height: 8px; border-radius: 4px; background: var(--fill); display: flex; overflow: hidden; }
.adv-progress span { height: 100%; }
.adv-progress .done { background: var(--green); }
.adv-progress .planned { background: var(--blue); }
.adv-stats { display: flex; flex-wrap: wrap; gap: .5rem 2rem; margin-top: .8rem; font-size: .95rem; color: var(--text-2); }
.adv-stats b { color: var(--text); font-weight: 600; font-variant-numeric: tabular-nums; }
.adv-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: .45rem; vertical-align: 1px; }
.adv-dot.ring { box-shadow: inset 0 0 0 1.5px var(--edge); }

/* ---------------- route: grouped lists on a timeline ---------------- */
.adv-route { position: relative; padding-left: 2.1rem; margin-top: .5rem; }
.adv-route::before { content: ""; position: absolute; left: 7px; top: 10px; bottom: 10px;
                     width: 2px; background: var(--hairline); }
.adv-sem { position: relative; margin-bottom: 1.6rem; }
.adv-sem::before { content: ""; position: absolute; left: calc(-2.1rem + 1px); top: 5px; width: 14px; height: 14px;
                   border-radius: 50%; background: var(--card); box-shadow: inset 0 0 0 2px var(--blue); }
.adv-sem.done::before { background: var(--green); box-shadow: none; }
.adv-sem-head { display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; margin-bottom: .55rem; }
.adv-sem-title { font-family: var(--font-display); font-size: 1.15rem; font-weight: 600; letter-spacing: -0.015em; }
.adv-sem-meta { font-size: .88rem; color: var(--text-2); font-variant-numeric: tabular-nums; }
.adv-list, .adv-list > li { margin: 0 !important; }
.adv-list { list-style: none; padding: 0 !important; background: var(--card); border-radius: 14px;
            box-shadow: var(--shadow); overflow: hidden; }
.adv-row { display: grid; grid-template-columns: 6.2rem 1fr auto; gap: 1rem; align-items: baseline;
           padding: .78rem 1.1rem; font-size: .95rem; }
.adv-row + .adv-row { border-top: 1px solid var(--hairline); }
.adv-code { font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap; }
.adv-meta { color: var(--text-2); font-variant-numeric: tabular-nums; white-space: nowrap; }
.adv-grade { display: inline-block; min-width: 1.6rem; text-align: center; font-weight: 600; color: var(--green);
             background: var(--green-tint); border-radius: 6px; padding: 0 .3rem; margin-right: .6rem; }

/* ---------------- notes ---------------- */
.adv-note { display: flex; gap: .7rem; align-items: flex-start; background: var(--card); border-radius: 14px;
            box-shadow: var(--shadow); padding: .85rem 1.1rem; margin: 0 0 1.25rem; font-size: .93rem; line-height: 1.45; }
.adv-note .ic { flex: none; display: grid; place-items: center; width: 1.25rem; height: 1.25rem;
                border-radius: 50%; margin-top: .05rem; font-size: .75rem; color: #fff !important; }
.adv-note.caution .ic { background: var(--orange); }
.adv-note.info .ic { background: var(--blue-text); }
@media (prefers-color-scheme: dark) { .adv-note .ic { color: #000 !important; } }
.adv-badge { display: inline-flex; align-items: center; gap: .35rem; font-size: .78rem; font-weight: 600;
             padding: .2rem .6rem; border-radius: 980px; background: var(--orange-tint); color: var(--orange); white-space: nowrap; }

/* ---------------- six checks ---------------- */
.adv-verdict { display: flex; gap: .6rem; align-items: center; font-weight: 600; font-size: 1.02rem; margin: 1rem 0 .25rem; }
.adv-verdict.pass { color: var(--green); }
.adv-verdict.fail { color: var(--red); }
.adv-check { display: grid; grid-template-columns: 1.6rem 1fr auto; gap: .2rem .8rem; align-items: center;
             padding: .85rem 1.1rem; }
.adv-check + .adv-check { border-top: 1px solid var(--hairline); }
.adv-check .ic { display: grid; place-items: center; width: 1.45rem; height: 1.45rem; border-radius: 50%; }
.adv-check .ic.pass { background: var(--green-tint); color: var(--green); }
.adv-check .ic.fail { background: var(--red-tint); color: var(--red); }
.adv-check .ic.wait { background: var(--fill); color: var(--text-2); }
.adv-check-name { font-weight: 500; }
.adv-check-letter { color: var(--text-2); font-variant-numeric: tabular-nums; margin-right: .35rem; }
.adv-check-state { font-size: .88rem; font-weight: 600; }
.adv-check-state.pass { color: var(--green); }
.adv-check-state.fail { color: var(--red); }
.adv-check-state.wait { color: var(--text-2); }
.adv-check-detail { grid-column: 2 / 4; color: var(--text-2); font-size: .88rem; }

/* ---------------- comparison ---------------- */
.adv-compare { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; }
.adv-compare h4 { font-size: 1rem; font-weight: 600; margin: 0 0 .6rem; padding: 0; }
.adv-mini { width: 100%; border-collapse: collapse; font-size: .9rem; }
.adv-mini td { padding: .55rem .2rem; border-top: 1px solid var(--hairline); vertical-align: top; }
.adv-mini tr:first-child td { border-top: 0; }
.adv-mini td:first-child { font-weight: 600; white-space: nowrap; padding-right: .9rem; }
.adv-mini td:last-child { text-align: right; color: var(--text-2); font-variant-numeric: tabular-nums; }
.adv-chips { display: flex; flex-wrap: wrap; gap: .4rem; margin: .4rem 0 0; }
.adv-chip { font-size: .85rem; font-weight: 600; padding: .28rem .7rem; border-radius: 980px; font-variant-numeric: tabular-nums; }
.adv-chip.add { background: var(--green-tint); color: var(--green); }
.adv-chip.rem { background: var(--red-tint); color: var(--red); text-decoration: line-through; }
.adv-chip.mov { background: var(--blue-tint); color: var(--blue-text); }
.adv-muted { color: var(--text-2); font-size: .93rem; }

/* ---------------- requirement rings ---------------- */
@property --t { syntax: "\\3C number>"; inherits: false; initial-value: 1; }
@keyframes adv-ring { from { --t: 0; } }
.adv-rings { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1.25rem 1rem; }
.adv-ring-item { margin: 0; display: flex; flex-direction: column; align-items: center; text-align: center; gap: .7rem; }
.adv-ring-wrap { position: relative; width: 92px; aspect-ratio: 1; }
.adv-ring-pct { position: absolute; inset: 0; display: grid; place-items: center; font-weight: 600;
  font-size: 1.05rem; letter-spacing: -0.01em; font-variant-numeric: tabular-nums; }
.adv-ring { position: absolute; inset: 0; border-radius: 50%;
  background: conic-gradient(var(--green) 0 calc(var(--d) * var(--t) * 1%),
                             var(--blue) 0 calc((var(--d) + var(--p)) * var(--t) * 1%),
                             var(--fill) 0);
  -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 11px), #000 calc(100% - 10px));
          mask: radial-gradient(farthest-side, transparent calc(100% - 11px), #000 calc(100% - 10px));
  animation: adv-ring 1.4s var(--spring) .35s both; }
.adv-ring-item figcaption { display: flex; flex-direction: column; gap: .15rem; font-size: .88rem; }
.adv-ring-item figcaption b { font-weight: 600; }
.adv-ring-item figcaption span { color: var(--text-2); font-variant-numeric: tabular-nums; }

/* ---------------- year view ---------------- */
.adv-years { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 1rem; }
.adv-year { background: var(--card); border-radius: var(--radius); box-shadow: var(--shadow); padding: 1.1rem 1.1rem 1.2rem;
  animation: adv-rise .55s var(--spring) both; animation-delay: calc(var(--i) * 70ms); }
.adv-year h4 { font-size: 1.05rem; font-weight: 600; margin: 0; padding: 0; }
.adv-year .adv-muted { margin: 0 0 .8rem; font-size: .85rem; }
.adv-yterm { border-top: 1px solid var(--hairline); padding: .65rem 0 .2rem; }
.adv-yterm-head { display: flex; justify-content: space-between; font-size: .85rem; font-weight: 600; margin-bottom: .45rem; }
.adv-yterm-head span:last-child { color: var(--text-2); font-weight: 500; font-variant-numeric: tabular-nums; }
.adv-ychips { display: flex; flex-wrap: wrap; gap: .3rem; }
.adv-ychips span { font-size: .78rem; font-weight: 600; padding: .2rem .5rem; border-radius: 6px;
  background: var(--blue-tint); color: var(--blue-text); font-variant-numeric: tabular-nums; }
.adv-yterm.done .adv-ychips span { background: var(--green-tint); color: var(--green); }

/* ---------------- rich cards inside chat replies ---------------- */
.adv-chatcard { background: var(--card); border-radius: 14px; padding: .75rem .9rem; margin: .65rem 0 .2rem;
  box-shadow: 0 0 0 1px var(--hairline); }
ul.adv-chatcard { padding: 0 !important; overflow: hidden; }
.adv-chatcard-head { display: flex; flex-wrap: wrap; justify-content: space-between; gap: .2rem 1rem;
  margin: .4rem 0 .4rem; font-size: .9rem; }
.adv-chatcard-head span { color: var(--text-2); }
.adv-chatcard .adv-row { grid-template-columns: 5.6rem 1fr auto; padding: .6rem .8rem; font-size: .9rem; }
[data-testid="stChatMessageContent"] .stButton > button { background: var(--card); min-height: 2.1rem; font-size: .88rem; }

/* ---------------- execution traces ---------------- */
.adv-trace-stats { margin: 0 0 1.25rem; }
.adv-traces { display: flex; flex-direction: column; gap: .75rem; }
.adv-trace { background: var(--card); border-radius: 14px; box-shadow: var(--shadow); padding: .95rem 1.1rem; }
.adv-trace header { display: flex; flex-wrap: wrap; align-items: center; gap: .45rem .6rem; }
.adv-trace-kind { font-weight: 600; font-size: .92rem; }
.adv-trace-meta { margin-left: auto; color: var(--text-2); font-size: .82rem; font-variant-numeric: tabular-nums; }
.adv-trace-q { margin: .55rem 0 .4rem; font-size: 1rem; }
.adv-trace-steps { list-style: none; margin: .3rem 0 0 !important; padding: 0 0 0 1rem !important;
  border-left: 2px solid var(--hairline); display: flex; flex-direction: column; gap: .45rem; }
.adv-trace-steps li { margin: 0 !important; display: grid; grid-template-columns: 8.5rem 1fr; gap: .6rem; font-size: .86rem; }
.adv-ev { color: var(--text-2); font-weight: 600; text-transform: capitalize; }
.adv-kv { display: flex; flex-wrap: wrap; gap: .25rem .9rem; font-size: .86rem; line-height: 1.4; }
.adv-kv i { font-style: normal; color: var(--text-2); margin-right: .15rem; }
.adv-trace.action { padding: .7rem 1.1rem; }
.adv-trace.action .adv-kv { margin-top: .35rem; }
.adv-src { font-size: .74rem; font-weight: 600; padding: .12rem .5rem; border-radius: 980px; white-space: nowrap; }
.adv-src.live { background: var(--green-tint); color: var(--green); }
.adv-src.preview { background: var(--orange-tint); color: var(--orange); }
.adv-src.not_ready { background: var(--fill); color: var(--text-2); }
.adv-src.intent { background: var(--blue-tint); color: var(--blue-text); text-transform: capitalize; }

@media (max-width: 720px) {
  .block-container { padding: 0 1rem 6rem; }
  .st-key-topbar { margin: 0 -1rem 1.75rem; padding: .5rem 1rem; }
  [class*="st-key-card_"] { padding: 1.25rem 1.1rem; }
  .adv-row { grid-template-columns: 1fr auto; }
  .adv-row .adv-title { grid-column: 1 / 3; grid-row: 2; }
  .adv-compare { grid-template-columns: 1fr; }
  .adv-trace-steps li { grid-template-columns: 1fr; gap: .1rem; }
  .adv-trace-meta { margin-left: 0; width: 100%; }
}
/* ---------------- motion ----------------
   Purposeful only (HIG motion.md): one load moment for the hero, and motion that
   answers an action (plan built, checks run, message sent, dialog opened).
   Nothing animates on hover or section switches. Every animated element's final
   state is its resting style, so reduced motion simply shows the end result. */
/* \\3C is the less-than sign: st.html drops a style block containing a raw one. */
@property --n { syntax: "\\3C integer>"; inherits: false; initial-value: 0; }
@keyframes adv-rise { from { opacity: 0; transform: translateY(14px); } }
@keyframes adv-fade { from { opacity: 0; } }
@keyframes adv-fill { from { transform: scaleX(0); } }
@keyframes adv-count { from { --n: 0; } }
@keyframes adv-pop-l { from { opacity: 0; transform: translateY(8px) scale(.94); } }
@keyframes adv-pop-r { from { opacity: 0; transform: translateY(8px) scale(.94); } }
@keyframes adv-sheet { from { opacity: 0; transform: translateY(24px) scale(.97); } }
@keyframes adv-dot { from { transform: scale(0); } }

.adv-hero h1 { animation: adv-rise .8s var(--spring) both; }
.adv-hero .sub { animation: adv-rise .8s var(--spring) .08s both; }
.adv-progress { animation: adv-fade .5s ease .15s both; }
.adv-progress span { transform-origin: left center; animation: adv-fill 1.25s var(--spring) .25s both; }
.adv-progress .planned { animation-delay: .55s; }
.adv-stats { animation: adv-rise .7s var(--spring) .3s both; }
.adv-sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
.adv-count { font-variant-numeric: tabular-nums; counter-reset: n var(--n); animation: adv-count 1.25s var(--spring) .25s both; }
.adv-count::after { content: counter(n); }

.adv-route.enter .adv-sem { animation: adv-rise .6s var(--spring) both;
  animation-delay: calc(min(var(--i), 10) * 55ms); }
.adv-route.enter .adv-sem::before { animation: adv-dot .45s var(--spring) both;
  animation-delay: calc(min(var(--i), 10) * 55ms + 120ms); }

.adv-checks-run .adv-check { animation: adv-rise .45s var(--spring) both;
  animation-delay: calc(var(--i) * 90ms); }
.adv-checks-run .adv-verdict { animation: adv-rise .5s var(--spring) .6s both; }

[data-testid="stChatMessage"] [data-testid="stChatMessageContent"] {
  transform-origin: bottom left; animation: adv-pop-l .42s var(--spring) both; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] {
  transform-origin: bottom right; animation-name: adv-pop-r; }
[role="dialog"] { animation: adv-sheet .5s var(--sheet) both; }

@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
@media (prefers-reduced-transparency: reduce) { .st-key-topbar { background: var(--page); backdrop-filter: none; } }
</style>
"""


def apply() -> None:
    st.html(CSS)
