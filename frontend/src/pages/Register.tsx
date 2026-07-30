import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import Logo from "../components/Logo";

const MIN_LENGTH = 10;

// Not zxcvbn - a small, honest heuristic (length + character variety) so we
// don't pull in a new dependency for this. Never blocks submission by
// itself; only the length >= 10 floor does.
function scorePassword(pw: string): { score: 0 | 1 | 2 | 3; label: string } {
  if (pw.length === 0) return { score: 0, label: "" };
  if (pw.length < MIN_LENGTH) return { score: 1, label: "Weak" };
  let variety = 0;
  if (/[a-z]/.test(pw)) variety++;
  if (/[A-Z]/.test(pw)) variety++;
  if (/[0-9]/.test(pw)) variety++;
  if (/[^A-Za-z0-9]/.test(pw)) variety++;
  if (pw.length >= 14 && variety >= 3) return { score: 3, label: "Strong" };
  if (variety >= 2) return { score: 2, label: "Good" };
  return { score: 1, label: "Weak" };
}

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const strength = useMemo(() => scorePassword(password), [password]);
  const valid = email.trim() && password.length >= MIN_LENGTH && consent;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    setBusy(true);
    setError("");
    try {
      await register(email, password, displayName, consent);
      navigate("/ask");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-column">
        <div className="auth-header">
          <Logo size={46} />
          <h1>Create your account</h1>
          <p>Add one prescription and you can start asking.</p>
        </div>

        {error && <div className="auth-error">{error}</div>}

        <form className="auth-card v2 compact" onSubmit={submit}>
          <label>
            YOUR NAME
            <input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Optional"
              autoComplete="name"
            />
          </label>
          <label>
            EMAIL
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </label>
          <label>
            PASSWORD
            <span className="auth-password-field">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="new-password"
              />
              <button
                type="button"
                className="auth-show-toggle"
                aria-pressed={showPassword}
                onClick={() => setShowPassword((v) => !v)}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </span>
            <span className="auth-helper-line">At least {MIN_LENGTH} characters.</span>
          </label>

          {password.length > 0 && (
            <div className="strength-meter">
              <div className="strength-bars">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className={`strength-bar ${i < strength.score ? `s${strength.score}` : ""}`}
                  />
                ))}
              </div>
              <span className={`strength-label s${strength.score}`}>{strength.label}</span>
            </div>
          )}

          <label className="consent-row">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
            />
            <span>
              I understand this app repeats what my prescriptions say and is not
              medical advice.
            </span>
          </label>

          <button type="submit" className="auth-submit" disabled={busy || !valid}>
            {busy ? "Creating…" : "Create account"}
          </button>
        </form>

        <p className="auth-alt">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </div>
    </div>
  );
}
