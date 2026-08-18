import { ReactElement, useEffect, useState } from "react";
import {
  Link,
  useLocation,
  useNavigate,
  useSearchParams,
} from "react-router-dom";
import { Child, Med, Prescription, childrenApi, medicationsApi, prescriptionsApi } from "./api";
import { useAuth } from "./auth/AuthContext";
import ChildrenModal from "./components/ChildrenModal";
import { useConfirm } from "./components/ConfirmDialog";
import Logo from "./components/Logo";
import ProfileModal from "./components/ProfileModal";
import { MED_COLOR_HEX, pluralize } from "./lib/format";
import AskView from "./views/AskView";
import RecordsView from "./views/RecordsView";
import UploadView from "./views/UploadView";

type Tab = "ask" | "records" | "upload";

function AskIcon({ color }: { color: string }) {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 5.5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H8l-4 3.5V13.5H5a2 2 0 0 1-2-2Z" />
    </svg>
  );
}

function RecordsIcon({ color }: { color: string }) {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="2.75" width="12" height="14.5" rx="3" />
      <path d="M7.5 7.5h5M7.5 11h3" />
    </svg>
  );
}

function UploadIcon({ color }: { color: string }) {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 13.5V4M6.5 7.5 10 4l3.5 3.5" />
      <path d="M4 13v2a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2v-2" />
    </svg>
  );
}

const NAV_ICON_COLORS: Record<Tab, string> = {
  ask: "#5B4BE6",
  records: "#17C39A",
  upload: "#FF6B5A",
};

function viewForPath(pathname: string): Tab {
  if (pathname.startsWith("/records")) return "records";
  if (pathname.startsWith("/upload")) return "upload";
  return "ask";
}

export default function App() {
  const { user, logout } = useAuth();
  const confirm = useConfirm();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const view = viewForPath(location.pathname);

  const [prescriptions, setPrescriptions] = useState<Prescription[]>([]);
  const [recordsLoading, setRecordsLoading] = useState(true);
  const [recordsError, setRecordsError] = useState("");
  const [meds, setMeds] = useState<Med[]>([]);
  const [selectedMedId, setSelectedMedId] = useState<string | null>(null);
  const [showAllMeds, setShowAllMeds] = useState(false);
  const [children, setChildren] = useState<Child[]>([]);
  const [childrenModalOpen, setChildrenModalOpen] = useState(false);

  const profileOpen = searchParams.get("profile") === "1";
  const openProfile = () => {
    const next = new URLSearchParams(searchParams);
    next.set("profile", "1");
    setSearchParams(next);
  };
  const closeProfile = () => {
    const next = new URLSearchParams(searchParams);
    next.delete("profile");
    setSearchParams(next);
  };
  const openChildrenModal = () => {
    closeProfile();
    setChildrenModalOpen(true);
  };

  const loadPrescriptions = async () => {
    try {
      setRecordsError("");
      setPrescriptions(await prescriptionsApi.list());
    } catch (e) {
      setRecordsError(e instanceof Error ? e.message : "Failed to load records");
    } finally {
      setRecordsLoading(false);
    }
  };

  const loadMedications = async () => {
    try {
      setMeds(await medicationsApi.list());
    } catch {
      // sidebar is a nice-to-have derived view - don't block the app on it
    }
  };

  const loadChildren = async () => {
    try {
      setChildren(await childrenApi.list());
    } catch {
      // child picker/filter degrade to "no children yet" - not fatal
    }
  };

  useEffect(() => {
    loadPrescriptions();
    loadMedications();
    loadChildren();
  }, []);

  useEffect(() => {
    if (location.pathname === "/") navigate("/ask", { replace: true });
  }, [location.pathname, navigate]);

  const deletePrescription = async (id: string) => {
    if (!id) return;
    if (!(await confirm({ message: "Delete this record?", confirmLabel: "Delete", danger: true }))) return;
    try {
      await prescriptionsApi.delete(id);
      if (location.pathname === `/records/${id}`) navigate("/records");
      await loadPrescriptions();
      await loadMedications();
    } catch (e) {
      setRecordsError(e instanceof Error ? e.message : "Failed to delete");
    }
  };

  const handleMedClick = (m: Med) => {
    setSelectedMedId(m.id);
    navigate("/ask", { state: { seedQuestion: `Tell me about ${m.name}` } });
  };

  const initial = (user?.display_name || user?.email || "?").charAt(0).toUpperCase();

  const navItems: { key: Tab; label: string; icon: (color: string) => ReactElement }[] = [
    { key: "ask", label: "Ask", icon: (c) => <AskIcon color={c} /> },
    { key: "records", label: "Records", icon: (c) => <RecordsIcon color={c} /> },
    { key: "upload", label: "Upload", icon: (c) => <UploadIcon color={c} /> },
  ];

  const activeMeds = meds.filter((m) => m.active);
  const visibleMeds = showAllMeds ? activeMeds : activeMeds.slice(0, 6);

  return (
    <div className="shell">
      <aside className="rail">
        <div className="rail-brand">
          <Logo size={36} className="logo-mark" />
          <div className="rail-brand-text">
            <div className="name">Prescription Pal</div>
            <div className="sub">{pluralize(prescriptions.length, "record")}, all yours</div>
          </div>
        </div>

        <nav className="rail-nav">
          {navItems.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`nav-item ${view === item.key ? "active" : ""}`}
              onClick={() => navigate(`/${item.key}`)}
            >
              <span className="nav-icon">
                {item.icon(view === item.key ? "#FFFFFF" : NAV_ICON_COLORS[item.key])}
              </span>
              <span className="nav-label">{item.label}</span>
              {item.key === "records" && (
                <span className="nav-count">{prescriptions.length}</span>
              )}
            </button>
          ))}
        </nav>

        {activeMeds.length > 0 && (
          <div className="rail-meds">
            <div className="rail-meds-heading">YOUR MEDS</div>
            <div className="rail-meds-list">
              {visibleMeds.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  className={`rail-med-row ${selectedMedId === m.id ? "selected" : ""}`}
                  onClick={() => handleMedClick(m)}
                >
                  <span className="med-chip" style={{ background: MED_COLOR_HEX[m.color_key] }} />
                  <span className="rail-med-name">{m.name}</span>
                  <span className="rail-med-cadence">{m.cadence}</span>
                </button>
              ))}
              {!showAllMeds && activeMeds.length > 6 && (
                <button
                  type="button"
                  className="rail-med-show-all"
                  onClick={() => setShowAllMeds(true)}
                >
                  Show all ({activeMeds.length})
                </button>
              )}
            </div>
          </div>
        )}

        {view === "upload" && (
          <div className="rail-tip-card">
            <div className="rail-tip-title">Tips for a clean read</div>
            <div className="rail-tip-body">
              Flat paper, no shadow, all four corners in frame.
            </div>
          </div>
        )}

        <div className="rail-spacer" />

        <div className="rail-account">
          <button className="rail-account-link" onClick={openProfile} title="View profile">
            <div className="avatar-tile">{initial}</div>
            <div className="rail-account-text">
              <div className="name">{user?.display_name || user?.email}</div>
              <div className="sub">Private &amp; encrypted</div>
            </div>
          </button>
          <button className="signout-btn" onClick={logout} title="Sign out">
            ↪
          </button>
        </div>
      </aside>

      <main className="main">
        <div className="mobilebar">
          <Logo size={30} />
          <div className="name">Prescription Pal</div>
          {view === "ask" && (
            <Link className="mobilebar-newchat" to="/ask" title="Ask">
              +
            </Link>
          )}
          <button className="avatar-tile" onClick={openProfile} title="View profile">
            {initial}
          </button>
        </div>

        <AskView visible={view === "ask"} prescriptions={prescriptions} />
        <RecordsView
          visible={view === "records"}
          prescriptions={prescriptions}
          meds={meds}
          childList={children}
          loading={recordsLoading}
          error={recordsError}
          onDelete={deletePrescription}
          onUpdated={loadPrescriptions}
          onManageChildren={openChildrenModal}
        />
        <UploadView
          visible={view === "upload"}
          hasRecords={prescriptions.length > 0}
          childList={children}
          onManageChildren={openChildrenModal}
          onSaved={() => {
            loadPrescriptions();
            loadMedications();
          }}
        />

        <nav className="bottomnav">
          {navItems.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`bottomnav-item ${view === item.key ? "active" : ""}`}
              onClick={() => navigate(`/${item.key}`)}
            >
              {item.icon(view === item.key ? "#4536C9" : NAV_ICON_COLORS[item.key])}
              <span className="label">{item.label}</span>
            </button>
          ))}
        </nav>
      </main>

      {profileOpen && (
        <ProfileModal
          onClose={closeProfile}
          recordCount={prescriptions.length}
          medicationCount={meds.length}
          onManageChildren={openChildrenModal}
        />
      )}

      {childrenModalOpen && (
        <ChildrenModal
          onClose={() => setChildrenModalOpen(false)}
          childList={children}
          onChanged={loadChildren}
        />
      )}
    </div>
  );
}
