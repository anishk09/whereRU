// How this page is being shown.
const params = new URLSearchParams(window.location.search);

/** Inside the desktop showcase's phone frames: skip sign-in and open as the frame's persona. */
export const embedded = params.has("embed") || window.self !== window.top;

/** Desktop with a mouse: show the showcase (pitch + two live phones). `?app` opens the plain app. */
export const showcase = !embedded && !params.has("app") &&
  window.matchMedia("(min-width: 1024px) and (hover: hover) and (pointer: fine)").matches;

// Lets the stylesheet give framed phones the iPhone's safe areas (Dynamic Island, home indicator).
if (embedded) document.documentElement.dataset.embed = "1";
