import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { me } from "../api/client";
import Loading from "./Loading";

export default function UnderwriterRoute({ children }) {
  const [state, setState] = useState("loading");

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      setState("unauthenticated");
      return;
    }
    me()
      .then(u => {
        const r = (u.role || "").toLowerCase();
        setState(r === "underwriter" || r === "admin" ? "ok" : "forbidden");
      })
      .catch(() => {
        localStorage.removeItem("access_token");
        setState("unauthenticated");
      });
  }, []);

  if (state === "loading") return <Loading />;
  if (state === "ok") return children;
  if (state === "forbidden") return <Navigate to="/dashboard" replace />;
  return <Navigate to="/login" replace />;
}
