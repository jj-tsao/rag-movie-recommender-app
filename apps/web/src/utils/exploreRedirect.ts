const EXPLORE_REDIRECT_KEY = "reelix_explore_used";

export function getExploreRedirectFlag(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(EXPLORE_REDIRECT_KEY) === "true";
  } catch (error) {
    void error;
    return false;
  }
}

export function setExploreRedirectFlag(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(EXPLORE_REDIRECT_KEY, "true");
  } catch (error) {
    void error;
  }
}
