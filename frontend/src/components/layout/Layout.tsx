import type { PropsWithChildren } from "react";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";

interface LayoutProps extends PropsWithChildren {
  showSidebar?: boolean;
  contentClassName?: string;
}

export function Layout({ children, showSidebar = true, contentClassName = "" }: LayoutProps) {
  return (
    <div className="app-shell">
      <Header />
      <div className={`app-body ${showSidebar ? "app-body-with-sidebar" : "app-body-no-sidebar"}`}>
        {showSidebar ? <Sidebar /> : null}
        <main className={`app-content ${showSidebar ? "app-content-with-sidebar" : "app-content-full"} ${contentClassName}`.trim()}>
          <div className={`app-content-inner ${showSidebar ? "app-content-inner-wide" : "app-content-inner-centered"}`}>
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
