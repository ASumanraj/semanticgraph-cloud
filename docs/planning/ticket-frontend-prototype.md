## Question

How should we prototype the SemanticGraph Cloud Tenant Dashboard (focusing on Ontology management and Document Uploads)? Given the `modern-web-guidance` skill, what modern HTML/CSS/JS APIs (e.g., View Transitions, modern layouts) should we use to prototype effectively without bloating the project with legacy frameworks?

**Labels**: `wayfinder:research`, `wayfinder:prototype`, `closed`

### Resolution: Prototype Recommendations

Based on the `modern-web-guidance` best practices for a zero-bloat, modern HTML/CSS/JS setup, we recommend the following approach for prototyping the SemanticGraph Cloud Tenant Dashboard:

**1. Architecture & Setup:**
- **No Legacy Frameworks:** Stick to vanilla HTML/JS/CSS using a lightweight bundler like **Vite**. If minimal reactivity is required (e.g., handling document upload states), use **Alpine.js** or standard Web Components.

**2. Modern HTML/CSS APIs for the UI:**
- **Modals (Document Uploads / Ontology Edits):** Use the native `<dialog>` element. It handles top-layer stacking, focus management, and accessibility out-of-the-box without extra JavaScript.
- **Context Menus & Dropdowns:** Use the native **Popover API** (`popover` attribute) combined with **CSS Anchor Positioning**. This eliminates the need for heavy positioning libraries (like Popper.js) to tether menus to ontology nodes or document list items, automatically handling viewport edges.
- **State Preservation (Top Layer):** If an ontology node or document item is reparented in the DOM while a popover/dialog is open, use the `moveBefore()` API to keep the UI visibly open and active without breaking state.
- **Seamless Navigation:** Use the **View Transitions API** for single-page-app-like transitions between the Dashboard and Document Upload views without needing a heavy SPA router.
- **Responsive Layout:** Utilize **CSS Grid** (with `subgrid` for nested alignment) and **Container Queries** (`@container`) instead of legacy `@media` queries. This makes the dashboard components independently responsive.
