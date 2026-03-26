import "./styles.css";

import { startDesktopApp } from "./app/bootstrap.ts";

const app = document.querySelector<HTMLDivElement>("#app");

if (!app) {
  throw new Error("Missing app root");
}

startDesktopApp(app);
