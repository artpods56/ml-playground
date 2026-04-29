const address = 'ws://' + window.location.hostname + ':8000/ws';
console.log('WebSocket address', address);
window.socket = new WebSocket(address);

function toggleDrawer() {
  const drawer = document.querySelector('input[type="checkbox"].drawer-toggle');
  if (drawer) {
    drawer.checked = false;
  }
}

document.addEventListener('DOMContentLoaded', function() {
  const socket = window.socket;

  socket.onopen = function(e) {
    console.log("[ws] Connection established");
  };

  socket.onclose = function(e) {
    console.log("[ws] Connection closed");
  };

  socket.onerror = function(e) {
    console.error("[ws] Connection error", e);
  };

  // Default message handler -- logs only.
  // Page-specific scripts (playground.js etc.) should override socket.onmessage.
  socket.onmessage = function(event) {
    console.log("[ws] Message received:", event.data);
  };
});