# Paper briefing UI

This revision changes presentation only. Translation, parsing, file watching, cache keys, auto-opening, launcher integration and military-data validation remain unchanged. The only edit in `main.py` is the body of `document(body, status)`, which now fills the standalone HTML template; its callers and saving flow are unchanged.

The paper uses the requested #ECE7DC ivory, #1F262A ink, #66705F olive and #5B6D79 blue. A low-opacity CSS/SVG grain sits in a pointer-transparent pseudo-element. The backing board exposes about 10px around the page; a small CSS metal clip and muted physical divider tabs support the paper rather than framing it as a dashboard. All operational content remains actual selectable HTML text and tables.

Pretendard, IBM Plex Sans Condensed and IBM Plex Mono are embedded as WOFF2 data in the CSS, with their OFL notices. No fonts or textures load from a CDN. `paper-theme.css` is the editable theme source; `build_ui.py` generates self-contained `briefing.css`, `viewer.html` and `standalone.html` from the source templates and shared `paper_document.js`.

The first A4 sheet is reserved for the actual mission overview, situation and crew when those sections exist. Further content is paginated at block/table-row boundaries, with table headings repeated where needed. Tabs navigate to the source section's page; language and viewport changes reflow the real content. Maps, routes or mission fields are never invented.

Screen mode shows one sheet mounted on the board. Print-preview-like mode removes grain, tabs and the board. The print stylesheet uses A4, prints every sheet, removes the reader toolbar and keeps operational rows together. Very large indivisible blocks may use a longer sheet instead of clipping content.

Screenshots and the data-preservation report are in `ui-review/`. Browser tooling does not allow file:// navigation, so direct browser opening of the standalone local file could not be automated. Its inline assets and source data are checked statically; the shared renderer is exercised in the live viewer.

No reference image was attached to the redesign request; the explicit palette and material instructions are the visual reference used.
