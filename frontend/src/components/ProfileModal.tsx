import { useEffect, useRef, useState } from "react";
import { HouseholdStatus, accountApi, householdApi } from "../api";
import { useAuth } from "../auth/AuthContext";
import { useConfirm } from "./ConfirmDialog";

interface ProfileModalProps {
  onClose: () => void;
  recordCount: number;
  medicationCount: number;
  onManageChildren: () => void;
}

export default function ProfileModal({
  onClose,
  recordCount,
  medicationCount,
  onManageChildren,
}: ProfileModalProps) {
  const { user, logout, refreshUser } = useAuth();
  const confirm = useConfirm();
  const dialogRef = useRef<HTMLDivElement>(null);

  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState(user?.display_name || "");
  const [nameBusy, setNameBusy] = useState(false);

  const [editingPassword, setEditingPassword] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [passwordBusy, setPasswordBusy] = useState(false);
  const [passwordDone, setPasswordDone] = useState(false);

  const [deleteStep, setDeleteStep] = useState<"idle" | "confirm">("idle");
  const [deleteText, setDeleteText] = useState("");
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  const [household, setHousehold] = useState<HouseholdStatus | null>(null);
  const [inviteLink, setInviteLink] = useState("");
  const [inviteBusy, setInviteBusy] = useState(false);
  const [inviteCopied, setInviteCopied] = useState(false);
  const [sharingError, setSharingError] = useState("");
  const [sharingBusy, setSharingBusy] = useState(false);

  const loadHousehold = async () => {
    try {
      setHousehold(await householdApi.status());
    } catch {
      // sharing section just stays hidden if this fails
    }
  };
  useEffect(() => {
    loadHousehold();
  }, []);

  const createInvite = async () => {
    setInviteBusy(true);
    setSharingError("");
    try {
      const { token } = await householdApi.invite();
      setInviteLink(`${window.location.origin}/join/${token}`);
      setInviteCopied(false);
    } catch (e) {
      setSharingError(e instanceof Error ? e.message : "Couldn't create invite");
    } finally {
      setInviteBusy(false);
    }
  };

  const copyInvite = async () => {
    try {
      await navigator.clipboard.writeText(inviteLink);
      setInviteCopied(true);
      setTimeout(() => setInviteCopied(false), 2000);
    } catch {
      // clipboard permission denied - the link is still shown to copy by hand
    }
  };

  const removeMember = async (memberId: string) => {
    const ok = await confirm({
      message: "Remove this person's access to your account?",
      confirmLabel: "Remove",
      danger: true,
    });
    if (!ok) return;
    setSharingBusy(true);
    setSharingError("");
    try {
      await householdApi.removeMember(memberId);
      await loadHousehold();
    } catch (e) {
      setSharingError(e instanceof Error ? e.message : "Couldn't remove member");
    } finally {
      setSharingBusy(false);
    }
  };

  const leaveHousehold = async () => {
    const ok = await confirm({
      message: "Stop sharing this account? You'll only see your own records.",
      confirmLabel: "Stop sharing",
      danger: true,
    });
    if (!ok) return;
    setSharingBusy(true);
    setSharingError("");
    try {
      await householdApi.leave();
      await loadHousehold();
    } catch (e) {
      setSharingError(e instanceof Error ? e.message : "Couldn't leave");
    } finally {
      setSharingBusy(false);
    }
  };

  // Focus trap + Esc/click-outside + return focus to the trigger on close.
  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    dialogRef.current?.focus();

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key !== "Tab" || !dialogRef.current) return;
      const focusables = dialogRef.current.querySelectorAll<HTMLElement>(
        'button, input, a[href], [tabindex]:not([tabindex="-1"])'
      );
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      previouslyFocused?.focus();
    };
  }, [onClose]);

  const initial = (user?.display_name || user?.email || "?").charAt(0).toUpperCase();

  const saveName = async () => {
    const name = nameDraft.trim();
    setNameBusy(true);
    try {
      await accountApi.updateProfile(name);
      await refreshUser();
      setEditingName(false);
    } catch {
      // keep the field open with whatever the user typed - inline error
      // isn't in the spec here, so just leave editing mode active
    } finally {
      setNameBusy(false);
    }
  };

  const savePassword = async () => {
    setPasswordError("");
    if (newPassword.length < 10) {
      setPasswordError("New password must be at least 10 characters.");
      return;
    }
    setPasswordBusy(true);
    try {
      await accountApi.changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setEditingPassword(false);
      setPasswordDone(true);
      await refreshUser();
      setTimeout(() => setPasswordDone(false), 3000);
    } catch (e) {
      setPasswordError(e instanceof Error ? e.message : "Couldn't change password");
    } finally {
      setPasswordBusy(false);
    }
  };

  const confirmDelete = async () => {
    setDeleteError("");
    setDeleteBusy(true);
    try {
      await accountApi.deleteAccount(deleteText);
      await logout();
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : "Couldn't delete account");
    } finally {
      setDeleteBusy(false);
    }
  };

  const passwordChangedLabel = user?.password_changed_at
    ? `Changed ${new Date(user.password_changed_at).toLocaleDateString()}`
    : user?.created_at
    ? `Set when you registered`
    : "";

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal profile-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="profile-modal-name"
        tabIndex={-1}
        ref={dialogRef}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-head profile-modal-head">
          <div className="avatar-tile profile-modal-avatar">{initial}</div>
          <div className="profile-modal-headtext">
            <div id="profile-modal-name" className="name">
              {user?.display_name || user?.email}
            </div>
            <div className="email">{user?.email}</div>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div className="modal-body profile-modal-body">
          <div className="profile-stats">
            <div className="fact-cell">
              <div className="fact-label">RECORDS</div>
              <div className="fact-value">{recordCount}</div>
            </div>
            <div className="fact-cell">
              <div className="fact-label">MEDICATIONS</div>
              <div className="fact-value">{medicationCount}</div>
            </div>
          </div>

          <div className="profile-section">
            <div className="profile-section-heading">ACCOUNT</div>

            <div className="profile-row">
              <span className="profile-label">Name</span>
              {editingName ? (
                <span className="profile-inline-edit">
                  <input
                    value={nameDraft}
                    onChange={(e) => setNameDraft(e.target.value)}
                    autoFocus
                  />
                  <button className="profile-row-action" onClick={saveName} disabled={nameBusy}>
                    Save
                  </button>
                </span>
              ) : (
                <>
                  <span>{user?.display_name || "—"}</span>
                  <button
                    className="profile-row-action"
                    onClick={() => {
                      setNameDraft(user?.display_name || "");
                      setEditingName(true);
                    }}
                  >
                    Edit
                  </button>
                </>
              )}
            </div>

            <div className="profile-row">
              <span className="profile-label">Email</span>
              <span>{user?.email}</span>
            </div>

            <div className="profile-row">
              <span className="profile-label">Password</span>
              {editingPassword ? (
                <span className="profile-inline-edit password">
                  <input
                    type="password"
                    placeholder="Current password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    autoFocus
                  />
                  <input
                    type="password"
                    placeholder="New password (10+ chars)"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                  />
                  <button
                    className="profile-row-action"
                    onClick={savePassword}
                    disabled={passwordBusy}
                  >
                    Save
                  </button>
                </span>
              ) : (
                <>
                  <span>{passwordDone ? "Updated" : passwordChangedLabel}</span>
                  <button
                    className="profile-row-action"
                    onClick={() => setEditingPassword(true)}
                  >
                    Change
                  </button>
                </>
              )}
            </div>
            {passwordError && <p className="field-hint error-text">{passwordError}</p>}
          </div>

          <div className="profile-section">
            <div className="profile-section-heading">FAMILY</div>
            <div className="profile-row">
              <span className="profile-label">Children</span>
              <button className="profile-row-action" onClick={onManageChildren}>
                Manage
              </button>
            </div>
          </div>

          {household && (
            <div className="profile-section">
              <div className="profile-section-heading">FAMILY &amp; SHARING</div>

              {household.owner_email ? (
                <div className="profile-row">
                  <span className="profile-label" title={`Sharing ${household.owner_email}'s account`}>
                    Sharing {household.owner_email}&apos;s account
                  </span>
                  <button
                    className="profile-row-action"
                    onClick={leaveHousehold}
                    disabled={sharingBusy}
                  >
                    Leave
                  </button>
                </div>
              ) : (
                <>
                  {household.members.map((m) => (
                    <div className="profile-row" key={m.id}>
                      <span className="profile-label" title={m.display_name || m.email}>
                        {m.display_name || m.email}
                      </span>
                      <button
                        className="profile-row-action"
                        onClick={() => removeMember(m.id)}
                        disabled={sharingBusy}
                      >
                        Remove
                      </button>
                    </div>
                  ))}

                  {inviteLink ? (
                    <div className="profile-row">
                      <span className="profile-inline-edit" style={{ justifyContent: "flex-start", flex: 1 }}>
                        <input value={inviteLink} readOnly onFocus={(e) => e.target.select()} />
                        <button className="profile-row-action" onClick={copyInvite}>
                          {inviteCopied ? "Copied!" : "Copy"}
                        </button>
                      </span>
                    </div>
                  ) : (
                    <div className="profile-row">
                      <span className="profile-label">Invite a co-parent</span>
                      <button
                        className="profile-row-action"
                        onClick={createInvite}
                        disabled={inviteBusy}
                      >
                        Get link
                      </button>
                    </div>
                  )}
                </>
              )}
              {sharingError && <p className="field-hint error-text">{sharingError}</p>}
            </div>
          )}

          <div className="profile-data-note">
            <span className="profile-data-icon">✓</span>
            <p>
              Records are encrypted at rest and never used to train anything. Only you
              can read them.
            </p>
          </div>

          <div className="profile-data-actions">
            <button className="ghost" onClick={() => accountApi.exportData()}>
              Export my records
            </button>
            {deleteStep === "idle" ? (
              <button
                className="danger-btn"
                onClick={() => setDeleteStep("confirm")}
              >
                Delete everything
              </button>
            ) : null}
          </div>

          {deleteStep === "confirm" && (
            <div className="delete-confirm">
              <p>
                This permanently deletes your account and every record in it. Type{" "}
                <strong>delete my account</strong> to confirm.
              </p>
              <input
                value={deleteText}
                onChange={(e) => setDeleteText(e.target.value)}
                placeholder="delete my account"
              />
              {deleteError && <p className="field-hint error-text">{deleteError}</p>}
              <div className="delete-confirm-actions">
                <button
                  className="danger-btn"
                  onClick={confirmDelete}
                  disabled={
                    deleteBusy || deleteText.trim().toLowerCase() !== "delete my account"
                  }
                >
                  Permanently delete
                </button>
                <button
                  className="ghost"
                  onClick={() => {
                    setDeleteStep("idle");
                    setDeleteText("");
                    setDeleteError("");
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          <button className="signout-full" onClick={logout}>
            Sign out
          </button>
        </div>
      </div>
    </div>
  );
}
