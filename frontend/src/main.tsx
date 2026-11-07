import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import StaffApp from "./staff/StaffApp";
import "./i18n";
import "./index.css";

// The back office lives at /#/staff in the same PWA. Staff and owner sessions use separate cookies.
const isStaff = () => window.location.hash.startsWith("#/staff");

function Root() {
  return isStaff() ? <StaffApp /> : <App />;
}

createRoot(document.getElementById("root")!).render(<StrictMode><Root /></StrictMode>);
window.addEventListener("hashchange", () => window.location.reload());

if ("serviceWorker" in navigator && import.meta.env.PROD) {
  navigator.serviceWorker.register("/sw.js").catch(() => undefined);
}
