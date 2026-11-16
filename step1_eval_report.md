# Step 1: Drawing Libraries Evaluation Report

I have cloned and evaluated all three repositories locally against your specific requirements for a drop-in web replacement. 

## 1. `deepentropy/lightweight-charts-drawing`
*   **Placement**: **Yes** - The documentation explicitly lists `long-position` and `short-position` as "1 click" placement tools using TradingView defaults.
*   **Dragging**: **Yes** - Full TradingView-style dragging (individual handles, moving the whole box) and hit testing.
*   **v5 Support**: **Yes** - Natively targets Lightweight Charts v5.
*   **Events/API**: **Yes** - Emits `add`, `update`, `change` events. The drawn instances expose their exact `points` (time, price) so our backend can track entry/stop/target live.
*   **Save/Load**: **Yes** - Provides `exportJSON()` and `importJSON()` out of the box with version migration.
*   **License**: MIT
*   **Last Commit**: October 2, 2026 (Extremely active).

## 2. `difurious/lightweight-charts-line-tools-core`
*   **Placement**: **No** - Typically requires a 2-click placement (click start, drag, click end) based on the old v3.8 model, requiring custom wrappers to force 1-click default sizing.
*   **Dragging**: **Yes** - Supports handle and body dragging.
*   **v5 Support**: **Yes** - Built as a v5 plugin orchestrator.
*   **Events/API**: **Yes** - Exposes state, but the API requires registering multiple separate plugin packages to the core orchestrator.
*   **Save/Load**: Partial/Manual - You have to serialize the plugin states yourself.
*   **License**: MPL 2.0
*   **Last Commit**: July 15, 2026.

## 3. `jezztify/backtesting-app` (Reference)
*   A great reference application, but its internal drawing primitives are tied to an older, monolithic React codebase. 
*   **Last Commit**: November 11, 2025.

---

### Recommendation
I strongly recommend **`deepentropy/lightweight-charts-drawing`**. 
It perfectly hits your requirements: it is literally 1-click placement, has native `exportJSON()`, natively emits `update` events when you drag a handle so we can send the new `entry/sl/tp` to FastAPI, and uses the MIT license. 

Do you approve this recommendation so we can move to **Step 2 (Architecture)** and build the FastAPI + Vite stack?
