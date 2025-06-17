export function getDeviceInfo() {
  const ua = navigator.userAgent;
  const platform = navigator.platform || "unknown";
  const deviceType = /Mobi|Android|iPhone|iPad|iPod/i.test(ua) ? "mobile" : "desktop";

  return {
    device_type: deviceType,
    platform,
    user_agent: ua,
  };
}

