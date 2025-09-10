import React, { useEffect } from "react";
import Routes from "./Routes";
import { wsService } from "./services/websocket";
import { authService } from "./services/auth";

function App() {
  useEffect(() => {
    // Initialize WebSocket connection with ensured auth
    (async () => {
      try { await authService.ensureLoggedIn(); } catch {}
      wsService.connect();
    })();

    // Cleanup on unmount
    return () => {
      wsService.disconnect();
    };
  }, []);

  return (
    <Routes />
  );
}

export default App;
