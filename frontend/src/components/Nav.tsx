import { NavLink } from "react-router-dom";

export function Nav() {
  return (
    <nav className="nav">
      <div className="nav-title">
        <span className="dot">●</span> NBA Scout Agent
      </div>
      <div className="nav-links">
        <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
          Chat
        </NavLink>
        <NavLink to="/admin" className={({ isActive }) => (isActive ? "active" : "")}>
          Admin
        </NavLink>
      </div>
    </nav>
  );
}
