export function getResponseErrorMessage(response: Response, fallback: string): string {
  switch (response.status) {
    case 401:
      return "Please sign in to continue.";
    case 403:
      return "You do not have access to that.";
    case 404:
      return "We could not find that. Please try again.";
    case 408:
      return "Request timed out. Please try again.";
    case 429:
      return "Too many requests. Please try again soon.";
    default:
      if (response.status >= 500) {
        return "Something went wrong on our end. Please try again.";
      }
      return fallback;
  }
}
