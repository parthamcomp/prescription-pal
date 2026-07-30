import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Profile() {
  const { user, logout } = useAuth();

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="brand">
          <div className="logo">Rx</div>
          <div>
            <h1>Your profile</h1>
            <p>Account details</p>
          </div>
        </div>

        <div className="profile-row">
          <span className="profile-label">Name</span>
          <span>{user?.display_name || "—"}</span>
        </div>
        <div className="profile-row">
          <span className="profile-label">Email</span>
          <span>{user?.email}</span>
        </div>

        <div className="actions">
          <Link className="btn-link" to="/">
            Back to app
          </Link>
          <button className="ghost danger" onClick={logout}>
            Sign out
          </button>
        </div>
      </div>
    </div>
  );
}
