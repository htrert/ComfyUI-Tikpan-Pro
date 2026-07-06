import { useEffect, useMemo, useState } from "react";
import { AppShell } from "./components/AppShell";
import { currentUser } from "./appData";
import type { AccountSection, AppRoute, Template } from "./types";

function routeFromPath(pathname: string): AppRoute {
  if (pathname.startsWith("/explore")) return "explore";
  if (pathname.startsWith("/account") || pathname.startsWith("/admin")) return "account";
  return "workspace";
}

function pathForRoute(route: AppRoute) {
  if (route === "explore") return "/explore";
  if (route === "account") return "/account";
  if (route === "admin") return "/admin";
  return "/workspace";
}

function App() {
  const [route, setRoute] = useState<AppRoute>(() =>
    typeof window === "undefined" ? "workspace" : routeFromPath(window.location.pathname),
  );
  const [accountSection, setAccountSection] = useState<AccountSection>(() =>
    typeof window !== "undefined" && window.location.pathname.startsWith("/admin") ? "admin-overview" : "assets",
  );
  const [templatePrompt, setTemplatePrompt] = useState("");

  useEffect(() => {
    const handlePopState = () => {
      setRoute(routeFromPath(window.location.pathname));
    };

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const navigate = useMemo(
    () => (nextRoute: AppRoute, nextAccountSection?: AccountSection) => {
      if (nextAccountSection) setAccountSection(nextAccountSection);
      setRoute(nextRoute);

      const nextPath = pathForRoute(nextRoute);
      if (typeof window !== "undefined" && window.location.pathname !== nextPath) {
        window.history.pushState({}, "", nextPath);
      }
    },
    [],
  );

  const useTemplate = (template: Template) => {
    setTemplatePrompt(template.prompt);
    navigate("workspace");
  };

  return (
    <AppShell
      accountSection={accountSection}
      isAdmin={currentUser.role === "admin"}
      route={route}
      templatePrompt={templatePrompt}
      user={currentUser}
      onAccountSectionChange={setAccountSection}
      onNavigate={navigate}
      onUseTemplate={useTemplate}
    />
  );
}

export default App;
