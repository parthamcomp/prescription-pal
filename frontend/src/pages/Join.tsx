import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { householdApi } from "../api";
import Logo from "../components/Logo";

export default function Join() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [ownerEmail, setOwnerEmail] = useState<string | null>(null);

  const join = async () => {
    if (!token) return;
    setBusy(true);
    setError("");
    try {
      const status = await householdApi.join(token);
      setOwnerEmail(status.owner_email);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't join this account");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-column">
        <div className="auth-header">
          <Logo size={46} />
          <h1>Join a shared account</h1>
          {!ownerEmail && (
            <p>You&apos;ve been invited to share a family&apos;s prescription records.</p>
          )}
        </div>

        {ownerEmail ? (
          <div className="auth-card v2 compact">
            <p>
              You&apos;re now sharing <strong>{ownerEmail}</strong>&apos;s account. You&apos;ll
              see the same children and records they do.
            </p>
            <button className="auth-submit" onClick={() => navigate("/ask")}>
              Go to my account
            </button>
          </div>
        ) : (
          <div className="auth-card v2 compact">
            {error && <div className="auth-error">{error}</div>}
            <p>
              Joining gives you full access to their saved prescriptions and children. Any
              records already on your own account stay private and become visible again if
              you ever leave.
            </p>
            <button className="auth-submit" onClick={join} disabled={busy}>
              {busy ? "Joining…" : "Accept and join"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
