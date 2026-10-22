import type { RouteRecord } from "vite-react-ssg";
import { Outlet } from "react-router-dom";
import "./index.css";
import { docSlugs, type Lang } from "./content";
import Home from "./pages/Home";
import Doc from "./pages/Doc";
import Schema from "./pages/Schema";
import Check from "./pages/Check";
import Badges from "./pages/Badges";

const pages = (lang: Lang): RouteRecord[] => [
  { index: true, element: <Home lang={lang} /> },
  { path: "schema", element: <Schema lang={lang} /> },
  { path: "check", element: <Check lang={lang} /> },
  { path: "badges", element: <Badges lang={lang} /> },
  ...docSlugs.map((slug) => ({ path: slug, element: <Doc key={`${lang}-${slug}`} lang={lang} slug={slug} /> })),
];
export const routes: RouteRecord[] = [
  { path: "/", element: <Outlet />, children: [...pages("en"), { path: "ja", element: <Outlet />, children: pages("ja") }] },
];
